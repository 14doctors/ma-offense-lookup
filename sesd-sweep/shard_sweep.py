# -*- coding: utf-8 -*-
"""SESD pre-1997 corpus sweep — SHARD worker (one year-range per process).

State Library of Massachusetts digital repository (archives.lib.state.ma.us,
DSpace 7 REST API). Each shard sweeps an independent year range; shards may
run concurrently. Detection patterns are BYTE-IDENTICAL to the serial run
launched 5 Aug 2026, so two independent runs can be cross-checked; do not
"improve" a pattern in one run only.

EPISTEMIC RULES (non-negotiable, encoded below):
  * ENUMERATION is deterministic (title-pattern listing + chapter-number
    continuity). A numbering gap is a missing item, reported never skipped.
    Continuity is blind to TAIL truncation — final chapter numbers must be
    confirmed against the printed volumes by hand.
  * TEXT is probabilistic OCR. A clean year means "no hit in the OCR text,"
    never "no hit in the law."
  * NO_TEXT and FETCH_FAIL are distinct; NEITHER is ever clean.
  * A year that errors is RERUN. This script never marks it OK.
  * A hit is a LEAD, not a disposition. Classification is a separate pass.
  * The recall test and the completeness claim are GLOBAL. A shard can only
    report on its own range; merge_verify.py owns the warranty. No shard,
    and no agent running a shard, may declare the sweep clean.

Usage:
    python3 shard_sweep.py --from 1940 --to 1949 [--out out] [--workers 4]
                           [--force] [--force-years 1934,1935]

Politeness: this is a small public state-library server. Default 4 workers
per shard; if FETCH_FAIL climbs, RERUN the shard with --workers 2 — do not
raise concurrency to "push through." Failures manufactured by hammering the
server cost more time than they save, because they all must be rerun.
"""
import argparse, json, os, random, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://archives.lib.state.ma.us/server/api'

# ---- SESD project defaults (overridable) -----------------------------------
CITES = ['339:1925', '431:1945', '516:1969', '643:1972']
NAMES = ['South Essex Sewerage District', 'South Essex sewerage board']
# Biennial-session period: Amendment Art. LXXII made General Court sessions
# biennial (1939, 1941, 1943); Art. LXXV annulled it (annual from 1945). The
# even years held no regular session — a thin enumeration IS clean for them.
THIN_OK = {1940, 1942, 1944}
KNOWN = ['1927:36', '1928:294', '1929:22', '1933:226', '1933:335', '1935:384',
         '1945:169', '1945:431', '1945:492', '1948:168', '1956:468', '1957:104',
         '1958:216', '1969:516', '1972:190', '1972:643', '1973:430', '1973:645',
         '1974:735', '1975:101', '1978:493', '1981:725', '1985:170', '1986:613',
         '1989:618', '1990:173', '1993:116']

# ---- HTTP ------------------------------------------------------------------
def gj(url, tries=4):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0',
                                                       'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(2 + 3 * a + random.random())


def gtext(url, tries=4):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode('utf-8', errors='replace')
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(2 + 3 * a + random.random())

# ---- enumeration (identical to serial run) ---------------------------------
TITLE_RE = re.compile(r'^(\d{4})\s+(?:Resolve\s+)?Chap(?:\.|ter)\s+0*(\d+)', re.I)


def enumerate_year(year):
    items = {}
    for pat in (f'"{year} Chap."', f'"{year} Chapter"', f'"{year} Resolve"'):
        q = urllib.parse.quote(pat)
        page = 0
        while True:
            d = gj(f'{BASE}/discover/search/objects?query={q}&dsoType=item&size=100&page={page}')
            res = d['_embedded']['searchResult']
            objs = res['_embedded'].get('objects', [])
            for o in objs:
                io = o['_embedded']['indexableObject']
                name = io.get('name', '') or ''
                m = TITLE_RE.match(name)
                if m and int(m.group(1)) == year:
                    items[io['uuid']] = (name, int(m.group(2)),
                                         'resolve' in name.lower()[:20])
            if page >= res['page']['totalPages'] - 1 or not objs:
                break
            page += 1
    return items


def continuity(items):
    gaps = {}
    for kind in (False, True):
        nums = sorted(n for _, n, r in items.values() if r == kind)
        if not nums:
            continue
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            gaps['resolves' if kind else 'acts'] = missing
    return gaps


def item_text(uuid):
    """OCR text: prefer ORIGINAL-bundle .txt, else largest nonzero TEXT bitstream."""
    b = gj(f'{BASE}/core/items/{uuid}/bundles?embed=bitstreams')
    cands = []
    for bun in b.get('_embedded', {}).get('bundles', []):
        emb = bun.get('_embedded', {}).get('bitstreams', {})
        bl = emb.get('_embedded', {}).get('bitstreams', []) if isinstance(emb, dict) else emb
        for x in bl:
            sz = x.get('sizeBytes') or 0
            if x['name'].lower().endswith('.txt') and sz > 0:
                pref = 0 if bun['name'] == 'ORIGINAL' else 1
                cands.append((pref, -sz, x['_links']['content']['href']))
    if not cands:
        return None
    cands.sort()
    return gtext(cands[0][2])

# ---- patterns (identical to serial run) ------------------------------------
AMEND = re.compile(r'amend|strik|insert|repeal|added|substitut', re.I)


def build_patterns(cites, names):
    strict, loose, saidp = {}, {}, {}
    for c in cites:
        n, y = c.split(':')
        strict[f'c{n}_{y}'] = re.compile(
            rf'chapter\s*{n}\s*of\s*the\s*acts\s*of\s*{y}', re.I)
        loose[f'loose_{n}_{y}'] = re.compile(
            rf'\b{n}\b[^.]{{0,60}}?a\wts\s*of\s*{y}', re.I)
        saidp[f'said_c{n}'] = (re.compile(rf'said\s*chapter\s*{n}\b', re.I), y)
    for nm in names:
        strict[nm[:24]] = re.compile(re.escape(nm).replace(r'\ ', r'\s*'), re.I)
    return strict, loose, saidp


def scan(text, strict, loose, saidp):
    t = re.sub(r'\s+', ' ', text)
    hits, ctx = {}, {}
    def snip(m):
        return t[max(0, m.start() - 280): m.end() + 280]
    for k, rx in strict.items():
        ms = list(rx.finditer(t))
        if ms:
            hits[k] = len(ms); ctx[k] = snip(ms[0])
    for k, (rx, y) in saidp.items():
        ms = list(rx.finditer(t))
        if ms and f'acts of {y}' in t.lower():
            hits[k] = len(ms); ctx[k] = snip(ms[0])
    for k, rx in loose.items():
        ms = list(rx.finditer(t))
        if ms and k not in hits:
            hits.setdefault(k, len(ms)); ctx.setdefault(k, snip(ms[0]))
    if hits:
        hits['_amendish'] = bool(AMEND.search(t))
    return hits, ctx

# ---- per-year sweep --------------------------------------------------------
def sweep_year(year, strict, loose, saidp, out_dir, workers):
    out = {'year': year, 'items': 0, 'no_text': [], 'fetch_fail': [],
           'gaps': {}, 'hits': [], 'status': 'RERUN'}
    try:
        items = enumerate_year(year)
        out['items'] = len(items)
        if len(items) < 100 and year not in THIN_OK:
            raise RuntimeError(f'EMPTY/THIN ENUMERATION ({len(items)} items) — a throttled or failed discovery query is never a clean year')
        out['gaps'] = continuity(items)
        ordered = sorted(items.items(), key=lambda kv: (kv[1][2], kv[1][1]))

        def work(kv):
            uuid, (name, num, isres) = kv
            time.sleep(random.random() * 0.25)          # jitter — be polite
            try:
                txt = item_text(uuid)
                st = 'ok' if (txt and len(txt.strip()) >= 20) else 'no_txt'
            except Exception:
                txt, st = None, 'fetch_fail'            # NOT the same as no_txt
            return kv, name, num, isres, txt, st

        pending, passes = list(ordered), 0
        while pending and passes < 3:
            passes += 1
            w = workers if passes == 1 else 2           # back off on retries
            retry = []
            with ThreadPoolExecutor(max_workers=w) as ex:
                for kv, name, num, isres, txt, st in ex.map(work, pending):
                    if st == 'fetch_fail':
                        retry.append(kv); continue
                    if st == 'no_txt':
                        out['no_text'].append(name[:90]); continue
                    h, c = scan(txt, strict, loose, saidp)
                    if h:
                        out['hits'].append({'title': name[:120], 'chap': num,
                                            'resolve': isres, 'uuid': kv[0],
                                            'hits': h, 'ctx': c})
            pending = retry
            if pending:
                time.sleep(10 * passes)
        out['fetch_fail'] = [kv[1][0][:90] for kv in pending]
        out['status'] = 'OK'
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'[:300]
    tmp = os.path.join(out_dir, f'year_{year}.json.tmp')
    json.dump(out, open(tmp, 'w'), indent=1)
    os.replace(tmp, os.path.join(out_dir, f'year_{year}.json'))   # atomic
    return out


def load_done(out_dir, year):
    p = os.path.join(out_dir, f'year_{year}.json')
    if not os.path.exists(p):
        return None
    try:
        d = json.load(open(p))
        if d.get('status') != 'OK' or (d.get('items', 0) < 100 and year not in THIN_OK):
            return None      # thin enumeration is never done (except biennial-gap years)
        return d
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='y0', type=int, required=True)
    ap.add_argument('--to', dest='y1', type=int, required=True)
    ap.add_argument('--cite', action='append', default=None, metavar='N:YYYY')
    ap.add_argument('--name', action='append', default=None)
    ap.add_argument('--known', action='append', default=None, metavar='YEAR:CHAP')
    ap.add_argument('--out', default='out')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--force', action='store_true',
                    help='re-sweep even if a clean year file exists')
    ap.add_argument('--force-years', default='',
                    help='comma-separated years to re-sweep regardless')
    a = ap.parse_args()
    cites = a.cite or CITES
    names = a.name or NAMES
    known = {tuple(int(x) for x in k.split(':')) for k in (a.known or KNOWN)}
    force_years = {int(x) for x in a.force_years.split(',') if x.strip()}
    os.makedirs(a.out, exist_ok=True)
    strict, loose, saidp = build_patterns(cites, names)

    label = f'{a.y0}-{a.y1}'
    found, bad_years = set(), []
    for y in range(a.y0, a.y1 + 1):
        prior = None if (a.force or y in force_years) else load_done(a.out, y)
        if prior is not None:
            r, tag = prior, 'SKIP (already OK)'
        else:
            r, tag = sweep_year(y, strict, loose, saidp, a.out, a.workers), 'OK'
            if r['status'] != 'OK':
                tag = 'RERUN'
        for h in r.get('hits', []):
            found.add((y, h['chap']))
        gaps = sum(len(v) for v in r.get('gaps', {}).values())
        if r.get('status') != 'OK' or r.get('fetch_fail') or gaps:
            bad_years.append(y)
        print(f"[{label}] {y}: {tag} items={r.get('items',0)} "
              f"hits={len(r.get('hits',[]))} no_text={len(r.get('no_text',[]))} "
              f"fetch_fail={len(r.get('fetch_fail',[]))} gaps={gaps}", flush=True)

    in_range = {k for k in known if a.y0 <= k[0] <= a.y1}
    missed = in_range - found
    print(f"[{label}] SHARD SUMMARY: years {a.y0}-{a.y1}, "
          f"knowns in range {len(in_range)}, re-found {len(in_range - missed)}")
    if missed:
        print(f"[{label}] SHARD RECALL FAILED — not re-found: {sorted(missed)}")
        print(f"[{label}] NO CLEARANCE for the affected years.")
        sys.exit(2)
    if bad_years:
        print(f"[{label}] YEARS NEEDING RERUN OR REVIEW: {bad_years}")
        print(f"[{label}] A failed year is RERUN, never clean.")
        sys.exit(3)
    print(f"[{label}] shard complete. Global claim belongs to merge_verify.py, "
          f"not to this shard.")


if __name__ == '__main__':
    main()
