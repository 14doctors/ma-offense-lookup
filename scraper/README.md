# South Essex Sewerage District annual report scraper

Downloads the digitized South Essex Sewerage District annual reports (PDFs)
from the State Library of Massachusetts digital repository at
<https://archives.lib.state.ma.us>.

## How the repository works

The State Library's "digital depository" is a [DSpace 7](https://wiki.lyrasis.org/display/DSDOC7x/REST+API)
repository. That matters because everything the website's search box does is
also available through a public, unauthenticated JSON REST API under
`https://archives.lib.state.ma.us/server/api`:

| Step | Endpoint | Purpose |
|------|----------|---------|
| 1 | `/pid/find?id=hdl:2452/801080` | Resolve the SESD handle to its internal UUID and type |
| 2 | `/core/communities/{uuid}/collections` | The SESD handle is a *community* (a container), so expand it into the collection(s) of items it holds |
| 3 | `/discover/search/objects?scope={uuid}&dsoType=item&page=N&size=50[&query=...]` | The search function — page through every item in each collection, optionally keyword-filtered (with `/discover/browses/title/items` as a fallback listing) |
| 4 | `/core/items/{uuid}/bundles` → `/core/bundles/{uuid}/bitstreams` | Identify each item's PDF file(s) (the `ORIGINAL` bundle holds the scanned documents) |
| 5 | `/core/bitstreams/{uuid}/content` | Download the actual PDF |

`2452/801080` is the handle of the repository's dedicated
**South Essex Sewerage District** collection, which contains the digitized
annual reports going back to the 1930s. You can see it in a browser at
<https://archives.lib.state.ma.us/handle/2452/801080>.

## Usage

Requires only Python 3.8+ (standard library, nothing to install):

```bash
# Download the whole collection into ./sesd_reports/
python3 sesd_scraper.py

# Preview what would be downloaded, without downloading
python3 sesd_scraper.py --dry-run

# Keyword-filter, custom folder, slower pacing
python3 sesd_scraper.py --query "annual report" --out ~/sesd-reports --delay 2
```

Files are named `<year>_<item title>__<original filename>.pdf`, already-present
files are skipped (so re-running resumes an interrupted download), and a
`manifest.csv` records the title, date, handle, source URL, and local filename
for every PDF.

## Notes

- The site sits behind a web application firewall that rejects obvious bot
  traffic, so the script sends a normal browser `User-Agent` and paces its
  requests (1 s between downloads by default). Please keep the pacing polite —
  this is a small state-government server.
- These are Commonwealth of Massachusetts public documents.
- If the REST API is ever unavailable, the same content is harvestable via the
  repository's OAI-PMH endpoint
  (`/oai/request?verb=ListRecords&metadataPrefix=oai_dc&set=col_2452_801080`),
  which returns item metadata including bitstream links.
- To scrape a *different* agency's reports, find its collection page on the
  site and pass its handle: `python3 sesd_scraper.py --handle 2452/XXXXXX`.
