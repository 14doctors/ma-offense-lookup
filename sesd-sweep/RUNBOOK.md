# SESD pre-1997 State Library sweep — Runbook

Operator's runbook for the parallel corpus sweep of the State Library of
Massachusetts digital repository (archives.lib.state.ma.us), years
**1925–1996**, for the South Essex Sewerage District consolidation
(c. 339 of the Acts of 1925 and its companion acts c. 431/1945,
c. 516/1969, c. 643/1972).

The 1997–2026 leg of the completeness claim is already complete and
warranted (Legislature API sweep, 5 August 2026). This run closes the
pre-1997 leg. Until the merge gate passes, the pre-1997 record rests on
the source collection as corrected by recital chains — a search
inference, not a swept corpus.

## What the sweep is, and what it can claim

Each year is swept in two layers:

1. **Enumeration is deterministic.** Every item titled `YYYY Chap. N` /
   `YYYY Resolve Chap. N` is listed and chapter-number continuity is
   checked. A numbering gap is a missing item — reported, never skipped.
   Continuity is blind to **tail truncation**: the final chapter number
   of each year must be confirmed against the printed Acts and Resolves
   volume by hand. No script closes that.
2. **Text is probabilistic OCR.** Each item's OCR text layer is scanned
   for every citation form of the four acts and for the District's and
   Board's proper names. A clean year means *"no hit in the OCR text"*,
   never *"no hit in the law."* `NO_TEXT` (no readable text layer) and
   `FETCH_FAIL` (couldn't retrieve) are distinct, and **neither is ever
   clean**.

A hit is a **lead, not a disposition** — classification is a separate
pass, and every classification is a draft until a human confirms it.

## Kit contents

| File | Role |
|---|---|
| `RUNBOOK.md` | This document — the operator's procedure |
| `CLAUDE.md` | Agent-orchestration prompt shipped with the kit (verbatim) |
| `shard_sweep.py` | Shard worker — sweeps one year range per process |
| `merge_verify.py` | Global merge gate — the only instrument that can make the 1925–1996 claim |
| `out/year_1925.json` … `out/year_1938.json` | Adopted baseline: fourteen clean years from the terminated serial run of 5–6 Aug 2026 |

Python 3 standard library only. No pip installs. The scripts and
detection patterns are **byte-identical** to the serial run launched
5 August 2026 — see hard rule 1.

## Hard rules — these override speed

1. **Do not edit the detection patterns.** They are byte-identical to an
   independent serial run; the two runs cross-check each other. A pattern
   changed in one run makes disagreement uninterpretable.
2. **FETCH_FAIL and NO_TEXT are never clean.** A year with either is
   open.
3. **A hit is a lead, not a disposition.** Agents classify; a human
   confirms.
4. **No shard and no agent may declare the sweep clean.** Only
   `merge_verify.py` over the full 1925–1996 range makes the global
   claim, and only a human may put its output into a compilation notice.
5. **Server politeness.** archives.lib.state.ma.us is a small public
   DSpace server. Max 4 workers per shard, max 8 shards, shard launches
   staggered by ~20 seconds. If FETCH_FAIL climbs, the server is
   shedding load: rerun the affected shard with `--workers 2` — never
   raise workers to push through. Failures manufactured by hammering the
   server cost more time than they save, because every one must be
   rerun.

## Phase 1 — run the shards

`out/` already contains completed, clean years; shards skip them
automatically (`--force` / `--force-years` override the skip). Launch
one agent per shard; each agent runs its command in the background,
polls its log, and reruns any RERUN year once before reporting.

| Agent | Command |
|---|---|
| shard-1925s | `python3 shard_sweep.py --from 1925 --to 1929 > log_1925s.txt 2>&1` |
| shard-1930s | `python3 shard_sweep.py --from 1930 --to 1939 > log_1930s.txt 2>&1` |
| shard-1940s | `python3 shard_sweep.py --from 1940 --to 1949 > log_1940s.txt 2>&1` |
| shard-1950s | `python3 shard_sweep.py --from 1950 --to 1959 > log_1950s.txt 2>&1` |
| shard-1960s | `python3 shard_sweep.py --from 1960 --to 1969 > log_1960s.txt 2>&1` |
| shard-1970s | `python3 shard_sweep.py --from 1970 --to 1979 > log_1970s.txt 2>&1` |
| shard-1980s | `python3 shard_sweep.py --from 1980 --to 1989 > log_1980s.txt 2>&1` |
| shard-1990s | `python3 shard_sweep.py --from 1990 --to 1996 > log_1990s.txt 2>&1` |

Expect roughly 3–6 minutes per non-skipped year; the whole run is
bounded by the largest shard — roughly an hour if the server
cooperates.

**Shard exit codes:** `0` clean shard · `2` shard recall failure (a
known amendment in range was not re-found — no clearance for the
affected years) · `3` one or more years need rerun or review
(RERUN status, FETCH_FAIL residue, or a numbering gap).

**Failure playbook:**

- FETCH_FAIL in a shard's summary lines → rerun that shard with
  `--workers 2`. The script already backs off to 2 workers on its
  internal retry passes; a persistent failure at 2 workers means wait,
  then retry — do not raise concurrency.
- A single bad year → `python3 shard_sweep.py --from YYYY --to YYYY`
  (add `--force` if a stale OK file exists for it).
- Year files are written atomically (`.tmp` then rename), so a killed
  shard never leaves a corrupt year file; just rerun the shard and it
  resumes past its clean years.

## Phase 2 — classify every hit

After its shard finishes, each agent classifies each hit in its own
range:

1. Read the hit's stored `ctx` snippets in `out/year_YYYY.json`. If a
   hit has no `ctx` or no `uuid` (files inherited from the prior run),
   rerun just that year:
   `python3 shard_sweep.py --from YYYY --to YYYY --force`.
   **Known case: 1934 has 4 hits inherited without contexts — the 1930s
   agent must rerun 1934 with `--force` and classify all 4. No known
   amendment exists in 1934, so these are either references or a
   genuine find.**
2. Where the snippet is not decisive, fetch the item's full OCR text
   (`shard_sweep.item_text(uuid)`) and read the whole chapter.
3. Classify each hit as exactly one of:
   - `AMENDMENT-CANDIDATE` — appears to amend c. 339/1925 or a
     companion act
   - `SUPPLEMENTAL-CANDIDATE` — standalone provision touching the
     District
   - `OTHER-STATUTE` — amends a different statute; reference only
   - `MERE-REFERENCE` — names the District/act without operating on it
   - `FALSE-POSITIVE` — OCR artifact or pattern coincidence
4. Write `report_<range>.md`: one row per hit — year, chapter,
   classification, the operative language **quoted**, and whether it
   already appears in the compilation's incorporated list, Supplemental
   appendix, or neither. **Any `AMENDMENT-CANDIDATE` or
   `SUPPLEMENTAL-CANDIDATE` not already in the compilation is a
   priority finding — put it at the top of the report.**

Classifications are drafts for human confirmation, not dispositions.

## Phase 3 — global verification, then STOP

When all eight shards report:

```
python3 merge_verify.py --out out --from 1925 --to 1996
```

Optional but valuable — if a second independent run's year files are
available, add `--cross-check <dir>`. Identical hit sets across two
independent executions is a real warranty upgrade; any disagreement is
a **defect to investigate, never to average away**.

`merge_verify.py` hard-fails (nonzero exit, NO CLEARANCE) on any of:

- a missing, unreadable, or RERUN year anywhere in 1925–1996;
- any FETCH_FAIL item;
- any chapter-number gap;
- a failed global recall test — all 27 known pre-1997 amendments must
  be re-found (list below).

`NO_TEXT` items do not fail the gate but are named residuals: each must
be pulled and read **by hand** before the claim issues.

On a clean run it writes `out/SWEEP_CERTIFICATE.json` and
`out/DRAFT_EDITORIAL_NOTE.txt`, then **stop and hand to the human**:

- the eight shard reports,
- the merge output including the unclassified-lead list,
- the draft editorial note — which contains a deliberate
  `[HAS / HAS NOT]` blank for the manual final-chapter tail
  confirmation. **Do not resolve that blank yourself**; it records a
  hand check against the printed volumes.

Two manual residuals survive a clean run by design: tail confirmation,
and human sign-off on every hit classification. The consolidations'
compilation notices may cite this sweep only after both.

## Global recall targets — the 27 known pre-1997 amendments

The sweep must re-find every one of these (year:chapter). They are
hard-coded identically in both scripts; `--known` overrides exist for
reuse on other projects, not for this one.

```
1927:36   1928:294  1929:22   1933:226  1933:335  1935:384  1945:169
1945:431  1945:492  1948:168  1956:468  1957:104  1958:216  1969:516
1972:190  1972:643  1973:430  1973:645  1974:735  1975:101  1978:493
1981:725  1985:170  1986:613  1989:618  1990:173  1993:116
```

## Status as of 6 August 2026

- The serial run from the compilation environment was **terminated**
  6 August 2026 to clear the repository server for the parallel run.
  Final state: **1925–1938 complete** — fourteen years, every year OK,
  no numbering gaps, no NO_TEXT, no fetch failures. Those fourteen
  year-files ship in `out/` as the kit's adopted baseline.
- Consequence worth recording: 1925–1938 rest on a single sweep
  execution. A second independent pass over those years (rerun with
  `--force`) is available as a discretionary cross-check but is not
  claimed.
- The parallel run is in flight under the reviewer's Claude Code
  session, reported at ten agents. The kit's design ceiling is eight
  shard agents at not more than four workers each; if the ten include
  classification or orchestration agents the design holds, but if ten
  sweep shards are running concurrently, watch the FETCH_FAIL counts —
  a climbing count means the server is shedding load, and the remedy is
  fewer workers per shard, never more.
- Completeness upgrade to all four compilation notices awaits the merge
  gate's certificate and recall test (Review Record No. 2, § 4).

## Provenance and related records

- Kit source: `sesd_statelib_parallel_sweep.zip`, project Drive folder
  `SESD` (uploaded 6 August 2026). This directory is the kit's contents
  verbatim plus this runbook.
- Project records (same Drive folder): *SESD Review Record No. 1*
  (§ 4 — sweep status at termination of the serial run) and *Review
  Record No. 2* (§ 4 — status table); the four consolidations issued
  5–6 August 2026; *SESD Amendment Inventory and Chain Map*.
- The DSpace REST endpoints used here are documented in this repo's
  `scraper/README.md` (PR #3), which first mapped the repository's API
  for the SESD annual-report scraper.
