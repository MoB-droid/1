# Trump Desk

Artifact: https://claude.ai/artifact/2xvhwAa31RypVqW1mWwDkK
Guidebook rules: 1.8, 6.9, 8.9, 9.7 (https://claude.ai/artifact/2WXGQv6ySeY6uFmuHTttHi)

- `tpl.html` — page renderer. `__DATA__` is replaced by `data.json` at build time.
- `data.json` — the data block: meta (last updated), highlights, roadmap, posts.
- Live data also lives in the artifact database, doc `desk/data` (same shape).
  Routines overwrite that doc; the page follows it live. Other artifacts
  (Premarket News etc.) read from it, never re-summarise.

Sources: Truth Social via https://www.trumpstruth.org/feed (RSS mirror of
@realDonaldTrump; truthsocial.com API itself returns 403). Schedule via
Factba.se (rollcall.com/factbase/trump/topic/calendar/) and kadoa.com/potus/schedule.

Time stamps: ET first, Israel in brackets, on top of every item.
