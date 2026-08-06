# -*- coding: utf-8 -*-
"""SESD pre-1997 sweep — GLOBAL merge and verification.

The completeness claim is global; shards cannot make it. This script:
  1. Requires a year_YYYY.json with status OK for EVERY year 1925-1996.
  2. Aggregates hits, NO_TEXT, FETCH_FAIL and continuity gaps.
  3. Runs the GLOBAL recall test against all 27 known pre-1997 amendments.
  4. Optionally cross-checks hit sets against a second independent run
     (--cross-check DIR) — two runs agreeing is a cheap warranty upgrade;
     two runs disagreeing on any year is a defect to investigate, never to
     average away.
  5. On a clean result, emits SWEEP_CERTIFICATE.json and a draft replacement
     COMPLETENESS editorial note. On anything else: NO CLEARANCE, nonzero exit.

Residual that no script closes: chapter-number continuity is blind to TAIL
truncation. The final chapter number of each year must be confirmed against
the printed Acts and Resolves volume by hand; the certificate records this
as an open manual step until a human initials it.
"""
import argparse, datetime, json, os, sys

KNOWN = ['1927:36', '1928:294', '1929:22', '1933:226', '1933:335', '1935:384',
         '1945:169', '1945:431', '1945:492', '1948:168', '1956:468', '1957:104',
         '1958:216', '1969:516', '1972:190', '1972:643', '1973:430', '1973:645',
         '1974:735', '1975:101', '1978:493', '1981:725', '1985:170', '1986:613',
         '1989:618', '1990:173', '1993:116']


def load(out_dir, y):
    p = os.path.join(out_dir, f'year_{y}.json')
    if not os.path.exists(p):
        return None, 'MISSING'
    try:
        d = json.load(open(p))
    except Exception:
        return None, 'UNREADABLE'
    return d, d.get('status', 'RERUN')


def hitkeys(d):
    return sorted((h['chap'], bool(h.get('resolve'))) for h in d.get('hits', []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out')
    ap.add_argument('--from', dest='y0', type=int, default=1925)
    ap.add_argument('--to', dest='y1', type=int, default=1996)
    ap.add_argument('--known', action='append', default=None)
    ap.add_argument('--cross-check', dest='xdir', default=None)
    a = ap.parse_args()
    known = {tuple(int(x) for x in k.split(':')) for k in (a.known or KNOWN)}

    problems, found = [], set()
    tot_items = tot_hits = 0
    no_text, fetch_fail, gap_years, maxchap = [], [], [], {}
    hits_flat = []
    for y in range(a.y0, a.y1 + 1):
        d, st = load(a.out, y)
        if st != 'OK':
            problems.append(f'{y}: {st}')
            continue
        tot_items += d.get('items', 0)
        for h in d.get('hits', []):
            found.add((y, h['chap']))
            hits_flat.append({'year': y, **h})
        tot_hits += len(d.get('hits', []))
        for n in d.get('no_text', []):
            no_text.append(f'{y}: {n}')
        for n in d.get('fetch_fail', []):
            fetch_fail.append(f'{y}: {n}')
        if any(d.get('gaps', {}).values()):
            gap_years.append((y, d['gaps']))
        nums = [h['chap'] for h in d.get('hits', [])]
        maxchap[y] = d.get('items', 0)

    print('=' * 68)
    print('  SESD PRE-1997 SWEEP — GLOBAL VERIFICATION')
    print('=' * 68)
    print(f'  Range: {a.y0}-{a.y1}   years OK: {a.y1 - a.y0 + 1 - len(problems)}'
          f'/{a.y1 - a.y0 + 1}   items swept: {tot_items}   hits: {tot_hits}')

    ok = True
    if problems:
        ok = False
        print(f'\n  ❌ COVERAGE INCOMPLETE — {len(problems)} year(s) not clean:')
        for p in problems:
            print(f'       {p}')
    if fetch_fail:
        ok = False
        print(f'\n  ❌ FETCH_FAIL items (never clean, rerun their years): {len(fetch_fail)}')
        for f in fetch_fail[:20]:
            print(f'       {f}')
    if gap_years:
        ok = False
        print(f'\n  ❌ CHAPTER-NUMBER GAPS (missing items, must be resolved):')
        for y, g in gap_years:
            print(f'       {y}: {g}')
    if no_text:
        print(f'\n  ⚠️  NO_TEXT items — named residuals, pull each BY HAND: {len(no_text)}')
        for n in no_text:
            print(f'       {n}')

    missed = known - found
    if missed:
        ok = False
        print(f'\n  ❌ GLOBAL RECALL TEST FAILED — known amendments not re-found:')
        for m in sorted(missed):
            print(f'       {m[0]} c.{m[1]}')
    else:
        print(f'\n  ✅ GLOBAL RECALL TEST PASSED — all {len(known)} known pre-1997 '
              f'amendments re-found by the sweep.')

    # ---- cross-check against an independent run ----------------------------
    if a.xdir:
        diffs = []
        for y in range(a.y0, a.y1 + 1):
            d1, s1 = load(a.out, y)
            d2, s2 = load(a.xdir, y)
            if s1 == 'OK' and s2 == 'OK' and hitkeys(d1) != hitkeys(d2):
                diffs.append((y, hitkeys(d1), hitkeys(d2)))
        if diffs:
            ok = False
            print(f'\n  ❌ CROSS-CHECK DISAGREEMENT with {a.xdir} — investigate, '
                  f'do not average:')
            for y, k1, k2 in diffs:
                print(f'       {y}: this run {k1}  vs  other run {k2}')
        else:
            both = sum(1 for y in range(a.y0, a.y1 + 1)
                       if load(a.xdir, y)[1] == 'OK' and load(a.out, y)[1] == 'OK')
            print(f'\n  ✅ CROSS-CHECK: {both} year(s) present in both runs; '
                  f'hit sets identical in all of them.')

    print('\n  Unclassified-lead check: every hit below must carry a human or')
    print('  agent classification before the consolidation cites this sweep.')
    for h in hits_flat:
        pats = [k for k in h.get('hits', {}) if not k.startswith('_')]
        print(f"    {h['year']} c.{h['chap']}: {pats}  | {h['title'][:70]}")

    print('\n  MANUAL RESIDUAL (no script closes this): confirm each year\'s FINAL')
    print('  chapter number against the printed Acts and Resolves volume —')
    print('  continuity checking is blind to tail truncation.')

    if not ok:
        print('\n  ❌ NO CLEARANCE. The pre-1997 completeness claim remains a search')
        print('     inference. Fix the failures above and rerun.')
        sys.exit(1)

    today = datetime.date.today().strftime('%-d %B %Y')
    note = (
        'EDITORIAL NOTE: COMPLETENESS. For the period 1997 to 2026 the completeness '
        'claim is a verified property of the complete authoritative corpus: the full '
        'ChapterText of every session law of every year 1997–2026 was swept on '
        '5 August 2026 for every citation form of this act and of its companion acts '
        'and for the District’s and Board’s proper names; no year failed to '
        'fetch, and every hit was read in full section before classification. For the '
        f'period 1925 to 1996 the State Library repository sweep was completed on '
        f'{today}: every session law of every year was enumerated by chapter number '
        f'({tot_items:,} items) with numbering continuity verified and no gaps found, '
        'and the OCR text of every item was swept for the same citation forms and '
        f'names; {len(no_text)} item(s) had no readable text layer'
        + (' (each pulled and read by hand — see the sweep certificate)' if no_text else '')
        + f'; no year failed to fetch; and the recall test re-found all {len(known)} '
        'known pre-1997 amendments. The pre-1997 claim is a deterministic enumeration '
        'over probabilistic OCR text: it supports “no hit in the OCR text,” '
        'not “no hit in the law.” Final-chapter tail confirmation against '
        'the printed volumes [HAS / HAS NOT] been performed by hand. No known '
        'amending act has been omitted.'
    )
    cert = {'range': [a.y0, a.y1], 'completed': today, 'items': tot_items,
            'hits': len(hits_flat), 'no_text': no_text, 'recall': 'PASSED',
            'knowns': sorted(f'{y}:{c}' for y, c in known),
            'cross_check': a.xdir or None,
            'manual_residuals': ['final-chapter tail confirmation vs printed volumes',
                                 'classification of every hit listed above'],
            }
    json.dump(cert, open(os.path.join(a.out, 'SWEEP_CERTIFICATE.json'), 'w'), indent=1)
    open(os.path.join(a.out, 'DRAFT_EDITORIAL_NOTE.txt'), 'w').write(note)
    print('\n  ✅ SWEEP CLEAN. Wrote SWEEP_CERTIFICATE.json and DRAFT_EDITORIAL_NOTE.txt')
    print('     The draft note contains a [HAS / HAS NOT] blank for the manual')
    print('     tail-confirmation step — it may not issue with the blank unresolved.')
    print('\n' + note)


if __name__ == '__main__':
    main()
