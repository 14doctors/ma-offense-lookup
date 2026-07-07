from app.match import match_bills
from app.segment import parse_bill

HOUSE = """An Act.

SECTION 1. The registrar shall issue municipal road safety guidance to every city and town not later than March 1.

SECTION 2. Chapter 90 of the General Laws is hereby amended by inserting after section 17C the following section:- Section 17D. Speed limits in safety zones shall be 20 miles per hour.

SECTION 3. This act shall take effect on January 1, 2027.
"""

# Senate renumbers: its SECTION 2 is a new section; House SECTION 2 becomes
# Senate SECTION 3; effective date moves to SECTION 4 with a changed date.
SENATE = """An Act.

SECTION 1. The registrar shall issue municipal road safety guidance to every city and town not later than March 1.

SECTION 2. The department shall conduct a public awareness campaign concerning municipal road safety zones.

SECTION 3. Chapter 90 of the General Laws is hereby amended by inserting after section 17C the following section:- Section 17D. Speed limits in safety zones shall be 25 miles per hour.

SECTION 4. This act shall take effect on July 1, 2027.
"""


def _pairs():
    left = parse_bill(HOUSE, "standard").units
    right = parse_bill(SENATE, "standard").units
    return match_bills(left, right)


def test_sections_match_by_language_despite_renumbering():
    pairs = _pairs()
    by_left = {p.left.number: p for p in pairs if p.left and p.left.kind == "section"}
    assert by_left["2"].right is not None
    assert by_left["2"].right.number == "3"
    assert by_left["3"].right is not None
    assert by_left["3"].right.number == "4"


def test_senate_only_section_survives_as_right_only():
    pairs = _pairs()
    right_only = [p for p in pairs if p.status == "right_only"]
    assert len(right_only) == 1
    assert right_only[0].right.number == "2"


def test_renumbering_alone_is_not_a_difference():
    pairs = _pairs()
    by_left = {p.left.number: p for p in pairs if p.left and p.left.kind == "section"}
    # House 1 == Senate 1 verbatim: identical.
    assert by_left["1"].status == "identical"


def test_bond_line_items_match_by_account_number():
    house = parse_bill(
        "SECTION 2. OFFICE\n\n1000-2026 For grants ................ $5,000,000\n",
        "bond").units
    senate = parse_bill(
        "SECTION 2. OFFICE\n\n1000-2026 For grants and loans ................ $6,000,000\n",
        "bond").units
    pairs = match_bills(house, senate)
    item_pairs = [p for p in pairs if (p.left or p.right).kind == "line_item"]
    assert len(item_pairs) == 1
    assert item_pairs[0].status == "different"
    assert item_pairs[0].left.amount == 5_000_000
    assert item_pairs[0].right.amount == 6_000_000
