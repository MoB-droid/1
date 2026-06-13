# Spec change — Index-event coverage (S&P 500 / Nasdaq-100)

Session: Better agent, 2026-06-13
Trigger: Alert Bot missed RKLB's Nasdaq-100 inclusion catalyst. On 2026-06-12 it
logged RKLB +9.26% but attributed it to Iran/defence-launch geopolitics, not the
index inclusion announced 2026-06-11 (effective 2026-06-22). Zero mentions of
"Nasdaq-100", "index inclusion", "rebalance", or "reconstitution" anywhere in the
Alert agent log.

Boundary kept across all three: rma / xbot forecast and speculate; Fact Bot anchors
only confirmed dates and figures (defers nothing it can't source).

---

## 1. Alert Bot — index-event detector leg  (CONFIRMED)

Add to ALERT AGENT spec (doc id 16zKRBZpMc27fs94kyOUPbTBTgNWUd8KSxEaqllUXrRA),
under "WHAT IT READS" / "LOGIC PER DETECTOR RUN".

- New detector leg: on each run, scan official index releases for List 1 tickers:
  - Nasdaq-100 quarterly + annual reconstitution releases (Nasdaq IR / Global Indexes).
  - S&P 500 add/drop announcements (S&P Dow Jones Indices).
- On an announcement-day hit for a List 1 ticker, fire a card tagged [INDEX].
- Attribution rule: when a >=8% single-day move coincides with a same-day index
  announcement for that ticker, flag [INDEX] as a candidate cause — do NOT default
  to the macro/geopolitics narrative without ruling it out.
- Route the dated record (announcement date, effective date, add/drop) through Fact
  Bot for the verified factual line before Alert assigns a cause.

## 2. Pre-announcement nominee rumors  (owner: xbot + rma — NOT Fact Bot)

There is no official "nominee" stage. Candidacy = market-cap rank at the index
cutoff (Nasdaq-100) or S&P committee discretion. Pre-announcement coverage is
therefore speculative and must never be asserted as fact.

- xbot: surface analyst chatter / rumor that a List 1 name is a likely S&P 500 or
  Nasdaq-100 add. Tag output [rumor] / [unverified].
- rma: maintain an eligibility screen — List 1 names crossing S&P 500 size/liquidity
  bars, or ranking into the Nasdaq-100 top-100 by market cap near a cutoff date.
- Fact Bot stays silent on candidacy until the official release; then it anchors the
  confirmed dated record.

## 3. T-7 effective-date alert -> rma  (owner: rma; surfaced by Alert Bot)

rma already owns index/dividend forward events. Extend it:

- Maintain an index-rebalance calendar:
  - Nasdaq-100 quarterly: effective prior to open on the 3rd Friday of Mar/Jun/Sep/Dec.
  - Nasdaq-100 annual: December reconstitution.
  - S&P 500: as-announced effective dates.
- Fire a card 7 days before any effective date affecting a List 1 ticker.
- Hand the info (ticker, add/drop, announcement date, effective date) to rma to push
  through the roadmap as a dated forward event.
