# ASTS TRIGGER WATCH — bot (added 2026-09-10)

**PURPOSE**
Catch the trigger the moment it hits the wire, not when the price shows it. Watches customers, competitors, regulators and the company's own filings 24/7, every 2 min, and logs every candidate to the Hits tab. Nothing else in the stack runs off-hours or reads the sources where the HWM-type shocks came from (a Saturday Musk post, a 07:30 ET GE press release).

**WHAT IT IS**
A single-ticker source watcher, same family as Daily price-bot and Alert Agent. Python, stdlib polling, no LLM in the loop. Sub-only (SB) `claude -p` call only on a keyword hit. Runs on the PC beside pp_server as one always-on process.

**WHEN IT RUNS**
Continuous, 2-min loop, 24/7. Registry column G: `continuous`. ACTA starts it on its hourly tick if the pid is dead and column H is on. Not a Windows task of its own (BR sits with ACTA).

**WHAT IT READS (never edits)**
- Sheet "ASTS trigger watch" `1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18`: tabs Sources, Map, Rules (re-read every 10 min).
- The feeds listed in Sources with on/off = on. Optional col F "min kw" raises the keyword bar per source (set 7 on Google News search feeds, or turn them off; they match their own query on every item). Today: GlobeNewswire ×2, PRNewswire ×2, SEC EDGAR ASTS, Google News ×2. BusinessWire, FCC, X, Truth Social are off (phase 2).

**WHAT IT EDITS**
- Hits tab only, newest on top: time ET | source | headline | link | kw score | llm score | direction | why | fired.
- Own files: bot_status/asts_trigger_watch.status.json (+ .pid), asts_trigger_watch.seen.json, asts_trigger_watch.log.

**LOGIC PER PASS**
1. Pull every source; keep only headlines not in seen.json (hash of title+link).
2. EDGAR: keep forms in Rules "edgar keep" (8-K, 424B, S-3, SC 13D/G, DEF 14A); drop Form 4/144/3.
3. Others: sum Map weights of matched terms; below "keyword threshold" (3) = discarded.
4. Candidate → one SB call scores 1–10 + direction + why. Stops at "llm daily cap" (50); after that rows are written keyword-only.
5. Write the row to Hits.
6. llm score ≥ "llm threshold" (7) → if Rules "fire on" = on, run "fire cmd" (the fast lane: Trade Map re-score, then Trader). Default off; until armed the row shows fired = pending.
7. First ever run backfills: remembers the backlog, scores nothing.

**PIPELINE**
Hits tab is the 5th input to the Trade Map (with Macro Desk, Premarket, Ticker Desk, Trader log). Baseline: Trade Map's scheduled runs read Hits every time. Fast lane: step 6 above, phase 2.

**HARD RULES**
- Never trades, never edits another bot, never picks its own sources.
- Fixed source list and map; Moran edits the sheet, the bot obeys next reload.
- A pass with zero candidates is the normal answer. Never invents a hit.
- Credits: zero in the loop; LLM only on candidates, hard daily cap.

**STRATEGIES**
ACTA-gated (registry col H). FAH: per-source try/except, status.json every pass, no partial rows. SB: sub-only, ANTHROPIC_API_KEY scrubbed, no API fallback. Single-instance via pid file.

**FILES**
- C:\Users\rayon\Desktop\cld1\asts_trigger_watch.py
- C:\Users\rayon\Desktop\cld1\start_asts_trigger_watch.bat
- C:\Users\rayon\Desktop\cld1\google_credentials.json (service account; the sheet must be shared with it as editor)

**REGISTRY**: new row in "Agents - Bots - Actions list" — category Bot, schedule `continuous`, status off until first PC test passes.

**TEST DONE (2026-09-10, from the cloud)**: one pass, 7 feeds, 320 headlines, 173 keyword matches on the backlog; second pass 0 new (dedupe ok). Not yet tested: Sheets write, SB scoring, fire cmd.
