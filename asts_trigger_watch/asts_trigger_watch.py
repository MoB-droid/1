#!/usr/bin/env python3
"""
ASTS TRIGGER WATCH  -  bot (category Bot). Runs on the PC beside pp_server as one always-on process.

WHAT IT DOES (2-min loop, 24/7, no LLM in the loop):
  1. reads the sheet: Sources (on), Map (terms + weights), Rules (thresholds)        [re-read every 10 min]
  2. pulls only NEW headlines from each source (RSS / Atom / SEC EDGAR)
  3. keyword-matches every headline against the Map; EDGAR filings pass on form type
  4. candidate (kw score >= threshold)  ->  one SB (sub-only) Claude leg scores it 1-10
  5. writes the candidate to the Hits tab, newest on top (NOT), and re-reads it back (WUD)
  6. llm score >= fire threshold  ->  runs "fire cmd" from Rules (Trade Map -> Trader fast lane) if "fire on" = on
  7. status.json + pid for ACTA; seen.json for dedupe; pending.json for rows that could not be written; log file

HOUSE DEFAULTS APPLIED
  SB   every Claude leg via failure_handler.claude_call (Max sub only). Fallback (failure_handler missing):
       claude.cmd -p with ANTHROPIC_API_KEY scrubbed from the child env. Never the API.
  FAH  every external call wrapped (retry with backoff); unrecovered legs -> central FAILURE_LOG doc,
       alerts.queue.json, status.json unrecovered_legs[]; NO PARTIAL PUBLISH: a hit whose LLM leg is
       unrecovered is queued to pending.json, not written half-done.
  WUD  after each Hits write the row is re-read; not visible -> pending.json; pending drained first next pass.
  NOT  Hits rows inserted at row 2. Log file prepends.
  ACTA status.json every pass, pid file, col H is the master switch (ACTA stops the process when off).
  BR   Task Scheduler entry (see register_asts_trigger_watch.ps1): at-startup trigger, run whether logged on,
       restart x3, no idle stop, no time limit, DISABLED by default (ACTA enables from col H).
  NOTE the 2-min cadence is a sleep loop inside the process, by Moran's decision (SPA "no sleep-loop" waived).

FILES (all under CLD1 = C:\\Users\\rayon\\Desktop\\cld1)
  asts_trigger_watch.py, start_asts_trigger_watch.bat, register_asts_trigger_watch.ps1
  google_credentials.json   service account claude-agent@claude-autonomous-494610.iam.gserviceaccount.com
                            (the sheet MUST be shared with it as Editor)
  bot_status/asts_trigger_watch.status.json, bot_status/asts_trigger_watch.pid
  asts_trigger_watch.seen.json, asts_trigger_watch_pending.json, asts_trigger_watch.log, alerts.queue.json

SHEET "ASTS trigger watch"  1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18
  Sources: name | url | type(rss/edgar/x/html) | on/off | note | min kw (optional per-source override)
  Map:     term | kind | weight | note ("case-sensitive" in note = exact case)
  Hits:    time ET | source | headline | link | kw score | llm score | direction | why | fired
  Rules:   rule | value | note  (poll interval, keyword threshold, llm threshold, llm daily cap, edgar keep,
                                 sheet id, fire on, fire cmd)

CLI
  python asts_trigger_watch.py            loop (production)
  python asts_trigger_watch.py --once     one pass then exit (test)
  python asts_trigger_watch.py --once --no-backfill   first run: score the backlog too (costs LLM calls)
  python asts_trigger_watch.py --status   print status.json and exit
"""
import os, re, sys, json, time, hashlib, subprocess, argparse, traceback
import urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------- config
BOT = "asts trigger watch"
BOT_KEY = "asts_trigger_watch"
TICKER = "ASTS"
SHEET_ID = "1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18"
FAILURE_LOG_DOC = "19fmvc6eM2NFB6Kl-4yyuaezacxgJrj0--Uj9dXn_ZFw"     # central FAH failure log
CLD1 = os.environ.get("CLD1", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CLD1)
CREDS = os.path.join(CLD1, "google_credentials.json")
STATUS_DIR = os.path.join(CLD1, "bot_status")
STATUS = os.path.join(STATUS_DIR, BOT_KEY + ".status.json")
PIDFILE = os.path.join(STATUS_DIR, BOT_KEY + ".pid")
SEEN = os.path.join(CLD1, BOT_KEY + ".seen.json")
PENDING = os.path.join(CLD1, BOT_KEY + "_pending.json")
LOG = os.path.join(CLD1, BOT_KEY + ".log")
ALERTS = os.path.join(CLD1, "alerts.queue.json")
UA = "Mozilla/5.0 (asts-trigger-watch; moranbenhur@gmail.com)"
CONFIG_TTL = 600
SEEN_MAX = 8000
LOG_MAX_LINES = 5000
BACKOFF = [30, 60, 120, 300]          # FAH retry schedule for non-Claude external calls (Google, feeds)

DEFAULT_RULES = {
    "poll interval": "2 min", "keyword threshold": "3", "llm threshold": "7", "llm daily cap": "50",
    "edgar keep": "8-K,424B,S-3,SC 13D,SC 13G,DEF 14A", "fire on": "off", "fire cmd": "",
}

# ---------------------------------------------------------------- house modules (optional)
try:
    import failure_handler as FH          # FAH/SB: claude_call, write_status, alerts
except Exception:
    FH = None

# ---------------------------------------------------------------- log (NOT: prepend)
def log(msg, level="INFO"):
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z {level} {msg}"
    print(line, flush=True)
    try:
        old = open(LOG, encoding="utf-8").read().splitlines() if os.path.exists(LOG) else []
        open(LOG, "w", encoding="utf-8").write("\n".join([line] + old[:LOG_MAX_LINES]) + "\n")
    except Exception:
        pass

# ---------------------------------------------------------------- time
def now_et():
    u = datetime.now(timezone.utc); y = u.year
    def nth_sunday(month, n):
        d = datetime(y, month, 1, 7, tzinfo=timezone.utc)
        return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))
    dst = nth_sunday(3, 2) <= u < nth_sunday(11, 1)
    return u + timedelta(hours=-4 if dst else -5)

# ---------------------------------------------------------------- FAH wrapper for non-Claude externals
class Unrecovered(Exception): pass

def safe_call(leg, fn, *a, **kw):
    """Retry with backoff. Returns result or raises Unrecovered (caller decides: pending / skip)."""
    last = None
    for i, wait in enumerate([0] + BACKOFF):
        if wait: time.sleep(wait)
        try:
            r = fn(*a, **kw)
            if i: STATE["recovered"] += 1
            return r
        except Exception as e:
            last = e; log(f"{leg}: attempt {i+1} failed: {e}", "WARN")
    STATE["unrecovered"].append(leg)
    record_failure(leg, str(last), len(BACKOFF) + 1)
    raise Unrecovered(f"{leg}: {last}")

def record_failure(leg, err, attempts):
    """FAH #4 central failure log (newest on top) + #7 alert queue. Best effort."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"━━━ {stamp} — {BOT} — UNRECOVERED ━━━\nLEG: {leg}\nERROR: {err[:400]}\nATTEMPTS: {attempts}\nRESOLUTION: queued to pending / skipped this pass\n\n"
    try:
        docs().documents().batchUpdate(documentId=FAILURE_LOG_DOC, body={"requests": [
            {"insertText": {"location": {"index": 1}, "text": entry}}]}).execute()
    except Exception as e:
        log(f"failure-log doc write failed: {e}", "WARN")
    try:
        q = json.load(open(ALERTS)) if os.path.exists(ALERTS) else []
        q.append({"ts": stamp, "bot": BOT, "msg": f"{BOT}: unrecovered leg {leg}: {err[:120]}"})
        json.dump(q, open(ALERTS, "w"), indent=1)
    except Exception as e:
        log(f"alerts queue write failed: {e}", "WARN")

# ---------------------------------------------------------------- google
_svc = {}
def _creds(scopes):
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_file(CREDS, scopes=scopes)

def sheets():
    if "sheets" not in _svc:
        from googleapiclient.discovery import build
        _svc["sheets"] = build("sheets", "v4", credentials=_creds(["https://www.googleapis.com/auth/spreadsheets"]),
                               cache_discovery=False).spreadsheets()
    return _svc["sheets"]

def docs():
    if "docs" not in _svc:
        from googleapiclient.discovery import build
        _svc["docs"] = build("docs", "v1", credentials=_creds(["https://www.googleapis.com/auth/documents"]),
                             cache_discovery=False)
    return _svc["docs"]

def read_tab(tab):
    r = sheets().values().get(spreadsheetId=SHEET_ID, range=f"{tab}!A1:Z500").execute()
    rows = r.get("values", [])
    return rows[1:] if rows else []

def load_config():
    src = []
    for r in read_tab("Sources"):
        r += [""] * (6 - len(r))
        if r[3].strip().lower() == "on" and r[1].strip():
            try: mk = int(float(r[5])) if r[5].strip() else None
            except ValueError: mk = None
            src.append({"name": r[0].strip(), "url": r[1].strip(), "type": (r[2].strip().lower() or "rss"), "min_kw": mk})
    mp = []
    for r in read_tab("Map"):
        r += [""] * (4 - len(r))
        if not r[0].strip(): continue
        try: w = int(float(r[2] or 1))
        except ValueError: w = 1
        mp.append({"term": r[0].strip(), "kind": r[1].strip(), "w": w, "cs": "case-sensitive" in r[3].lower()})
    rules = dict(DEFAULT_RULES)
    for r in read_tab("Rules"):
        if len(r) >= 2 and r[0].strip(): rules[r[0].strip().lower()] = r[1].strip()
    return src, mp, rules

def hits_sheet_id():
    meta = sheets().get(spreadsheetId=SHEET_ID, fields="sheets(properties(sheetId,title))").execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == "Hits": return s["properties"]["sheetId"]
    raise RuntimeError("Hits tab missing")

def write_hit_verified(row):
    """NOT: insert at row 2. WUD: re-read row 2 and confirm the headline is there."""
    sid = hits_sheet_id()
    sheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [{"insertDimension": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2}, "inheritFromBefore": False}}]}).execute()
    sheets().values().update(spreadsheetId=SHEET_ID, range="Hits!A2:I2", valueInputOption="USER_ENTERED",
                             body={"values": [row]}).execute()
    back = sheets().values().get(spreadsheetId=SHEET_ID, range="Hits!A2:I2").execute().get("values", [[]])[0]
    if len(back) < 3 or back[2].strip() != str(row[2]).strip():
        raise RuntimeError("WUD verify failed: row 2 does not show the written headline")
    return True

# ---------------------------------------------------------------- feeds
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def parse_items(xml_bytes):
    root = ET.fromstring(xml_bytes); A = "{http://www.w3.org/2005/Atom}"; out = []
    for it in root.iter("item"):
        out.append(((it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()))
    for e in root.iter(A + "entry"):
        ln = e.find(A + "link")
        out.append(((e.findtext(A + "title") or "").strip(), ln.get("href", "") if ln is not None else ""))
    return out

def edgar_form(title):
    return title.split(" - ")[0].strip().upper()

def kw_match(text, mp):
    return [m for m in mp if re.search(r"(?<![\w&])" + re.escape(m["term"]) + r"(?![\w])", text, 0 if m["cs"] else re.I)]

# ---------------------------------------------------------------- Claude leg (SB via FAH)
LLM_PROMPT = """You score one news headline for its likely impact on {ticker} stock. Reply with JSON only, nothing else.
Headline: {headline}
Source: {source}
Matched terms: {terms}
Rubric: 9-10 customer/competitor M&A, in-house move that removes a customer, guidance change, regulatory ruling, capital raise/dilution, launch failure.
7-8 analyst initiation/downgrade, major contract, executive change, launch success or delay, presidential/government action on the sector.
4-6 conference, product PR, minor partnership, competitor routine news. 1-3 routine PR, unrelated, analysis/opinion piece.
Return: {{"score": <1-10>, "direction": "up"|"down"|"mixed", "why": "<= 20 words"}}"""

def llm_score(headline, source, terms):
    """Returns (score, direction, why) or raises Unrecovered."""
    prompt = LLM_PROMPT.format(ticker=TICKER, headline=headline, source=source, terms=", ".join(terms))
    out = None
    if FH is not None and hasattr(FH, "claude_call"):
        ok, result, err = FH.claude_call(prompt, leg=f"score:{headline[:40]}", tools="", via_stdin=True)
        if not ok:
            STATE["unrecovered"].append("llm_score"); record_failure("llm_score", str(err), 0)
            raise Unrecovered(f"llm_score: {err}")
        out = result
    else:                                              # fallback: sub-only, key scrubbed (SB hygiene)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        exe = "claude.cmd" if os.name == "nt" else "claude"
        def run():
            p = subprocess.run([exe, "-p", "--model", "haiku"], input=prompt, capture_output=True, text=True, timeout=120, env=env)
            if p.returncode != 0 or not p.stdout.strip(): raise RuntimeError((p.stderr or "empty output")[:200])
            return p.stdout
        out = safe_call("llm_score", run)
    m = re.search(r"\{.*?\}", out or "", re.S)
    j = json.loads(m.group(0)) if m else {}
    return int(j.get("score", 0)), str(j.get("direction", ""))[:8], str(j.get("why", ""))[:120]

# ---------------------------------------------------------------- fire (fast lane; off by default)
def fire(rules):
    cmd = rules.get("fire cmd", "").strip()
    if rules.get("fire on", "off").lower() != "on" or not cmd: return "pending"
    try:
        subprocess.Popen(cmd, shell=True, cwd=CLD1); return "fired " + now_et().strftime("%H:%M")
    except Exception as e:
        log(f"fire failed: {e}", "ERROR"); return "fire failed"

# ---------------------------------------------------------------- state / status
STATE = {"day": "", "llm_calls": 0, "hits_today": 0, "recovered": 0, "unrecovered": [], "success": 0}

def write_status(t0, **extra):
    os.makedirs(STATUS_DIR, exist_ok=True)
    s = {"bot": BOT, "timestamp": datetime.now(timezone.utc).isoformat(), "pid": os.getpid(),
         "success_count": STATE["success"], "recovered_count": STATE["recovered"],
         "unrecovered_legs": list(STATE["unrecovered"]), "total_duration": round(time.time() - t0, 1),
         "doc_written": extra.pop("doc_written", False), "llm_calls_today": STATE["llm_calls"],
         "hits_today": STATE["hits_today"], "day_et": STATE["day"]}
    s.update(extra)
    json.dump(s, open(STATUS, "w"), indent=1)

def single_instance():
    os.makedirs(STATUS_DIR, exist_ok=True)
    if os.path.exists(PIDFILE):
        try:
            pid = int(open(PIDFILE).read().strip())
            if os.name == "nt":
                alive = str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
            else:
                os.kill(pid, 0); alive = True
        except Exception:
            alive = False
        if alive: log(f"already running as pid {pid}; exit"); sys.exit(0)
    open(PIDFILE, "w").write(str(os.getpid()))

def load_json(p, default):
    try: return json.load(open(p))
    except Exception: return default

# ---------------------------------------------------------------- one pass
def one_pass(cfg, seen, pending, backfill):
    t0 = time.time(); STATE["unrecovered"] = []
    src, mp, rules = cfg
    kw_thr = int(float(rules["keyword threshold"])); llm_thr = int(float(rules["llm threshold"]))
    cap = int(float(rules["llm daily cap"])); keep = [k.strip().upper() for k in rules["edgar keep"].split(",")]
    today = now_et().strftime("%Y-%m-%d")
    if STATE["day"] != today: STATE.update({"day": today, "llm_calls": 0, "hits_today": 0})
    written = 0

    # WUD: drain pending rows first (oldest first)
    still = []
    for row in pending:
        try: safe_call("write_hit(pending)", write_hit_verified, row); written += 1; log(f"pending row written: {row[2][:70]}")
        except Unrecovered: still.append(row)
    pending[:] = still

    total = new = cands = 0; per_source = {}
    for s in src:
        try: items = safe_call(f"fetch:{s['name']}", lambda: parse_items(fetch(s["url"])))
        except Unrecovered: per_source[s["name"]] = "FAIL"; continue
        n_new = 0
        for title, link in items:
            total += 1
            key = hashlib.sha1((title + "|" + link).encode()).hexdigest()
            if key in seen: continue
            seen[key] = int(time.time()); new += 1; n_new += 1
            if backfill: continue                                   # first run: remember only
            if s["type"] == "edgar":
                form = edgar_form(title)
                if not any(form.startswith(k) for k in keep): continue
                terms, kw = [f"EDGAR {form}"], 3
            else:
                hits = kw_match(title, mp); kw = sum(h["w"] for h in hits); terms = [h["term"] for h in hits]
                if kw < (s.get("min_kw") or kw_thr): continue
            cands += 1
            row = [now_et().strftime("%d %b %Y %H:%M"), s["name"], title[:200], link, kw, "", "", "", "no"]
            if STATE["llm_calls"] >= cap:
                row[7] = "llm daily cap reached"
            else:
                STATE["llm_calls"] += 1
                try:
                    score, direction, why = llm_score(title, s["name"], terms)
                    row[5], row[6], row[7] = score, direction, why
                    if score >= llm_thr: row[8] = fire(rules)
                except Unrecovered:
                    pending.append(row); log(f"llm unrecovered -> pending: {title[:70]}", "WARN"); continue   # no partial publish
            try:
                safe_call("write_hit", write_hit_verified, row); written += 1; STATE["hits_today"] += 1; STATE["success"] += 1
                log(f"HIT [{kw}/{row[5]}] {s['name']} | {title[:90]} | {row[8]}")
            except Unrecovered:
                pending.append(row)
        per_source[s["name"]] = f"{len(items)} items, {n_new} new"
    if backfill: log(f"backfill: {new} headlines remembered, none scored")
    if len(seen) > SEEN_MAX:
        for k in sorted(seen, key=seen.get)[: len(seen) - SEEN_MAX]: del seen[k]
    json.dump(seen, open(SEEN, "w")); json.dump(pending, open(PENDING, "w"), indent=1)
    write_status(t0, doc_written=written > 0, last_pass_et=now_et().strftime("%d %b %Y %H:%M ET"), headlines=total,
                 new=new, candidates=cands, rows_written=written, pending=len(pending), sources=per_source,
                 fire_on=rules.get("fire on", "off"), llm_cap=cap)
    log(f"pass: {total} headlines, {new} new, {cands} candidates, {written} written, {len(pending)} pending, llm {STATE['llm_calls']}/{cap}")

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true"); ap.add_argument("--no-backfill", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.status:
        print(open(STATUS).read() if os.path.exists(STATUS) else "no status yet"); return
    single_instance()
    seen = load_json(SEEN, {}); pending = load_json(PENDING, [])
    backfill = (not seen) and (not args.no_backfill)
    cfg = None; cfg_at = 0
    log(f"start pid {os.getpid()} once={args.once} backfill={backfill} failure_handler={'yes' if FH else 'fallback'}")
    while True:
        try:
            if time.time() - cfg_at > CONFIG_TTL:
                cfg = safe_call("load_config", load_config); cfg_at = time.time()
                log(f"config: {len(cfg[0])} sources on, {len(cfg[1])} map terms, fire on={cfg[2].get('fire on')}")
            one_pass(cfg, seen, pending, backfill); backfill = False
        except Unrecovered as e:
            log(f"pass skipped: {e}", "ERROR"); write_status(time.time(), ok=False, error=str(e)); cfg_at = 0
        except Exception as e:
            log(f"pass crashed: {e}\n{traceback.format_exc()}", "ERROR"); write_status(time.time(), ok=False, error=str(e)); cfg_at = 0
        if args.once: break
        m = re.search(r"(\d+)", (cfg[2]["poll interval"] if cfg else "2"))
        time.sleep(60 * int(m.group(1)) if m else 120)

if __name__ == "__main__":
    main()
