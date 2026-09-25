# Trade Map — display spec (LIVING DOCUMENT)

Read this BEFORE building or editing any Trade Map display. Every time.
After the user approves a change to the Trade Map, update this file in the
same session, commit and push. This file is the single source of truth.

Last updated: 2026-09-25 (applied to the Trade Map artifact, v116)

## Structure

1. Screen title: "Trade Map".
2. Events grouped under a date header, monospace uppercase:
   `TODAY · MON 28 SEP 2026`  /  `IN 3 DAYS · MON 28 SEP 2026`  /  `TUE 29 SEP 2026`
3. One card per event:
   - Time + timezone, bold (e.g. `08:15 ET`), then headline (one sentence).
   - Status chip: PENDING / CONFIRMED / DONE / CANCELLED.
   - Key-value rows (label left, value right):
     - OUTCOME — result or `Pending · polling 08:10–09:45 ET, every 2 min`.
     - EXPECT — one line per direction, e.g. `UP 3–6% clean flight · DOWN 5–7% slip/failure`.
     - One row per scenario (e.g. FLEW CLEAN / SLIPPED / FAILED):
       expected move + the action (`buy ≤ $58.00 = 10 sh`).
   - Position line: `$58.00 = 10 sh (unchanged); 6 sh held, 25-share max`.

## Rules (fixes learned so far)

1. "TODAY" only when the event date equals the real current date. Otherwise
   `IN N DAYS` or plain weekday. Never mislabel the date.
2. Value column ≥ 65% of card width; label column ≤ 35%. Labels may wrap to
   2 lines; values must not wrap more than 4 lines.
3. No number is repeated across rows. History (last time +5.76% / −6.68%)
   goes ONCE, in a single HISTORY row, not inside EXPECT and scenario rows.
4. Each value ≤ 25 words. Cut prose, keep numbers and the action.
5. Dark theme, monospace for headers/labels, sans-serif for values.

## Change log

- 2026-09-25: created from screenshot review; rules 1–4 added.
- 2026-09-25: applied to Trade Map (https://claude.ai/artifact/PdNcLUaNjsyVrbPGUy4LLe v116): TODAY card now shows Today / Tomorrow / In N days by real ET date; label column capped at 35%; Expect = moves only, scenario rows = actions only, History once.

## Where the Trade Map lives

Artifact: https://claude.ai/artifact/PdNcLUaNjsyVrbPGUy4LLe (MAP data block is rewritten by routines; the renderer below it is what this spec governs). Spec artifact: https://claude.ai/artifact/UfWf3mhmb8KS6NitWjseEr
