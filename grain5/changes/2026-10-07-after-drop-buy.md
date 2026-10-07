# 2026-10-07 · Rule 3.1.20 After-drop buy

Guidebook change (Grain 5 rule 4.3.1, step 5: the spec note in the repo).
From Trade Fixer Sep 2026, card 3, refined in chat and approved by Moran.

1. 3.1.20 added. Trigger: ASTS closes down 7% or more (or more than twice its
   20-session average daily move, when that is larger) on news not about ASTS.
   The next session's Buy is that close, a limit, when all six checks pass:
   1. News: no ASTS press release or filing that day.
   2. Roadmap: no high-impact event in the next 5 trading days.
   3. Volume: at least 1.5x the 20-day average.
   4. Support: the close within 3% of the 20-day low.
   5. Gap: after-hours down less than 3%.
   6. Cooldown: no 3.1.20 buy in the last 5 trading days.
   Size: all cash; half the cash when short interest is over 20% of the float
   (the one exception to 3.1.9 Buy size). Exit: the existing levels.
   Not filled that session: Buy returns to stop + one ATR.
2. Dropped in chat: the market filter (QQQ/SPY over the 50-day MA), the peers
   filter (overlaps the news check), the 20-sample test.
3. Evidence: 18 Sep 2026 −6.68% on the Starship slip, +8.83% missed by 22 Sep.
   That day is under the 7% trigger, so 3.1.20 would not have bought it.
4. Applied the same day: Guidebook 3.1.20, 3.1.9, 5.5.4.7.4 and change log;
   MAP.safety "After-drop buy" and the playbook testing note on the Trade Map;
   both Trade Map re-score routines (AFTER-DROP BUY paragraph, safety list);
   Trade Fixer card 3 set to approved (page and Sep 2026 doc).
