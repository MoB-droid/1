#!/usr/bin/env python3
"""
ASTS TRIGGER WATCH  -  bot, category Bot, runs on the PC beside pp_server.

WHAT IT DOES (every 2 min, 24/7, no LLM in the loop):
  1. reads the sheet: Sources (on), Map (terms + weights), Rules (thresholds)
  2. pulls only NEW headlines from each source (RSS / Atom / SEC EDGAR)
  3. keyword-matches every headline against the Map; EDGAR filings pass on form type
  4. candidate (kw score >= threshold)  ->  one short SB (claude -p) call scores it 1-10
  5. writes the candidate to the Hits tab (newest on top)
  6. llm score >= fire threshold  ->  runs FIRE_CMD (Trade Map -> Trader fast lane), if enabled
  7. status.json + pid for ACTA; seen.json for dedupe; log file

FILES (all under CLD1):
  asts_trigger_watch.py            this script
  start_asts_trigger_watch.bat     wrapper (Task Scheduler / ACTA)
  google_credentials.json          service account (already used by the other bots)
  bot_status/asts_trigger_watch.status.json, .pid
  asts_trigger_watch.seen.json     dedupe memory (bounded)
  asts_trigger_watch.log           append-only

SHEET: "ASTS trigger watch"  1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18
  Sources: name | url | type(rss/edgar/x/html) | on/off | note | min kw (optional, per-source override;
           set 6+ on Google News search feeds, which match their own query on every item)
  Map:     term | kind | weight | note   ("case-sensitive" in note = exact case)
  Hits:    time ET | source | headline | link | kw score | llm score | direction | why | fired
  Rules:   rule | value | note   (poll interval, keyword threshold, llm threshold, llm daily cap,
                                  edgar keep, sheet id, fire cmd [optional], fire on [on/off, optional])

CREDITS: zero in the loop. LLM only on candidates (expect 5-20/day), hard daily cap from Rules.
SB: sub-only via claude -p; ANTHROPIC_API_KEY scrubbed from the child env. No API fallback.
"""
import os, re, sys, json, time, hashlib, logging, subprocess, argparse, threading
import urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------- config
BOT = "asts_trigger_watch"
TICKER = "ASTS"
SHEET_ID = "1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18"
CLD1 = os.environ.get("CLD1", os.path.dirname(os.path.abspath(__file__)))
CREDS = os.path.join(CLD1, "google_credentials.json")
STATUS_DIR = os.path.join(CLD1, "bot_status")
STATUS = os.path.join(STATUS_DIR, BOT + ".status.json")
PIDFILE = os.path.join(STATUS_DIR, BOT + ".pid")
SEEN = os.path.join(CLD1, BOT + ".seen.json")
LOG = os.path.join(CLD1, BOT + ".log")
UA = "Mozilla/5.0 (asts-trigger-watch; moranbenhur@gmail.com)"
CONFIG_TTL = 600          # re-read Sources/Map/Rules every 10 min
SEEN_MAX = 8000
ET_TZ_OFFSET = None       # computed from US DST each call

DEFAULT_RULES = {
    "poll interval": "2 min",
    "keyword threshold": "3",
    "llm threshold": "7",
    "llm daily cap": "50",
    "edgar keep": "8-K,424B,S-3,SC 13D,SC 13G,DEF 14A",
    "fire on": "off",
    "fire cmd": "",
}

logging.basicConfig(filename=LOG, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(BOT)
log.addHandler(logging.StreamHandler(sys.stdout))

# ---------------------------------------------------------------- time
def now_et():
    """US Eastern, DST-aware without pytz (2nd Sun Mar .. 1st Sun Nov)."""
    u = datetime.now(timezone.utc)
    y = u.year
    def nth_sunday(month, n):
        d = datetime(y, month, 1, 7, tzinfo=timezone.utc)   # 2am local ~ 7am UTC
        d += timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))
        return d
    dst = nth_sunday(3, 2) <= u < nth_sunday(11, 1)
    return u + timedelta(hours=-4 if dst else -5)

# ---------------------------------------------------------------- sheets
def sheets():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()

def read_tab(svc, tab):
    r = svc.values().get(spreadsheetId=SHEET_ID, range=f"{tab}!A1:Z500").execute()
    rows = r.get("values", [])
    return rows[1:] if rows else []

def load_config(svc):
    src = []
    for r in read_tab(svc, "Sources"):
        r += [""] * (6 - len(r))
        if r[3].strip().lower() == "on" and r[1].strip():
            try: mk = int(float(r[5])) if r[5].strip() else None      # col F "min kw": per-source override
            except ValueError: mk = None
            src.append({"name": r[0].strip(), "url": r[1].strip(), "type": r[2].strip().lower() or "rss", "min_kw": mk})
    mp = []
    for r in read_tab(svc, "Map"):
        r += [""] * (4 - len(r))
        if not r[0].strip(): continue
        try: w = int(float(r[2] or 1))
        except ValueError: w = 1
        mp.append({"term": r[0].strip(), "kind": r[1].strip(), "w": w, "cs": "case-sensitive" in r[3].lower()})
    rules = dict(DEFAULT_RULES)
    for r in read_tab(svc, "Rules"):
        if len(r) >= 2 and r[0].strip(): rules[r[0].strip().lower()] = r[1].strip()
    return src, mp, rules

def write_hit(svc, row):
    """Insert at row 2 of Hits (newest on top)."""
    sid = None
    meta = svc.get(spreadsheetId=SHEET_ID, fields="sheets(properties(sheetId,title))").execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == "Hits": sid = s["properties"]["sheetId"]
    if sid is None: raise RuntimeError("Hits tab missing")
    svc.batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [{"insertDimension": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2}, "inheritFromBefore": False}}]}).execute()
    svc.values().update(spreadsheetId=SHEET_ID, range="Hits!A2:I2", valueInputOption="USER_ENTERED",
                        body={"values": [row]}).execute()

# ---------------------------------------------------------------- feeds
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def parse_items(xml_bytes):
    root = ET.fromstring(xml_bytes)
    A = "{http://www.w3.org/2005/Atom}"
    out = []
    for it in root.iter("item"):
        out.append(((it.findtext("title") or "").strip(), (it.findtext("link") or "").strip(), (it.findtext("pubDate") or "").strip()))
    for e in root.iter(A + "entry"):
        ln = e.find(A + "link")
        out.append(((e.findtext(A + "title") or "").strip(), ln.get("href", "") if ln is not None else "", (e.findtext(A + "updated") or "").strip()))
    return out

def edgar_form(title):
    return title.split(" - ")[0].strip().upper()

# ---------------------------------------------------------------- match
def kw_match(text, mp):
    hits = []
    for m in mp:
        pat = r"(?<![\w&])" + re.escape(m["term"]) + r"(?![\w])"
        if re.search(pat, text, 0 if m["cs"] else re.I):
            hits.append(m)
    return hits

# ---------------------------------------------------------------- LLM (SB, sub-only)
LLM_PROMPT = """You score one news headline for its likely impact on {ticker} stock. Reply with JSON only.
Headline: {headline}
Source: {source}
Matched terms: {terms}
Rubric: 9-10 customer/competitor M&A, in-house move that removes a customer, guidance change, regulatory ruling, capital raise/dilution, launch failure.
7-8 analyst initiation/downgrade, major contract, executive change, launch success or delay.
4-6 conference, product PR, minor partnership, competitor routine news. 1-3 routine PR, unrelated, analysis/opinion piece.
Return: {{"score": <1-10>, "direction": "up"|"down"|"mixed", "why": "<= 20 words"}}"""

def llm_score(headline, source, terms):
    prompt = LLM_PROMPT.format(ticker=TICKER, headline=headline, source=source, terms=", ".join(terms))
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}   # SB: sub-only
    try:
        try:
            from failure_handler import claude_p_subprocess          # house wrapper, if present
            out = claude_p_subprocess(prompt, tools="", timeout=90)
        except ImportError:
            exe = "claude.cmd" if os.name == "nt" else "claude"
            out = subprocess.run([exe, "-p", prompt, "--model", "haiku"], capture_output=True, text=True, timeout=120, env=env).stdout
        m = re.search(r"\{.*?\}", out, re.S)
        j = json.loads(m.group(0)) if m else {}
        return int(j.get("score", 0)), str(j.get("direction", "")), str(j.get("why", ""))[:120]
    except Exception as e:
        log.warning(f"llm_score failed: {e}")
        return 0, "", "llm failed"

# ---------------------------------------------------------------- fire (fast lane)
def fire(rules, hit_row):
    cmd = rules.get("fire cmd", "").strip()
    if rules.get("fire on", "off").lower() != "on" or not cmd:
        return "pending"                       # logged, hook not armed
    try:
        subprocess.Popen(cmd, shell=True, cwd=CLD1)
        return "fired " + now_et().strftime("%H:%M")
    except Exception as e:
        log.error(f"fire failed: {e}"); return "fire failed"

# ---------------------------------------------------------------- status / pid
def write_status(**kw):
    os.makedirs(STATUS_DIR, exist_ok=True)
    kw.update({"bot": BOT, "pid": os.getpid(), "updated": datetime.now(timezone.utc).isoformat()})
    json.dump(kw, open(STATUS, "w"), indent=1)

def single_instance():
    os.makedirs(STATUS_DIR, exist_ok=True)
    if os.path.exists(PIDFILE):
        try:
            pid = int(open(PIDFILE).read().strip())
            if os.name == "nt":
                r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                alive = str(pid) in r.stdout
            else:
                os.kill(pid, 0); alive = True
        except Exception: alive = False
        if alive:
            log.info(f"already running as pid {pid}; exit"); sys.exit(0)
    open(PIDFILE, "w").write(str(os.getpid()))

# ---------------------------------------------------------------- one pass
def one_pass(svc, cfg, seen, state, args):
    src, mp, rules = cfg
    kw_thr = int(float(rules["keyword threshold"])); llm_thr = int(float(rules["llm threshold"]))
    cap = int(float(rules["llm daily cap"])); keep = [k.strip().upper() for k in rules["edgar keep"].split(",")]
    today = now_et().strftime("%Y-%m-%d")
    if state.get("day") != today: state.update({"day": today, "llm_calls": 0, "hits_today": 0})
    total = new = cands = 0; per_source = {}
    for s in src:
        try: items = parse_items(fetch(s["url"]))
        except Exception as e:
            per_source[s["name"]] = f"FAIL {type(e).__name__}"; log.warning(f"{s['name']}: {e}"); continue
        n_new = 0
        for title, link, _ in items:
            total += 1
            key = hashlib.sha1((title + "|" + link).encode()).hexdigest()
            if key in seen: continue
            seen[key] = int(time.time()); new += 1; n_new += 1
            if state.get("backfill"):        # first pass: remember, do not score
                continue
            is_edgar = s["type"] == "edgar"
            if is_edgar:
                form = edgar_form(title)
                if not any(form.startswith(k) for k in keep): continue
                terms = [f"EDGAR {form}"]; kw = 3
            else:
                hits = kw_match(title, mp)
                kw = sum(h["w"] for h in hits); terms = [h["term"] for h in hits]
                if kw < (s.get("min_kw") or kw_thr): continue
            cands += 1
            score, direction, why = 0, "", "llm cap reached"
            if state["llm_calls"] < cap:
                state["llm_calls"] += 1
                score, direction, why = llm_score(title, s["name"], terms)
            row = [now_et().strftime("%d %b %Y %H:%M"), s["name"], title[:200], link, kw, score or "", direction, why, ""]
            row[8] = fire(rules, row) if score >= llm_thr else "no"
            try: write_hit(svc, row); state["hits_today"] += 1
            except Exception as e: log.error(f"write_hit failed: {e}")
            log.info(f"HIT [{kw}/{score}] {s['name']} | {title[:90]} | {row[8]}")
        per_source[s["name"]] = f"{len(items)} items, {n_new} new"
    if state.pop("backfill", None): log.info(f"backfill: {new} headlines remembered, none scored")
    # bound seen
    if len(seen) > SEEN_MAX:
        for k in sorted(seen, key=seen.get)[: len(seen) - SEEN_MAX]: del seen[k]
    json.dump(seen, open(SEEN, "w"))
    write_status(ok=True, last_pass=now_et().strftime("%d %b %Y %H:%M ET"), headlines=total, new=new,
                 candidates=cands, llm_calls_today=state["llm_calls"], hits_today=state["hits_today"],
                 sources=per_source, fire_on=rules.get("fire on", "off"))
    log.info(f"pass: {total} headlines, {new} new, {cands} candidates, llm {state['llm_calls']}/{cap}")

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="single pass then exit")
    ap.add_argument("--no-backfill", action="store_true", help="score the existing backlog on first run (costs LLM calls)")
    args = ap.parse_args()
    single_instance()
    try: seen = json.load(open(SEEN))
    except Exception: seen = {}
    state = {"backfill": not seen and not args.no_backfill}
    svc = None; cfg = None; cfg_at = 0
    while True:
        try:
            if svc is None: svc = sheets()
            if time.time() - cfg_at > CONFIG_TTL:
                cfg = load_config(svc); cfg_at = time.time()
                log.info(f"config: {len(cfg[0])} sources on, {len(cfg[1])} map terms, rules {cfg[2]}")
            one_pass(svc, cfg, seen, state, args)
        except Exception as e:
            log.error(f"pass failed: {e}"); write_status(ok=False, error=str(e)); svc = None
        if args.once: break
        m = re.search(r"(\d+)", (cfg[2]["poll interval"] if cfg else "2"))
        time.sleep(60 * int(m.group(1)) if m else 120)

if __name__ == "__main__":
    main()
