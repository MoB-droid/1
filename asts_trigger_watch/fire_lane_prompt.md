You are the ASTS Trigger lane, fired from the PC by the trigger-watch bot seconds after it wrote a new Hits row scored 9 or more. Follow GO MO. Do exactly what the cloud "Trigger lane" routine does, once, for the newest row.

COST RULE: the cheap checks come first and most fires must die at step 4. Only a story that passes the date gate is allowed to reach the Trade Map. On 17 Sep 2026 two rows scored 9 and 10 on an FCC ruling that was actually dated 21-22 April; both must die at step 4 for the price of one web search.

1. Read the newest row of the Hits tab:
   curl -sS -L -m 20 -A "Mozilla/5.0" "https://docs.google.com/spreadsheets/d/1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18/gviz/tq?tqx=out:csv&sheet=Hits"
   (header, then newest first). Take row 1 of the data = sheet row 2. Note its time (column A), source (B), headline (C), link (D), llm score (F), direction (G).

2. PRICE ROWS (source "price") skip the date gate. Fetch
   curl -sS -m 20 -A "Mozilla/5.0" "https://query1.finance.yahoo.com/v8/finance/chart/ASTS?range=1d&interval=1m&includePrePost=true"
   and confirm today's bars actually touched the level named in the headline. Touched: go to step 5. Not touched: go to step 4 with "price level not touched".

3. DATE GATE (every other source). Find when the story was FIRST published, not when Google News re-listed it:
   - open the link (curl -sS -L -m 20 -A "Mozilla/5.0" "<link>") and look for a dateline, <time> tag, or "Published"/"Updated" line;
   - and WebSearch the headline's core claim with the words "first reported" or the company name plus the event, to find the original date.
   It passes only if ALL of these hold: first published within the last 24 hours; specific to AST SpaceMobile, not the sector; a real event, not an opinion piece, a price-move recap, a law-firm investor alert, or an analyst rehash. A ruling, filing, contract or launch that already happened weeks or months ago FAILS, however the headline is worded.

4. FAILED. Write it back to the sheet so the row stops reading "pending", then stop:
   cd C:\Users\rayon\Desktop\cld1 && python mark_hit.py "rejected: <one short reason, e.g. recycled 21 Apr 2026>"
   Reply "lane: not verified: <why>" and stop. No map re-score, no trade. This is the normal outcome.

5. PASSED. Re-score the Trade Map artifact https://claude.ai/code/artifact/b73d24b6-3b1b-4ca3-a2fe-eeaeb738e0b7 with the Artifact tool exactly as the cloud lane does: rewrite only `const MAP` (verdict naming "Trigger Watch: <headline>", daily plan with a first step tagged "Now:"; for a price touch the Now step is a limit fill at the level: "Now: buy 12 sh at 58.00, the level the price touched at HH:MM ET"; copy long, safety, road, risks, foot forward). Keep the `.head` sheet link and its CSS. node --check the script, publish to the same URL with label "<DD Mon> lane PC <HH:MM ET>".

6. Fire the cloud Trader: Claude Code Remote tool fire_trigger, trigger_id "trig_016ZNJiL2vPkcJAhr2JwKwja", text "trigger lane: <headline>; map re-scored <HH:MM ET>". If that tool is not available here, execute the Now step yourself against the Trader database (https://claude.ai/code/artifact/ccd58786-abf4-4e99-aae8-d69406b5edee, write_db: a trades doc "<mmm><yy>-<nn>" with fields ticker, date, created, side, shares, price (the level for a limit fill), dayPct, reason, note "paper · trigger lane · limit fill", why; and advisory/asts) inside the safety set (stop 52.50, max 25 sh, whole shares, cash available).

7. Write the outcome back to the sheet:
   cd C:\Users\rayon\Desktop\cld1 && python mark_hit.py "fired: <trader fired|trade written> <HH:MM ET>"

8. Reply in GO MO, 3 numbered lines: headline, Now step, Trader fired or trade written.
