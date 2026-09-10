Install and test the "ASTS trigger watch" bot on this PC. Follow C:\Users\rayon\Desktop\cld1\CLAUDE.md house rules and talk to Moran in GO MO (≤30 words, numbered lists, y/n questions). Do every step yourself; stop and ask Moran only where this text says "ASK".

## What this bot is
A 2-min, 24/7 source watcher for ASTS. Python, no LLM in the loop. It pulls new headlines from wire/EDGAR/Google News feeds listed in a Google Sheet, keyword-matches them against a Map tab, scores keyword hits with one sub-only Claude leg (failure_handler.claude_call), and writes each candidate to the Hits tab of the sheet, newest on top. The Trade Map routines in the cloud already read that Hits tab by public CSV on every scheduled run (wired and tested 10 Sep 2026). The fast lane ("fire on" / "fire cmd" in the Rules tab) stays OFF; do not design or enable it.

Sheet "ASTS trigger watch": https://docs.google.com/spreadsheets/d/1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18 (tabs: Sources, Map, Hits, Rules). Owner moranbenhur@gmail.com. It is link-readable (view) so the cloud can curl it.

## Where the files are
Git repo MoB-droid/1, branch `claude/consul-definition-h8a19i`, folder `asts_trigger_watch/`:
- `asts_trigger_watch.py` — the bot (read its docstring first; it documents every house default it applies: SB, FAH, WUD, NOT, ACTA hooks, BR)
- `start_asts_trigger_watch.bat` — pythonw launcher
- `register_asts_trigger_watch.ps1` — Task Scheduler entry, created DISABLED
- `INSTALL.md`, `CHARTER.md` — install steps and the doc section

If cld1 is not a checkout of that repo, clone it to a temp folder: `git clone -b claude/consul-definition-h8a19i https://github.com/MoB-droid/1.git %TEMP%\mob1` and copy the three runtime files (.py, .bat, .ps1) into `C:\Users\rayon\Desktop\cld1`. Do not copy the .md files into cld1.

## Steps (do in order; report each in one line)

1. COPY the three runtime files into cld1. Confirm `failure_handler.py`, `google_credentials.json`, `bot_status\` exist in cld1 (they do for the other bots). Check `python -c "import googleapiclient, google.oauth2"` works in the same Python the other bots use; if not, `pip install google-api-python-client google-auth`.

2. READ `failure_handler.py` and confirm the signature the bot calls: `claude_call(prompt, leg=..., tools="", via_stdin=True)` returning `(ok, result, err)`. If the real signature differs, adapt `llm_score()` in the bot to the real one (keep it sub-only; never add an API key path). Confirm the bot's `record_failure()` writes the same FAILURE_LOG doc format the other bots use (doc id 19fmvc6eM2NFB6Kl-4yyuaezacxgJrj0--Uj9dXn_ZFw, newest on top); if failure_handler already exposes a helper for that, use it instead.

3. SHEET ACCESS. Confirm the service account email in google_credentials.json (expected claude-agent@claude-autonomous-494610.iam.gserviceaccount.com). Test read: a 5-line python snippet reading `Sources!A1:F3` with the service account. If it fails with 403, ASK Moran to share the sheet with that email as Editor, then retry.

4. SHEET TWEAKS via the Sheets API (service account), then re-read to verify:
   - Sources: set F1 = `min kw`; set F = 7 on the two Google News rows (names start "Google News").
   - Map: append rows `initiates | analyst | 2`, `buy rating | analyst | 2`, `Trump | person | 2`, `moon | keyword | 1` (skip any that already exist).
   - Rules: ensure rows `fire on | off` and `fire cmd | (blank)` exist. Do not change other rules.

5. TEST PASS 1 (backfill): `cd C:\Users\rayon\Desktop\cld1 && python asts_trigger_watch.py --once`. Expected: log says "backfill: N headlines remembered, none scored", status.json written, Hits tab unchanged, no LLM calls. Show Moran the first 5 log lines.

6. TEST PASS 2 (live): run `--once` again. Expected: 0–3 new headlines, candidates scored via claude_call, rows inserted at Hits row 2 and verified (WUD), status.json `doc_written` true if any row was written. If nothing new arrived (normal at quiet hours), force a demo: delete `asts_trigger_watch.seen.json`, set Rules `llm daily cap` to 5 temporarily, run `--once --no-backfill`, confirm 5 rows land in Hits with scores, then set the cap back to 50 and delete the 5 demo rows from Hits (leave the header). Show Moran the rows.

7. ACTA WIRING in `acta.py` (read it first, match its existing patterns exactly):
   - `TASK_NAME_MAP['ASTS trigger watch'] = 'asts-trigger-watch'`
   - `BOT_SCRIPTS['asts_trigger_watch.py'] = 'ASTS trigger watch'`
   - Column-G schedule format: add support for `continuous` if `read_registry`/`sync_trigger` would choke on it: treat it as "task enabled = process should be alive". If ACTA has a reconcile loop that Stop-Process's bots with col H = off, make sure it finds this bot's pid at `bot_status\asts_trigger_watch.pid`. Keep the edit minimal; run ACTA's own self-test or a dry `python acta.py --help`/import check afterwards.

8. TASK SCHEDULER: run `register_asts_trigger_watch.ps1` in an elevated PowerShell. Verify with `Get-ScheduledTask -TaskName asts-trigger-watch` that it exists and is Disabled. Do NOT enable it.

9. REGISTRY ROW in sheet "Agents - Bots - Actions list" (id 1-N_aldKfjfC3jnO8qyXQVUU3q4HUQyq2_PasJX3YV7Y, tab גיליון1, data from row 8): find the next free row and write
   C = next num | D = `Bot` | E = `ASTS trigger watch` | F = `2-min source watcher for ASTS: wires, SEC EDGAR, competitor/partner headlines → Hits tab of the "ASTS trigger watch" sheet; the Trade Map reads it every run. No LLM in the loop; one sub-only leg per keyword hit, capped daily.` | G = `continuous (2-min loop, 24/7; at-startup task asts-trigger-watch)` | H = `off` | I = `Bots & Agents` | J = blank.

10. CHARTER: insert the content of `CHARTER.md` (from the repo folder) into the "Bots & Agents" doc (id 16zKRBZpMc27fs94kyOUPbTBTgNWUd8KSxEaqllUXrRA) as a new bot section, formatted like the neighbouring bot sections (bold title, PURPOSE / WHEN / WHERE / EDITS / READS / LOGIC / STRATEGIES / FILES / REFERENCE, ending with the ━━━ end ━━━ line). It is a bot, NOT an agent: do not add a `=== CHARTER: ... ===` block and do not touch sync_charters.EXPECTED. Add a CHANGELOG line at the top of the doc's changelog: "2026-09-10 — ASTS trigger watch bot added (2-min source watcher → Hits tab → Trade Map input #5)."

11. GO LIVE — ASK Moran: "Tests passed. Flip registry H to on so ACTA starts the task? y/n". If y: set H = on, then either wait for ACTA's next hourly tick or start it now with `Start-ScheduledTask -TaskName asts-trigger-watch`. Confirm `bot_status\asts_trigger_watch.pid` is alive and status.json updates every 2 min.

12. REPORT to Moran in GO MO, numbered: what passed, what was changed in acta.py, registry row number, task state, and the one number that matters: LLM calls today from status.json.

## Guardrails
- Never add an Anthropic API key path. Sub-only.
- Never enable the fast lane (`fire on` stays off).
- Never delete or rewrite existing Hits rows except the demo rows you yourself inserted in step 6.
- Any write to a tracked sheet/doc: re-read and verify (WUD).
- If anything in the bot conflicts with a house rule you find in cld1 (failure_handler contract, ACTA mechanics), adapt the bot to the house, not the other way round, and say what you changed.
