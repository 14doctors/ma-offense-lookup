# SESD pre-1997 corpus sweep — parallel orchestration

You are orchestrating the completion of the State Library repository sweep
(1925–1996) for the South Essex Sewerage District consolidation (c. 339 of the
Acts of 1925). The 1997–2026 leg is already complete and warranted. This run
closes the pre-1997 leg. Work happens in three phases; the third ends with a
hard stop for human review.

## Hard rules — these override speed

1. **Do not edit the detection patterns.** They are byte-identical to an
   independent serial run; the two runs cross-check each other. A pattern
   changed in one run makes disagreement uninterpretable.
2. **FETCH_FAIL and NO_TEXT are never clean.** A year with either is open.
3. **A hit is a lead, not a disposition.** Agents classify; a human confirms.
4. **No shard and no agent may declare the sweep clean.** Only
   `merge_verify.py` over the full 1925–1996 range makes the global claim,
   and only a human may put its output into the compilation notice.
5. **Server politeness.** archives.lib.state.ma.us is a small public DSpace
   server. Max 4 workers per shard, max 8 shards. If FETCH_FAIL appears in a
   shard, rerun that shard with `--workers 2` — never raise workers to push
   through. Stagger shard launches by ~20 seconds.

## Phase 1 — run the shards (parallel agents, one per range)

`out/` already contains completed, clean years from the prior run — shards
skip them automatically. Launch one agent per shard; each agent runs its
command in the background, polls its log, and reruns any RERUN year once
before reporting.

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

Python 3 stdlib only — no pip installs. Expect roughly 3–6 minutes per
non-skipped year per shard; the whole run is bounded by the largest shard,
roughly an hour if the server cooperates. Exit codes: 0 clean shard,
2 shard recall failure, 3 years needing rerun.

## Phase 2 — classify every hit (same agents, their own decade)

After its shard finishes, each agent classifies each hit in its range:

1. Read the hit's stored `ctx` snippets in `out/year_YYYY.json`. If a hit has
   no `ctx` or no `uuid` (files inherited from the prior run), rerun just that
   year: `python3 shard_sweep.py --from YYYY --to YYYY --force`.
   **Known case: 1934 has 4 hits inherited without contexts — the 1930s agent
   must rerun 1934 with `--force` and classify all 4. No known amendment
   exists in 1934, so these are either references or a genuine find.**
2. Where the snippet is not decisive, fetch the item's full OCR text
   (`shard_sweep.item_text(uuid)`) and read the whole chapter.
3. Classify each hit as exactly one of:
   - `AMENDMENT-CANDIDATE` — appears to amend c. 339/1925 or a companion act
   - `SUPPLEMENTAL-CANDIDATE` — standalone provision touching the District
   - `OTHER-STATUTE` — amends a different statute; reference only
   - `MERE-REFERENCE` — names the District/act without operating on it
   - `FALSE-POSITIVE` — OCR artifact or pattern coincidence
4. Write `report_<range>.md`: one row per hit — year, chapter, classification,
   the operative language QUOTED, and whether it already appears in the
   compilation's incorporated list, Supplemental appendix, or neither.
   **Any `AMENDMENT-CANDIDATE` or `SUPPLEMENTAL-CANDIDATE` not already in the
   compilation is a priority finding — put it at the top of the report.**

Classifications are drafts for human confirmation, not dispositions.

## Phase 3 — global verification, then STOP

When all eight shards report:

```
python3 merge_verify.py --out out --from 1925 --to 1996
```

Optional but valuable — if a second independent run's year files are
available, add `--cross-check <dir>`; identical hit sets across two
independent executions is a real warranty upgrade, and any disagreement is a
defect to investigate, never to average away.

`merge_verify.py` hard-fails on: any missing/RERUN year, any FETCH_FAIL, any
numbering gap, or a failed global recall test (all 27 known pre-1997
amendments must be re-found). On a clean run it writes
`SWEEP_CERTIFICATE.json` and `DRAFT_EDITORIAL_NOTE.txt`.

Then **stop and hand to the human**:
- the eight shard reports,
- the merge output including the unclassified-lead list,
- the draft editorial note — which contains a deliberate `[HAS / HAS NOT]`
  blank for the manual final-chapter tail confirmation. Do not resolve that
  blank yourself; it records a hand check against the printed volumes.

Two manual residuals survive a clean run by design: tail confirmation, and
human sign-off on every hit classification. The consolidation's compilation
notice may cite this sweep only after both.
