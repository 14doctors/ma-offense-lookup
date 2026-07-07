from app.segment import detect_mode, parse_bill

STANDARD = """An Act about things.

SECTION 1. First section text.

SECTION 2. Second section text.

SECTION 2A. Inserted section text.
"""

BOND = """An Act financing things.

SECTION 1. Statutory intro.

SECTION 2. OFFICE OF EXAMPLE

1000-2026 For a program of example grants ................ $5,000,000

1000-2027 For another program ................ $2,500,000

SECTION 3. Reporting requirement.
"""

CHARTER = """An Act establishing a charter.

ARTICLE I - POWERS

SECTION 1. Body corporate.

ARTICLE II - COUNCIL

SECTION 1. Nine members.
"""


def test_detect_modes():
    assert detect_mode(STANDARD) == "standard"
    assert detect_mode(BOND) == "bond"
    assert detect_mode(CHARTER) == "charter"


def test_standard_segmentation():
    bill = parse_bill(STANDARD, "standard")
    numbers = [u.number for u in bill.units if u.kind == "section"]
    assert numbers == ["1", "2", "2A"]
    assert bill.units[0].kind == "preamble"


def test_bond_segmentation_splits_line_items():
    bill = parse_bill(BOND, "bond")
    items = [u for u in bill.units if u.kind == "line_item"]
    assert [i.number for i in items] == ["1000-2026", "1000-2027"]
    assert all(i.container == "2" for i in items)
    assert items[0].amount == 5_000_000
    assert items[1].amount == 2_500_000
    containers = [u for u in bill.units if u.kind == "container"]
    assert [c.number for c in containers] == ["2"]
    sections = [u.number for u in bill.units if u.kind == "section"]
    assert sections == ["1", "3"]


def test_charter_sections_are_article_qualified():
    bill = parse_bill(CHARTER, "charter")
    sections = [u.number for u in bill.units if u.kind == "section"]
    assert sections == ["I/1", "II/1"]
