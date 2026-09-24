# ASTS trigger watch — PRICE LEG update (14 Sep 2026). Install on the PC (cld1)

Talk to Moran in GO MO. Do every step; ask only where it says ASK.

## What changed
`asts_trigger_watch.py` now has a zero-credit PRICE LEG:
- every 2-min pass fetches the ASTS price from Yahoo (pre/regular/post) — one HTTP call, no Claude;
- reads the Trade Map's levels file `https://raw.githubusercontent.com/MoB-droid/1/asts-levels/asts_trigger_watch/levels.json` (the cloud map routines push it after every re-score: buy / sell / stop / size / position / mode);
- when the price touches a level in mode "limit", it writes a Hits row: source `price`, headline `PRICE touched buy 58.00: ASTS 57.90 (pre) - Trade Map <stamp>`, llm score 9 (no Claude call), once per level per day, and runs the fast lane like any 9+ hit;
- every Hits row now carries column J `price at hit` (the header is added automatically), so headlines and price can be correlated later.
New Rules rows (defaults inside the script if absent): `price on` = on, `price score` = 9, `price url` = the raw GitHub URL above.

## Steps
1. Pull branch `claude/trading-system-direction-mq4c8l` of MoB-droid/1 (or clone to %TEMP%\mob1) and copy `asts_trigger_watch.py`, `fire_lane.bat`, `fire_lane_prompt.md` into `C:\Users\rayon\Desktop\cld1`. Keep the old .py as `asts_trigger_watch.py.bak`.
2. Stop the running bot (kill the pid in `bot_status\asts_trigger_watch.pid`, or flip registry H to off and wait for ACTA), run `python asts_trigger_watch.py --once --no-backfill` and confirm in the log: `config: ... price on=on`, `Hits header: added column J 'price at hit'` (first time only), and `pass:` with no crash. Show Moran the status.json fields `last_price`, `price_session`, `levels_stamp`.
3. Rules tab: add rows `price on | on | zero-credit price leg`, `price score | 9 | Hits llm score written for a price touch`, `price url | https://raw.githubusercontent.com/MoB-droid/1/asts-levels/asts_trigger_watch/levels.json | Trade Map levels file`. Re-read to verify.
4. Demo: temporarily edit `price url` in Rules to a file that says buy = 999 (e.g. a gist), run `--once --no-backfill`, confirm one `PRICE touched buy 999.00` row lands in Hits with J filled, then delete that row and restore the url. Also delete the key `price:buy:999.00:<date>` from `asts_trigger_watch.seen.json`.
5. Restart the bot (registry H = on, or `Start-ScheduledTask -TaskName asts-trigger-watch`). Confirm status.json updates every 2 min with `last_price`.
6. FAST LANE (phase B, optional, ASK Moran first): set Rules `fire cmd` = `C:\Users\rayon\Desktop\cld1\fire_lane.bat` and `fire on` = on only after a manual test: run `fire_lane.bat` once by hand with a real 9+ row on top of Hits and read `fire_lane.log`. It runs one sub-only Claude session that re-scores the Trade Map and fires the cloud Trader. If the local CLI cannot use the Artifact tool, leave `fire on` = off; the cloud lane still picks up price rows within the hour.
7. Report in GO MO: last_price seen, levels_stamp read, demo row written and removed, fire on = on/off.

## Guardrails
- Never add an API key path. The price leg makes no Claude call at all.
- Never edit levels.json by hand on the PC; the map owns it.
- Never delete Hits rows except the one demo row you inserted.
