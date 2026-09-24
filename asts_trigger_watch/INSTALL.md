# ASTS trigger watch — install on the PC (cld1)

Do these in order. Each is one minute.

1. **Copy files** into `C:\Users\rayon\Desktop\cld1`:
   `asts_trigger_watch.py`, `start_asts_trigger_watch.bat`, `register_asts_trigger_watch.ps1`.

2. **Share the sheet** "ASTS trigger watch" (`1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18`) as **Editor** with
   `claude-agent@claude-autonomous-494610.iam.gserviceaccount.com`. Without it the Hits write fails WUD.

3. **Sheet tweaks** (Moran, by hand):
   - Sources: add header `min kw` in F1; put `7` in F for both Google News rows (the company name + ticker alone already score 6) (they match their own query on every item).
   - Map: add `initiates` (analyst, 2), `buy rating` (analyst, 2), `Trump` (person, 2), `moon` (keyword, 1).
   - Rules: rows `fire on` = `off`, `fire cmd` = (blank). Leave off until the fast lane is designed.

4. **Test pass** (console, no scheduler):
   ```
   cd C:\Users\rayon\Desktop\cld1
   python asts_trigger_watch.py --once
   ```
   First run = backfill: remembers the backlog, scores nothing, writes nothing. Check `bot_status\asts_trigger_watch.status.json` and the top of `asts_trigger_watch.log`.
   Second run: `python asts_trigger_watch.py --once` again. Anything new since = candidates -> scored -> Hits rows.
   To force scoring of the backlog for a demo: delete `asts_trigger_watch.seen.json`, then `--once --no-backfill` (costs up to the daily LLM cap).

5. **ACTA wiring** (`acta.py`):
   ```python
   TASK_NAME_MAP['ASTS trigger watch'] = 'asts-trigger-watch'
   BOT_SCRIPTS['asts_trigger_watch.py'] = 'ASTS trigger watch'
   ```
   BOT_MECHANISM: Windows task `asts-trigger-watch` (schtasks /ENABLE | /DISABLE). When col H = off and `bot_status\asts_trigger_watch.pid` is alive, ACTA Stop-Process's that pid.

6. **Register the task** (PowerShell, elevated): `.\register_asts_trigger_watch.ps1` -> created DISABLED.

7. **Registry row** (sheet "Agents - Bots - Actions list", tab gilion1, next free row):
   C=num | D=`Bot` | E=`ASTS trigger watch` | F=`2-min source watcher for ASTS: wires, EDGAR, competitor/partner headlines -> Hits tab of the ASTS trigger watch sheet; Trade Map reads it` | G=`continuous (2-min loop, 24/7; at-startup task)` | H=`off` | I=`Bots & Agents` | J=blank.
   Flip H to `on` after step 4 passes. ACTA enables the task on its next tick.

8. **Charter** — paste `CHARTER.md` into the Bots & Agents doc as a new bot section (not an AGENT CHARTERS block; it is a bot).

## What runs where
- Loop, feeds, keyword match, sheet write: Python on the PC, zero credits.
- Scoring: one sub-only Claude leg per candidate (`failure_handler.claude_call`), capped per day in Rules.
- Trade Map reads the Hits tab by public CSV on every scheduled run (already wired, tested 10 Sep).
- Fast lane (`fire on` / `fire cmd`): off. Phase 2.
