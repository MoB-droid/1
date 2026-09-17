"""Write the `fired` column (I) of one Hits row. Used by the fast lane to close the loop.

  python mark_hit.py "fired: trade written 10:42 ET"
  python mark_hit.py --row 5 "rejected: recycled 21 Apr 2026"

No arguments beyond the note means row 2 (the newest row; the bot inserts at the top).
Same service account and sheet as the bot. Zero Claude calls.
"""
import os, sys

CLD1 = os.environ.get("CLD1", os.path.dirname(os.path.abspath(__file__)))
CREDS = os.path.join(CLD1, "google_credentials.json")
SHEET_ID = "1cjZru5WmFwLWVflApD07wM1FUgtJbMAZCXaAcY10w18"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def sheets():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()


def main(argv):
    row = 2
    if len(argv) >= 2 and argv[0] == "--row":
        row = int(argv[1]); argv = argv[2:]
    if not argv:
        print("usage: mark_hit.py [--row N] \"<note>\"", file=sys.stderr); return 2
    note = " ".join(argv)[:120]
    rng = f"Hits!I{row}:I{row}"
    svc = sheets()
    # WUD: write, then read it back and confirm.
    svc.values().update(spreadsheetId=SHEET_ID, range=rng, valueInputOption="RAW",
                        body={"values": [[note]]}).execute()
    got = svc.values().get(spreadsheetId=SHEET_ID, range=rng).execute().get("values", [[""]])
    got = (got[0][0] if got and got[0] else "")
    if got.strip() != note.strip():
        print(f"mark_hit: write not confirmed (row {row}, read back {got!r})", file=sys.stderr); return 1
    print(f"mark_hit: row {row} I = {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
