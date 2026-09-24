#!/usr/bin/env python3
"""
ASTS TRIGGER WATCH  -  bot (category Bot). Runs on the PC beside pp_server as one always-on process.

WHAT IT DOES (2-min loop, 24/7, no LLM in the loop):
  1. reads the sheet: Sources (on), Map (terms + weights), Rules (thresholds)        [re-read every 10 min]
  2. pulls only NEW headlines from each source (RSS / Atom / SEC EDGAR)
  3. keyword-matches every headline against the Map; EDGAR filings pass on form type
  4. candidates (kw score >= threshold) are queued and scored in BATCHES - one SB (sub-only) Claude leg
     scores up to 20 headlines 1-10 (was one leg per headline, which exhausted the subscription)
  5. writes the candidate to the Hits tab, newest on top (NOT), and re-reads it back (WUD)
  6. llm score >= fire threshold  ->  runs "fire cmd" from Rules (Trade Map -> Trader fast lane) if "fire on" = on
  7. status.json + pid for ACTA; seen.json for dedupe; pending.json for rows that could not be written; log file
  8. PRICE LEG (added 14 Sep 2026, zero credits): every pass fetches the ASTS price from Yahoo (one HTTP call) and
     reads the Trade Map's levels file (levels.json, published by the map routines to GitHub). When the price
     touches a "limit" level (buy / sell / stop) it writes a Hits row with source "price", llm score 9 and no
     Claude call, once per level per day, and runs the fast lane like any 9+ hit. Every Hits row also gets
     column J "price at hit" so headlines and price can be correlated later.

HOUSE DEFAULTS APPLIED
  SB   every Claude leg via failure_handler.claude_call (Max sub only). Fallback (failure_handler missing):
       claude.cmd -p with ANTHROPIC_API_KEY scrubbed from the child env. Never the API.
  FAH  every external call wrapped (retry with backoff); unrecovered legs -> central FAILURE_LOG doc,
       alerts.queue.json, status.json unrecovered_legs[]; NO PARTIAL PUBLISH: a hit whose LLM leg is
       unrecovered is queued to pending.json, not written half-done, and is RE-SCORED on the next pass -
       an unscored row is never published blank (it could never fire). Dropped after 48h unscored.
       Watchdog: no successful score for 6h with rows waiting -> unrecovered leg "llm_score:stale".
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
  Hits:    time ET | source | headline | link | kw score | llm score | direction | why | fired | price at hit
  Rules:   rule | value | note  (poll interval, keyword threshold, llm threshold, llm daily cap, edgar keep,
                                 sheet id, fire on, fire cmd, price on, price url, price score)

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
LLMSTATE = os.path.join(CLD1, BOT_KEY + ".llm.json")   # last successful score, survives restarts
ALERTS = os.path.join(CLD1, "alerts.queue.json")
UA = "Mozilla/5.0 (asts-trigger-watch; moranbenhur@gmail.com)"
CONFIG_TTL = 600
SEEN_MAX = 8000
BATCH_MAX = 20                        # headlines scored in one Claude leg (was one leg per headline)
PENDING_MAX_HOURS = 48                # an unscored row older than this is dropped, not published blank
LLM_STALE_HOURS = 6                   # no successful score in this long, with candidates waiting -> alert
LOG_MAX_LINES = 5000
BACKOFF = [30, 60, 120, 300]          # FAH retry schedule for non-Claude external calls (Google, feeds)

DEFAULT_RULES = {
    "poll interval": "2 min", "keyword threshold": "3", "llm threshold": "7", "llm daily cap": "50",
    "edgar keep": "8-K,424B,S-3,SC 13D,SC 13G,DEF 14A", "fire on": "off", "fire cmd": "",
    "price on": "on", "price score": "9",
    "price url": "https://raw.githubusercontent.com/MoB-droid/1/asts-levels/asts_trigger_watch/levels.json",
    "recycled days": "2", "claim memory days": "30",
}
PRICE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=1d&interval=1m&includePrePost=true"
HITS_COLS = 10                         # A..J ; J = price at hit

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
    row = list(row) + [""] * (HITS_COLS - len(row))
    if len(row) >= HITS_COLS and row[HITS_COLS - 1] in ("", None) and STATE.get("last_price") is not None:
        row[HITS_COLS - 1] = STATE["last_price"]            # price at hit, for headline/price correlation
    sheets().values().update(spreadsheetId=SHEET_ID, range="Hits!A2:J2", valueInputOption="USER_ENTERED",
                             body={"values": [row]}).execute()
    back = sheets().values().get(spreadsheetId=SHEET_ID, range="Hits!A2:J2").execute().get("values", [[]])[0]
    if len(back) < 3 or back[2].strip() != str(row[2]).strip():
        raise RuntimeError("WUD verify failed: row 2 does not show the written headline")
    return True

# ---------------------------------------------------------------- feeds
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def parse_items(xml_bytes):
    """(title, link, published) - published is a UTC datetime or None."""
    root = ET.fromstring(xml_bytes); A = "{http://www.w3.org/2005/Atom}"; out = []
    for it in root.iter("item"):
        out.append(((it.findtext("title") or "").strip(), (it.findtext("link") or "").strip(),
                    parse_date(it.findtext("pubDate") or it.findtext("date") or "")))
    for e in root.iter(A + "entry"):
        ln = e.find(A + "link")
        out.append(((e.findtext(A + "title") or "").strip(), ln.get("href", "") if ln is not None else "",
                    parse_date(e.findtext(A + "published") or e.findtext(A + "updated") or "")))
    return out

def parse_date(s):
    """RSS/Atom date -> aware UTC datetime, or None when absent or unparseable."""
    s = (s or "").strip()
    if not s: return None
    try:
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d is None: return None
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

OUTLET_TAIL = re.compile(r"\s+[-\u2013\u2014|]\s+[^-\u2013\u2014|]{1,40}\s*$")

def strip_outlet(title):
    """Drop the trailing ' - Outlet' byline: MarketBeat and marketbeat.com carry the same story."""
    t = OUTLET_TAIL.sub("", title.strip())
    return t if len(t) >= 15 else title.strip()

def claim_key(title):
    """A story's identity, so the same event re-listed by another outlet is one claim."""
    words = re.findall(r"[a-z0-9]+", strip_outlet(title).lower())
    stop = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "is", "as", "at", "by", "its", "it",
            "with", "from", "that", "this", "says", "said", "after", "over", "new", "inc", "nasdaq", "stock"}
    core = [w for w in words if w not in stop and len(w) > 2][:8]
    return "claim:" + hashlib.sha1(" ".join(core).encode()).hexdigest()[:16]

def recycled_reason(title, published, seen, rules):
    """Why this item must not score. None means it is genuinely new."""
    try: max_age = float(rules.get("recycled days", "2"))
    except ValueError: max_age = 2.0
    try: memory = float(rules.get("claim memory days", "30"))
    except ValueError: memory = 30.0
    if published is not None:
        age = (datetime.now(timezone.utc) - published).total_seconds() / 86400.0
        if age > max_age:
            return f"recycled: first published {published.strftime('%d %b %Y')}, {age:.0f} days old"
    ck = claim_key(title)
    first = seen.get(ck)
    if first and (time.time() - first) <= memory * 86400:
        when = datetime.fromtimestamp(first, timezone.utc).strftime("%d %b %Y")
        return f"recycled: same claim already scored {when}"
    seen[ck] = seen.get(ck) or int(time.time())
    return None

def edgar_form(title):
    return title.split(" - ")[0].strip().upper()

def kw_match(text, mp):
    return [m for m in mp if re.search(r"(?<![\w&])" + re.escape(m["term"]) + r"(?![\w])", text, 0 if m["cs"] else re.I)]

# ---------------------------------------------------------------- Claude leg (SB via FAH)
LLM_BATCH_PROMPT = """You score news headlines for their likely impact on {ticker} stock. Reply with JSON only, nothing else.
Rubric: 9-10 customer/competitor M&A, in-house move that removes a customer, guidance change, regulatory ruling, capital raise/dilution, launch failure.
7-8 analyst initiation/downgrade, major contract, executive change, launch success or delay, presidential/government action on the sector.
4-6 conference, product PR, minor partnership, competitor routine news. 1-3 routine PR, unrelated, analysis/opinion piece.
Headlines:
{lines}
Return: {{"scores": [{{"n": <headline number>, "score": <1-10>, "direction": "up"|"down"|"mixed", "why": "<= 20 words"}}]}}
One entry per numbered headline, same numbers, nothing else."""

def llm_run(prompt, leg):
    """One Claude leg (SB: Max sub only, never the API). Returns raw text or raises Unrecovered."""
    if FH is not None and hasattr(FH, "claude_call"):
        ok, result, err = FH.claude_call(prompt, leg=leg, tools="", via_stdin=True)
        if not ok:
            STATE["unrecovered"].append("llm_score"); record_failure("llm_score", str(err), 0)
            raise Unrecovered(f"llm_score: {err}")
        return result
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}   # SB hygiene
    exe = "claude.cmd" if os.name == "nt" else "claude"
    def run():
        p = subprocess.run([exe, "-p", "--model", "haiku"], input=prompt, capture_output=True, text=True, timeout=180, env=env)
        if p.returncode != 0 or not p.stdout.strip(): raise RuntimeError((p.stderr or "empty output")[:200])
        return p.stdout
    return safe_call("llm_score", run)

def llm_score_batch(items):
    """One Claude call for up to BATCH_MAX candidates (was one call per headline, which burned the sub).
    items: [{'title','source','terms'}]. Returns {index: (score, direction, why)}; a missing index stays unscored."""
    lines = "\n".join("%d. %s  [source: %s; terms: %s]" % (i + 1, it["title"], it["source"], ", ".join(it["terms"]))
                      for i, it in enumerate(items))
    out = llm_run(LLM_BATCH_PROMPT.format(ticker=TICKER, lines=lines), leg="score:%d headlines" % len(items))
    STATE["llm_calls"] += 1
    m = re.search(r"\{.*\}", out or "", re.S)
    j = json.loads(m.group(0)) if m else {}
    scored = {}
    for e in (j.get("scores") or []):
        try: n = int(e.get("n", 0)) - 1
        except (TypeError, ValueError): continue
        if 0 <= n < len(items):
            scored[n] = (int(e.get("score", 0)), str(e.get("direction", ""))[:8], str(e.get("why", ""))[:120])
    if scored:
        STATE["llm_ok_at"] = time.time()
        try: json.dump({"llm_ok_at": STATE["llm_ok_at"]}, open(LLMSTATE, "w"))
        except Exception: pass
    return scored

def pending_age_h(row):
    """Hours since the row was first built, from its own ET stamp. Unparseable -> 0 (keep it)."""
    try: t = datetime.strptime(str(row[0]), "%d %b %Y %H:%M")
    except (ValueError, TypeError): return 0.0
    return (now_et().replace(tzinfo=None) - t).total_seconds() / 3600.0

def llm_watchdog(waiting):
    """The scorer dying quietly is what breaks the fire lane. Alert once every LLM_STALE_HOURS."""
    if not waiting: return
    last = STATE.get("llm_ok_at") or 0
    if last and time.time() - last < LLM_STALE_HOURS * 3600: return
    if time.time() - (STATE.get("stale_alert_at") or 0) < LLM_STALE_HOURS * 3600: return
    STATE["stale_alert_at"] = time.time()
    when = datetime.fromtimestamp(last, timezone.utc).strftime("%d %b %Y %H:%M UTC") if last else "never"
    record_failure("llm_score:stale", f"no headline scored since {when}; {waiting} rows waiting unscored", 0)
    log(f"WATCHDOG: no successful score since {when}, {waiting} rows waiting", "ERROR")

# ---------------------------------------------------------------- price leg (zero credits)
def ensure_price_header():
    """Once per config reload: make sure Hits!J1 says 'price at hit' (adds the column, touches nothing else)."""
    try:
        h = sheets().values().get(spreadsheetId=SHEET_ID, range="Hits!A1:J1").execute().get("values", [[]])[0]
        if len(h) < HITS_COLS or not h[HITS_COLS - 1].strip():
            sheets().values().update(spreadsheetId=SHEET_ID, range="Hits!J1", valueInputOption="USER_ENTERED",
                                     body={"values": [["price at hit"]]}).execute()
            log("Hits header: added column J 'price at hit'")
    except Exception as e:
        log(f"price header check failed: {e}", "WARN")

def fetch_price(ticker):
    """Latest ASTS print from Yahoo, pre/regular/post. Returns (price, session) or raises."""
    req = urllib.request.Request(PRICE_URL.format(t=ticker), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        j = json.load(r)["chart"]["result"][0]
    ts = j.get("timestamp") or []; closes = j["indicators"]["quote"][0].get("close") or []
    bars = [(t, c) for t, c in zip(ts, closes) if c is not None]
    meta = j.get("meta", {})
    if bars:
        t, c = bars[-1]
        tp = meta.get("currentTradingPeriod", {})
        ses = "regular"
        for name in ("pre", "post"):
            p = tp.get(name, {})
            if p and p.get("start", 0) <= t < p.get("end", 0): ses = name
        return round(float(c), 2), ses
    return round(float(meta["regularMarketPrice"]), 2), "last"

def fetch_levels(url):
    """levels.json written by the Trade Map: {ticker, stamp, mode, buy, sell, stop, size, position, note}."""
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"t={int(time.time())}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def _num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def price_leg(rules, seen):
    """One price check per pass. Writes a Hits row when the price touches a limit level, once per level per day."""
    if rules.get("price on", "on").lower() != "on": return []
    try:
        price, ses = safe_call("price:fetch", fetch_price, TICKER)
    except Unrecovered:
        return []
    STATE["last_price"] = price; STATE["last_price_session"] = ses
    try:
        lv = safe_call("price:levels", fetch_levels, rules["price url"])
    except Unrecovered:
        return []
    STATE["levels_stamp"] = lv.get("stamp", "")
    if str(lv.get("ticker", TICKER)).upper() != TICKER: return []
    if str(lv.get("mode", "limit")).lower() != "limit": return []          # the map said "close only" today
    holding = str(lv.get("position", "flat")).lower() != "flat"
    rows = []
    checks = [("buy", _num(lv.get("buy")), lambda p, x: p <= x, "up", not holding or lv.get("allow_add")),
              ("sell", _num(lv.get("sell")), lambda p, x: p >= x, "down", holding),
              ("stop", _num(lv.get("stop")), lambda p, x: p <= x, "down", holding)]
    day = now_et().strftime("%Y-%m-%d"); score = int(float(rules.get("price score", "9")))
    for side, level, hit, direction, applies in checks:
        if level is None or not applies or not hit(price, level): continue
        key = f"price:{side}:{level:.2f}:{day}"
        if key in seen: continue
        seen[key] = int(time.time())
        head = f"PRICE touched {side} {level:.2f}: {TICKER} {price:.2f} ({ses}) - Trade Map {lv.get('stamp', '')}"
        why = f"price leg: {side} level from the Trade Map daily plan, size {lv.get('size', '')}, position {lv.get('position', 'flat')}"
        rows.append([now_et().strftime("%d %b %Y %H:%M"), "price", head[:200], rules["price url"], 0, score, direction, why[:120], "no", price])
    return rows

# ---------------------------------------------------------------- fire (fast lane; off by default)
def fire(rules):
    cmd = rules.get("fire cmd", "").strip()
    if rules.get("fire on", "off").lower() != "on" or not cmd: return "pending"
    try:
        subprocess.Popen(cmd, shell=True, cwd=CLD1); return "fired " + now_et().strftime("%H:%M")
    except Exception as e:
        log(f"fire failed: {e}", "ERROR"); return "fire failed"

# ---------------------------------------------------------------- state / status
STATE = {"day": "", "llm_calls": 0, "hits_today": 0, "recovered": 0, "unrecovered": [], "success": 0,
         "llm_ok_at": 0, "stale_alert_at": 0}

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
    queue = []                                                # candidates waiting for a score

    # WUD: drain pending first. A row that never got its score is re-queued, never published blank.
    still = []
    for row in pending:
        if row[5] in ("", None):
            if pending_age_h(row) > PENDING_MAX_HOURS:
                log(f"pending dropped, unscored for {PENDING_MAX_HOURS}h: {str(row[2])[:70]}", "WARN"); continue
            queue.append({"row": row, "title": str(row[2]), "source": str(row[1]), "terms": []})
            continue
        try: safe_call("write_hit(pending)", write_hit_verified, row); written += 1; log(f"pending row written: {row[2][:70]}")
        except Unrecovered: still.append(row)
    pending[:] = still

    total = new = cands = 0; per_source = {}
    for row in price_leg(rules, seen):                        # zero-credit price touches, scored by rule
        cands += 1
        if row[5] >= llm_thr: row[8] = fire(rules)
        try:
            safe_call("write_hit(price)", write_hit_verified, row); written += 1; STATE["hits_today"] += 1; STATE["success"] += 1
            log(f"PRICE HIT {row[2][:90]} | {row[8]}")
        except Unrecovered:
            pending.append(row)
    for s_ in src:
        try: items = safe_call(f"fetch:{s_['name']}", lambda: parse_items(fetch(s_["url"])))
        except Unrecovered: per_source[s_["name"]] = "FAIL"; continue
        n_new = 0
        for title, link, published in items:
            total += 1
            key = hashlib.sha1((strip_outlet(title) + "|" + link).encode()).hexdigest()
            if key in seen: continue
            seen[key] = int(time.time()); new += 1; n_new += 1
            if backfill: continue                                   # first run: remember only
            if s_["type"] == "edgar":
                form = edgar_form(title)
                if not any(form.startswith(k) for k in keep): continue
                terms, kw = [f"EDGAR {form}"], 3
            else:
                hits = kw_match(title, mp); kw = sum(h["w"] for h in hits); terms = [h["term"] for h in hits]
                if kw < (s_.get("min_kw") or kw_thr): continue
            cands += 1
            row = [now_et().strftime("%d %b %Y %H:%M"), s_["name"], title[:200], link, kw, "", "", "", "no"]
            stale = recycled_reason(title, published, seen, rules) if s_["type"] != "edgar" else None
            if stale:                                               # zero Claude calls, can never reach the fire threshold
                row[5], row[6], row[7], row[8] = 1, "recycled", stale[:120], "recycled"
                STATE["recycled_today"] = STATE.get("recycled_today", 0) + 1
                try:
                    safe_call("write_hit(recycled)", write_hit_verified, row); written += 1; STATE["hits_today"] += 1
                    log(f"RECYCLED [{kw}] {s_['name']} | {title[:80]} | {stale}")
                except Unrecovered:
                    pending.append(row)
                continue
            queue.append({"row": row, "title": title, "source": s_["name"], "terms": terms})
        per_source[s_["name"]] = f"{len(items)} items, {n_new} new"

    # scoring: one Claude leg per batch of candidates, not one per headline
    waiting = len(queue)
    while queue:
        if STATE["llm_calls"] >= cap:
            for q in queue: q["row"][7] = "llm daily cap reached"; pending.append(q["row"])
            log(f"llm daily cap {cap} reached: {len(queue)} rows held unscored in pending", "WARN"); queue = []
            break
        batch, queue = queue[:BATCH_MAX], queue[BATCH_MAX:]
        try:
            scored = llm_score_batch(batch)
        except Unrecovered:                                    # scorer down: hold everything, publish nothing blank
            for q in batch + queue: pending.append(q["row"])
            log(f"llm unrecovered: {len(batch) + len(queue)} rows held in pending, none written", "WARN")
            queue = []
            break
        for i, q in enumerate(batch):
            row = q["row"]
            if i not in scored:
                pending.append(row); log(f"no score returned -> pending: {q['title'][:70]}", "WARN"); continue
            row[5], row[6], row[7] = scored[i]
            if row[5] >= llm_thr: row[8] = fire(rules)
            try:
                safe_call("write_hit", write_hit_verified, row); written += 1; STATE["hits_today"] += 1; STATE["success"] += 1
                log(f"HIT [{row[4]}/{row[5]}] {q['source']} | {q['title'][:90]} | {row[8]}")
            except Unrecovered:
                pending.append(row)
    llm_watchdog(len([r for r in pending if r[5] in ("", None)]) if waiting or pending else 0)

    if backfill: log(f"backfill: {new} headlines remembered, none scored")
    if len(seen) > SEEN_MAX:
        for k in sorted(seen, key=seen.get)[: len(seen) - SEEN_MAX]: del seen[k]
    json.dump(seen, open(SEEN, "w")); json.dump(pending, open(PENDING, "w"), indent=1)
    unscored = len([r for r in pending if r[5] in ("", None)])
    write_status(t0, doc_written=written > 0, last_pass_et=now_et().strftime("%d %b %Y %H:%M ET"), headlines=total,
                 new=new, candidates=cands, rows_written=written, pending=len(pending), pending_unscored=unscored,
                 sources=per_source, fire_on=rules.get("fire on", "off"), llm_cap=cap, last_price=STATE.get("last_price"),
                 price_session=STATE.get("last_price_session"), levels_stamp=STATE.get("levels_stamp"),
                 last_llm_ok=(datetime.fromtimestamp(STATE["llm_ok_at"], timezone.utc).isoformat()
                              if STATE.get("llm_ok_at") else None))
    log(f"pass: {total} headlines, {new} new, {cands} candidates, {written} written, "
        f"{len(pending)} pending ({unscored} unscored), llm calls {STATE['llm_calls']}/{cap}")

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
    STATE["llm_ok_at"] = load_json(LLMSTATE, {}).get("llm_ok_at", 0)
    backfill = (not seen) and (not args.no_backfill)
    cfg = None; cfg_at = 0
    log(f"start pid {os.getpid()} once={args.once} backfill={backfill} failure_handler={'yes' if FH else 'fallback'}")
    while True:
        try:
            if time.time() - cfg_at > CONFIG_TTL:
                cfg = safe_call("load_config", load_config); cfg_at = time.time()
                log(f"config: {len(cfg[0])} sources on, {len(cfg[1])} map terms, fire on={cfg[2].get('fire on')}, price on={cfg[2].get('price on')}")
                ensure_price_header()
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
