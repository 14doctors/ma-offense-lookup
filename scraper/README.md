# South Essex Sewerage District annual report scraper

Downloads the digitized South Essex Sewerage District annual reports (PDFs)
from the State Library of Massachusetts digital repository at
<https://archives.lib.state.ma.us>.

## How the repository works

The State Library's "digital depository" is a [DSpace 7](https://wiki.lyrasis.org/display/DSDOC7x/REST+API)
repository (the DSpace-CRIS variant). That matters because everything the
website's search box does is also available through a public, unauthenticated
JSON REST API under `https://archives.lib.state.ma.us/server/api`:

| Step | Endpoint | Purpose |
|------|----------|---------|
| 1 | `/pid/find?id=hdl:2452/801080` | Resolve the SESD handle to its internal UUID and type |
| 2 | `/discover/search/objects?...&dsoType=item&page=N&size=50` | The search function — page through matching items, 50 per page |
| 3 | `/core/items/{uuid}/bundles` → `/core/bundles/{uuid}/bitstreams` | Identify each item's PDF file(s) (the `ORIGINAL` bundle holds the scanned documents) |
| 4 | `/core/bitstreams/{uuid}/content` | Download the actual PDF |

`2452/801080` is the handle of the repository's
**South Essex Sewerage District** page, which gathers the digitized annual
reports going back to the 1930s. You can see it in a browser at
<https://archives.lib.state.ma.us/handle/2452/801080>. On this server the
handle resolves to a DSpace-CRIS *entity item* representing the agency
(a migrated collection record), not an ordinary collection — so step 2 tries
listing strategies in order until one yields items:

1. a search scoped to the resolved object (works for ordinary
   communities/collections, which are expanded via
   `/core/communities/{uuid}/collections` first);
2. the title browse index `/discover/browses/title/items?scope={uuid}`
   (the server 500s on entity-item scopes — treated as a soft failure);
3. a site-wide search for the scope UUID (matches CRIS relation metadata);
4. a site-wide phrase search for the entity's name — the strategy that
   works for the SESD page.

Because the last strategy is a full-text phrase search, results can include
other documents that mention the district (old House bills, for example);
add `--query "annual report"` to narrow to the reports.

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
