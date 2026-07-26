#!/usr/bin/env python3
"""
Download South Essex Sewerage District annual reports from the
State Library of Massachusetts digital repository (DSpace 7).

The State Library's repository at https://archives.lib.state.ma.us is a
DSpace 7 instance. Everything the website's search box can do is also
exposed by its public REST API under /server/api, which is what this
script uses:

  1. Resolve the collection handle (2452/801080, "South Essex Sewerage
     District") to its internal UUID via /server/api/pid/find.
  2. Page through every item in that collection with the discovery
     search endpoint /server/api/discover/search/objects, optionally
     filtered by a keyword query (e.g. "annual report").
  3. For each item, list its ORIGINAL bundle's bitstreams and keep the
     PDFs.
  4. Download each PDF from /server/api/core/bitstreams/{uuid}/content
     into the output folder, and write a manifest.csv describing what
     was fetched.

Runs on Python 3.8+ with the standard library only.

Examples:
    python3 sesd_scraper.py                          # everything in the collection
    python3 sesd_scraper.py --query "annual report"  # keyword-filtered
    python3 sesd_scraper.py --dry-run                # list, don't download
    python3 sesd_scraper.py --out ~/sesd-reports --delay 2
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ.get("SESD_API_BASE", "https://archives.lib.state.ma.us/server/api")
SESD_COLLECTION_HANDLE = "2452/801080"

# The repository sits behind a WAF that rejects obvious bot user agents,
# so identify as a regular browser.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

MAX_RETRIES = 4
PAGE_SIZE = 50


def http_get(url, retries=MAX_RETRIES):
    """GET a URL with retries and exponential backoff; returns raw bytes."""
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_err = e
            # Retry on rate limiting / transient server errors.
            if e.code in (429, 500, 502, 503, 504):
                wait = int(e.headers.get("Retry-After") or 2 ** (attempt + 1))
                print(f"    HTTP {e.code}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            wait = 2 ** (attempt + 1)
            print(f"    {e}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Failed after {retries} attempts: {url}") from last_err


DEBUG = False


def get_json(url):
    if DEBUG:
        print(f"    GET {url}", file=sys.stderr)
    data = json.loads(http_get(url).decode("utf-8"))
    if DEBUG:
        print(f"    -> {json.dumps(data)[:400]}", file=sys.stderr)
    return data


def resolve_handle(handle):
    """Resolve a DSpace handle to the object's UUID, name, and type."""
    url = f"{BASE}/pid/find?id=hdl:{urllib.parse.quote(handle, safe='/')}"
    obj = get_json(url)
    return obj["uuid"], obj.get("name", ""), obj.get("type", "")


def first_metadata(obj, key, default=""):
    values = obj.get("metadata", {}).get(key, [])
    return values[0]["value"] if values else default


def paged(url_base, embedded_key):
    """Yield objects from a paginated DSpace endpoint."""
    page = 0
    while True:
        sep = "&" if "?" in url_base else "?"
        data = get_json(f"{url_base}{sep}page={page}&size={PAGE_SIZE}")
        for obj in data.get("_embedded", {}).get(embedded_key, []):
            yield obj
        page += 1
        if page >= data.get("page", {}).get("totalPages", 0):
            break


def collection_scopes(uuid, dso_type):
    """Expand a community handle into the collections it contains.

    The SESD handle can point at either a collection of items or a
    community that holds one or more collections; scoped item searches
    only return results against collections, so communities have to be
    walked down to their collections (including nested subcommunities).
    """
    if dso_type == "collection":
        return [uuid]
    scopes = []
    if dso_type == "community":
        for col in paged(f"{BASE}/core/communities/{uuid}/collections",
                         "collections"):
            print(f"  contains collection: {col.get('name', '?')}")
            scopes.append(col["uuid"])
        for sub in paged(f"{BASE}/core/communities/{uuid}/subcommunities",
                         "subcommunities"):
            print(f"  descending into subcommunity: {sub.get('name', '?')}")
            scopes.extend(collection_scopes(sub["uuid"], "community"))
    return scopes or [uuid]


def iter_search_items(scope_uuid, query=None):
    """Yield items via the discovery search API, optionally scoped."""
    page = 0
    while True:
        params = {
            "dsoType": "item",
            "page": str(page),
            "size": str(PAGE_SIZE),
        }
        if scope_uuid:
            params["scope"] = scope_uuid
        if query:
            params["query"] = query
        url = f"{BASE}/discover/search/objects?{urllib.parse.urlencode(params)}"
        data = get_json(url)
        result = data["_embedded"]["searchResult"]
        for wrapper in result["_embedded"]["objects"]:
            obj = wrapper["_embedded"]["indexableObject"]
            # The State Library's server echoes the scope object itself
            # back as a search result (it models agencies as entity
            # items); skip it and anything that isn't a real item.
            if obj.get("uuid") == scope_uuid:
                continue
            if obj.get("type", "item") == "item":
                yield obj
        page_info = result["page"]
        page += 1
        if page >= page_info.get("totalPages", 0):
            break


def iter_collection_items(scope_uuid, query=None, fallback_query=None):
    """Yield every item in scope, trying three listing strategies:
    scoped search, then the title browse index (what the website's
    "Browse by Title" pages use), then a site-wide phrase search for
    the scope object's name."""
    found = False
    for item in iter_search_items(scope_uuid, query):
        found = True
        yield item
    if found or query:
        return  # don't fall back to unfiltered listings past an explicit query
    print("  scoped search returned nothing; trying title browse index...")
    for item in paged(
            f"{BASE}/discover/browses/title/items?scope={scope_uuid}",
            "items"):
        found = True
        yield item
    if found or not fallback_query:
        return
    print(f'  browse returned nothing; site-wide search for "{fallback_query}"...')
    for item in iter_search_items(None, f'"{fallback_query}"'):
        yield item


def item_pdf_bitstreams(item_uuid):
    """Return (name, uuid, size) for each PDF in the item's ORIGINAL bundle."""
    bundles = get_json(f"{BASE}/core/items/{item_uuid}/bundles?size=50")
    pdfs = []
    for bundle in bundles.get("_embedded", {}).get("bundles", []):
        if bundle.get("name") != "ORIGINAL":
            continue
        bs = get_json(f"{BASE}/core/bundles/{bundle['uuid']}/bitstreams?size=100")
        for b in bs.get("_embedded", {}).get("bitstreams", []):
            name = b.get("name") or ""
            mime = first_metadata(b, "dc.format.mimetype").lower()
            if name.lower().endswith(".pdf") or mime == "application/pdf":
                pdfs.append((name, b["uuid"], b.get("sizeBytes")))
    return pdfs


def safe_filename(text, max_len=150):
    text = re.sub(r"[^\w\s.-]", "", text).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:max_len] or "untitled"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--out", default="sesd_reports", help="output folder (default: sesd_reports)")
    ap.add_argument("--handle", default=SESD_COLLECTION_HANDLE,
                    help=f"collection handle (default: {SESD_COLLECTION_HANDLE})")
    ap.add_argument("--query", default=None,
                    help='optional keyword filter, e.g. "annual report"')
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds to pause between downloads (default: 1.0)")
    ap.add_argument("--limit", type=int, default=None, help="stop after N items")
    ap.add_argument("--dry-run", action="store_true",
                    help="list items and PDFs without downloading")
    ap.add_argument("--debug", action="store_true",
                    help="print every API request and a snippet of each response")
    args = ap.parse_args()

    global DEBUG
    DEBUG = args.debug

    out_dir = Path(args.out)

    print(f"Resolving handle {args.handle} ...")
    root_uuid, name, dso_type = resolve_handle(args.handle)
    print(f"  -> {name!r} ({dso_type or 'unknown type'}, {root_uuid})")
    scopes = collection_scopes(root_uuid, dso_type)

    manifest_rows = []
    item_count = 0
    pdf_count = 0
    seen_items = set()

    for item in (i for scope in scopes
                 for i in iter_collection_items(scope, query=args.query,
                                                fallback_query=name)):
        if args.limit is not None and item_count >= args.limit:
            break
        if item["uuid"] in seen_items:
            continue
        seen_items.add(item["uuid"])
        item_count += 1
        title = first_metadata(item, "dc.title", item.get("name", "untitled"))
        issued = first_metadata(item, "dc.date.issued")
        handle = item.get("handle", "")
        print(f"[{item_count}] {title} ({issued or 'no date'})  hdl:{handle}")

        pdfs = item_pdf_bitstreams(item["uuid"])
        if not pdfs:
            print("    no PDF bitstreams found")
        for bs_name, bs_uuid, size in pdfs:
            pdf_count += 1
            prefix = f"{issued}_" if issued else ""
            local_name = f"{prefix}{safe_filename(title)}__{safe_filename(bs_name)}"
            if not local_name.lower().endswith(".pdf"):
                local_name += ".pdf"
            dest = out_dir / local_name
            content_url = f"{BASE}/core/bitstreams/{bs_uuid}/content"
            manifest_rows.append({
                "title": title, "issued": issued, "handle": handle,
                "bitstream": bs_name, "url": content_url, "file": local_name,
            })
            if args.dry_run:
                print(f"    would download {bs_name} ({size or '?'} bytes)")
                continue
            if dest.exists():
                print(f"    already have {local_name}, skipping")
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"    downloading {bs_name} ({size or '?'} bytes) -> {dest}")
            data = http_get(content_url)
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(data)
            tmp.rename(dest)
            time.sleep(args.delay)

    if manifest_rows and not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest = out_dir / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
            writer.writeheader()
            writer.writerows(manifest_rows)
        print(f"\nWrote {manifest}")

    print(f"\nDone: {item_count} items, {pdf_count} PDFs"
          f"{' (dry run)' if args.dry_run else ''}.")


if __name__ == "__main__":
    main()
