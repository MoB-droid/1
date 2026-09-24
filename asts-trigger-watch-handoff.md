# ASTS / Trade Map / Trigger Watch — handoff

Session date: 24 Sep 2026. Prepared for a fresh discussion. Nothing here should be
acted on without re-verification.

---

## 1. The system as it stands

| # | Component | Where it lives | Role |
|---|---|---|---|
| 1 | Trade Map | Artifact `claude.ai/artifact/PdNcLUaNjsyVrbPGUy4LLe` | Scores the trade, holds the plan |
| 2 | Trade Map SIM | Artifact `RcUS1pfAMgYLJekfAMNnhU` | Simulation copy |
| 3 | ASTS History | Artifact `5GmoFNnoSra3r1gTdQR2Tc` | Per-session learning log (`db`, collection `log`) |
| 4 | Ticker Desk | Artifact `Ya7HuN4qbpa5V1kr3P7MVx` | 10:00 ET and 16:15 ET session logs |
| 5 | Premarket News | Artifact `PmKrqj3zfQU4865kdMhuZL` | Pre-market editions |
| 6 | Macro Desk | Artifact `88oBm5CZfdTvwTdQHHUWYC` | Macro pillars |
| 7 | Trader | Artifact `SJ3JXkePMjEKDco5fjpfuP` | Executes the daily plan |
| 8 | Trigger Watch | Google Sheet `1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18` | 2-min news poller and scorer |
| 9 | Price sheet (list 1) | Google Sheet `1-I8rGODnqLC_AARz0uXjst4fIks-Pllbpwfx1-lJmD0` | Daily % change and price, 25 tickers |
| 10 | levels.json | repo `MoB-droid/1`, branch `asts-levels`, `asts_trigger_watch/levels.json` | Price leg input |

Trigger Watch is a **sheet, not an artifact**. Its runner code is not in the repo —
only `levels.json` is on the `asts-levels` branch. So the runner's real behaviour
could not be inspected this session; everything below about it comes from the
sheet's own Config tab.

---

## 2. Position and levels (as of the 24 Sep 05:10 ET map run)

| # | Item | Value |
|---|---|---|
| 1 | Holding | 6 sh @ $58.00 |
| 2 | Cash | $1,257.10 |
| 3 | Last print | $59.98, 23 Sep 16:00 ET close, −5.83% |
| 4 | Stop | $54.14 (15% trail off the $63.69 high close, 22 Sep) |
| 5 | Trim trigger | $62.64 (+8% from entry, catalyst-free, checked 15:50 ET) |
| 6 | Target | $67.00 |
| 7 | Pending buy | $58.00, 10 sh — unfilled, $1.98 below the last close |
| 8 | Verdict | No-Go / hold |

---

## 3. Verified findings

### 3.1 The −5% after-drop pattern

Built from the list-1 price sheet, ASTS column, 17 Aug – 23 Sep 2026.
**Seven** closes of −5% or worse, not six — the Trade Map playbook's tally is
missing 28 Aug.

| # | Date | Drop | Cause | D+1 | 5 sessions |
|---|---|---|---|---|---|
| 1 | 18 Aug | −5.72% | none identified | −2.06% | −10.7% |
| 2 | 24 Aug | −9.18% | Q2 miss, SpaceX IPO fear | −0.55% | −5.2% |
| 3 | 28 Aug | −5.52% | macro / PCE | +1.81% | +7.3% |
| 4 | 01 Sep | −5.58% | macro | +11.83% | +11.9% |
| 5 | 09 Sep | −5.60% | SpaceX lockup unlock | −4.02% | −5.0% |
| 6 | 18 Sep | −6.68% | Starship slip | +5.76% | +8.8% |
| 7 | 23 Sep | −5.83% | rates / hot PMI, no ASTS news | open | open |

Split, on 6 complete samples:

- Company-specific cause (1, 2, 5) → kept falling. 3 of 3.
- Macro or sector cause, no ASTS news (3, 4, 6) → bounced. 3 of 3.
- 23 Sep sits in the second bucket.

Caveats: every bounce had a visible trigger (analyst upgrade, sector rally); the
rate backdrop on 23–24 Sep is worse than in cases 3 and 4 (10Y ~5.11%, October-hike
odds ~71%, PCE due 30 Sep). Six samples is not a rule.

### 3.2 Trigger Watch config (Config tab, verbatim)

| # | Rule | Value | Sheet's own note |
|---|---|---|---|
| 1 | poll interval | 2 min | 24/7 |
| 2 | keyword threshold | 3 | sum of weights to become a candidate |
| 3 | llm threshold | 7 | llm score to fire Trade Map + Trader |
| 4 | llm daily cap | 50 | then keyword-only rows |
| 5 | dedupe | title+link hash | |
| 6 | **fire on** | **off** | fast lane; keep off until designed |
| 7 | **fire cmd** | *(blank)* | fast lane command; blank = nothing runs |
| 8 | price on | on | zero-credit price leg |
| 9 | price score | 9 | Hits llm score written for a price touch |

Feeds (Sources tab), all ASTS-scoped: GlobeNewswire all, GlobeNewswire aerospace,
PRNewswire all, PRNewswire telecom, SEC EDGAR ASTS, Google News "AST SpaceMobile"
(min kw 7), Google News direct-to-cell (min kw 7). Off: BusinessWire (403), FCC
headlines (403), X Elon Musk, X Abel Avellan, Truth Social.

**No RKLB feed. No IRDM feed.** Keyword "Iridium" is weight **1**, below the
candidate threshold of 3.

### 3.3 The `fired` column

Hits tab rows sampled (roughly 250 rows, 20–24 Sep):

| # | `fired` value | Count |
|---|---|---|
| 1 | recycled | 172 |
| 2 | no | 73 |
| 3 | **pending** | **2** |
| 4 | blank | 1 |

No row reads "yes". The two pending rows are the only ones that cleared llm ≥ 7:

**Row A — 24 Sep 2026 05:54 ET**
- Source: Google News AST SpaceMobile
- Headline: "SpaceX Just Launched AST SpaceMobile's Biggest Bet To Advance Cell Service From Space" — Stocktwits
- kw 7, **llm 8**, direction **up**
- Why: "Major launch success of key satellite advancing commercial service"
- Price at hit: 59.48
- `fired`: **pending**

**Row B — 21 Sep 2026 10:42 ET**
- Source: Google News direct-to-cell
- Headline: "ASTS Stock Rises Overnight: AST SpaceMobile Clears The Runway For 'Imminent' UK Direct-To-Cell Service With Vodafone" — Stocktwits
- kw 12, **llm 7**, direction **up**
- `fired`: **pending**

**Row A is a false positive.** No BlueBird launch occurred in September 2026. The
last two were 17 Jun 2026 (BlueBird 8-10) and 5 Aug 2026, both confirmed by
Spaceflight Now. The recycled detector caught 172 other rows and missed this one;
the llm then scored it 8 and marked it up. **Not verified independently beyond a
web search — re-check before relying on it.**

### 3.4 RKLB–Iridium shareholder vote, 24 Sep 08:30 ET

- Iridium holders vote on being acquired by Rocket Lab. Virtual, 08:30 ET.
- Terms: $27 cash + RKLB stock per IRDM share, exchange ratio off RKLB's 10-day VWAP.
- Majority of IRDM holders required. Close expected mid-2027.
- Friction: SpaceX flagged the deal to the FCC (28 Aug; RKLB −4.65%, ASTS −5.52% that day). Three shareholder suits allege disclosure gaps.
- Peer event, not ASTS-specific. Any ASTS move from it is sector sympathy, which
  under the Trim rule means a catalyst-free move.
- **Nothing in the system was watching for the result.** Trigger Watch has no
  RKLB/IRDM feed and "Iridium" scores below threshold. The 09:00 ET map run and
  the 10:00 ET Ticker Desk were the only possible catchers, both indirect.

### 3.5 Trade Map rendering — dark data

The 22 Sep restructure dropped these MAP fields from rendering. The data is still
written every run and read by the routines; the page showed none of it:

| # | Field | Contents |
|---|---|---|
| 1 | price | current price, % change, timestamp |
| 2 | verdict | the Go / No-Go call and its reasons |
| 3 | daily | today's objective, execution steps, buy/sell/size notes |
| 4 | safety | the 5 fixed rules |
| 5 | inputs | sector (with peer prices), overnight, macro, ticker, trader |
| 6 | long | the long plan |
| 7 | levels.above | consensus 79.61, Berenberg 92, 52-wk high 133.86 |
| 8 | risks | the 4 things that break the map |
| 9 | foot | basis, sources, run schedule |

The action line (`HOLD 6 sh · stop $54.14 · now $59.98`) is computed every run and
discarded.

---

## 4. Changes made to the Trade Map this session

Two publishes. Both are live and carry forward.

1. **v100** — added a Roadmap row for the 24 Sep 08:30 ET Iridium vote, and a code
   comment stating the rule: every upcoming ASTS-moving event gets a Roadmap row,
   date "TBD" if unknown.
2. **v101** — added a "Dark data" button at the foot of the page. It lists every
   top-level MAP key the renderer does not show, driven by a `RENDERED` allowlist,
   so a field added later surfaces automatically.

No changes were made to Trigger Watch, the price sheet, the Trader, or any other
artifact.

---

## 5. Proposed but NOT done

1. Add RKLB and IRDM feeds to Trigger Watch Sources.
2. Raise keyword "Iridium" from weight 1 to 2–3.
3. Run the recycled/staleness check **before** the llm scores, not after — Row A
   shows a stale headline reaching llm 8 today.
4. Only then consider `fire on = on` with a real `fire cmd`.
5. Restore some of the dark fields to the rendered page (price, verdict, daily).

---

## 6. Corrections to statements made this session

Stated wrongly, corrected later in the same session:

1. Claimed the Iridium vote details were "in the Trade Map" — they were in
   `verdict`, `daily` and `inputs`, which the page does not render. Not visible.
2. Claimed Trigger Watch had no fast-lane mechanism. Wrong: the `fired` column and
   the llm threshold exist and work. What is off is the execution switch
   (`fire on = off`, blank `fire cmd`).
3. Implied gaps in the Hits timestamps showed the poller stalling. They do not —
   rows are only written when something clears the keyword threshold.

Treat every number above as needing re-verification.
