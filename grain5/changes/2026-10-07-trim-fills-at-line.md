# 2026-10-07 · Rule 3.1.18 amended: Trim fills at the line, price only

Guidebook change (Grain 5 rule 4.3.1, step 5: the spec note in the repo).
From Trade Fixer Sep 2026, card 4, approved by Moran in chat.

1. Problem: 29 Sep 2026 ASTS popped to about $65 in the morning, over the
   $62.64 Trim, and closed $59.40. The Trim was checked only at 15:50 ET, so
   nothing was sold (about +$21 missed). Rule 3.1.18 (06 Oct) checks in every
   run, but only at the live price, so a pop between two runs is still missed.
2. Fills at the line: the Trim works like a resting limit sell. Every run reads
   today's 1-minute high; when it reached the Trim and the lot is not trimmed,
   half is booked as sold at the Trim price (the bar open on a gap through it),
   timed at the first touch, even after a fade. Paper fill now; a broker
   resting limit sell when trading goes live.
3. Price only: the Trim is a trigger number (3.1.9, 05 Oct). The "no
   ASTS-specific catalyst" condition is dropped; news never blocks or undoes
   the Trim. The other half rides the news.
4. Applied the same day: Guidebook 3.1.9, 3.1.18, 4.1.2.4, 4.1.2.8, 5.5.4.7.2,
   the 5.5.4 C sample and the change log; Trader intraday (S4) and 15:50 ET
   routines; Daily Event Watch runner STEP 0; both Trade Map re-score
   routines; MAP.safety Trim and the renderer note on the Trade Map; Trade
   Fixer card 4 set to approved.
5. Open: the PC price bot's levels.json has no trim key and has not been
   updated since 25 Sep 2026, so the bot does not watch the Trim.
