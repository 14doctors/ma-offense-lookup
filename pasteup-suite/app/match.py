"""Align House and Senate units into paste-up pairs.

Statutory sections are matched by language similarity, not section number —
chambers renumber freely, so SECTION 12 in the House engrossment may be
SECTION 47 in the Senate's. Line items are matched by XXXX-XXXX account
number, and charter sections get first crack at an exact article/section
match before falling back to similarity.
"""

import difflib
from dataclasses import dataclass

from .segment import Unit
from .wdiff import normalize

# Minimum similarity for two sections to be treated as counterparts.
SIM_THRESHOLD = 0.42
# Bonus when both chambers use the same section number, to break ties
# between boilerplate-heavy sections that all look alike.
SAME_NUMBER_BONUS = 0.05
# Similarity is computed on at most this many characters; long sections are
# reliably matchable from their opening text.
SIM_PREFIX = 4000


@dataclass
class Pair:
    left: Unit | None      # House unit (or the base chamber)
    right: Unit | None     # Senate unit
    similarity: float = 0.0

    @property
    def status(self) -> str:
        if self.left is None:
            return "right_only"
        if self.right is None:
            return "left_only"
        if normalize(self.left.text_wo_number) == normalize(self.right.text_wo_number):
            return "identical"
        return "different"


def _text_wo_number(unit: Unit) -> str:
    """Unit text with its own header stripped, so renumbering alone does not
    register as a textual difference."""
    text = unit.text
    if unit.kind == "section" and unit.number:
        import re
        text = re.sub(r"^\s*SECTION\s+\S+\s*[.:]\s*", "", text, count=1, flags=re.IGNORECASE)
    return text


# Attach as a property so Pair.status can use it without circular imports.
Unit.text_wo_number = property(_text_wo_number)


def _similarity(a: Unit, b: Unit) -> float:
    ta = normalize(a.text_wo_number)[:SIM_PREFIX]
    tb = normalize(b.text_wo_number)[:SIM_PREFIX]
    if not ta or not tb:
        return 0.0
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    if sm.real_quick_ratio() < SIM_THRESHOLD:
        return sm.real_quick_ratio()
    if sm.quick_ratio() < SIM_THRESHOLD:
        return sm.quick_ratio()
    return sm.ratio()


def match_bills(left_units: list[Unit], right_units: list[Unit]) -> list[Pair]:
    pairs: list[Pair] = []
    used_right: set[int] = set()

    exact_pools = _exact_match_pools(left_units, right_units)

    # Pass 1: exact-key matches (line items by account number, containers and
    # preamble by label, charter sections by article/section number).
    exact_for_left: dict[int, tuple[int, float]] = {}
    for li, ri in exact_pools:
        if ri in used_right or li in exact_for_left:
            continue
        exact_for_left[li] = (ri, _similarity(left_units[li], right_units[ri]))
        used_right.add(ri)

    # Pass 2: similarity matching for everything still unmatched, best
    # candidates first (greedy global assignment).
    remaining_left = [i for i, u in enumerate(left_units)
                      if i not in exact_for_left and u.kind == "section"]
    remaining_right = [i for i, u in enumerate(right_units)
                       if i not in used_right and u.kind == "section"]
    candidates = []
    for li in remaining_left:
        for ri in remaining_right:
            score = _similarity(left_units[li], right_units[ri])
            if left_units[li].number and left_units[li].number == right_units[ri].number:
                score = min(1.0, score + SAME_NUMBER_BONUS)
            if score >= SIM_THRESHOLD:
                candidates.append((score, li, ri))
    candidates.sort(key=lambda c: -c[0])
    sim_for_left: dict[int, tuple[int, float]] = {}
    for score, li, ri in candidates:
        if li in sim_for_left or ri in used_right:
            continue
        sim_for_left[li] = (ri, score)
        used_right.add(ri)

    matched = {**exact_for_left, **sim_for_left}

    # Assemble output in left-bill order, splicing unmatched right units in
    # after the last right unit that found a partner before them.
    right_anchor: dict[int, int] = {}   # right index -> position in pairs list
    for li, left in enumerate(left_units):
        if li in matched:
            ri, score = matched[li]
            pairs.append(Pair(left, right_units[ri], score))
            right_anchor[ri] = len(pairs) - 1
        else:
            pairs.append(Pair(left, None))

    inserts: list[tuple[int, Pair]] = []
    for ri, right in enumerate(right_units):
        if ri in used_right:
            continue
        anchor = -1
        for prev in range(ri - 1, -1, -1):
            if prev in right_anchor:
                anchor = right_anchor[prev]
                break
        inserts.append((anchor, Pair(None, right)))
    for anchor, pair in sorted(inserts, key=lambda x: x[0], reverse=True):
        pairs.insert(anchor + 1, pair)
    return pairs


def _exact_match_pools(left_units: list[Unit], right_units: list[Unit]) -> list[tuple[int, int]]:
    """(left_index, right_index) pairs that share an exact identity key."""
    def key(u: Unit) -> tuple | None:
        if u.kind == "line_item":
            return ("item", u.number)
        if u.kind == "container":
            return ("container", u.number)
        if u.kind == "preamble":
            return ("preamble",)
        if u.kind == "section" and u.container is not None and u.number:
            return ("charter_section", u.number)   # already article-qualified
        return None

    right_by_key: dict[tuple, list[int]] = {}
    for ri, u in enumerate(right_units):
        k = key(u)
        if k is not None:
            right_by_key.setdefault(k, []).append(ri)

    pools: list[tuple[int, int]] = []
    for li, u in enumerate(left_units):
        k = key(u)
        if k is None:
            continue
        matches = right_by_key.get(k) or []
        if matches:
            pools.append((li, matches.pop(0)))
    return pools
