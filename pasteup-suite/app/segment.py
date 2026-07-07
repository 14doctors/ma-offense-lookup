"""Segment bill text into comparable units.

Three document shapes are supported:

- standard: Massachusetts bills organized as "SECTION 1.", "SECTION 2.", ...
- bond:     capital bond bills, where SECTION 2 / 2A / 2B are appropriation
            containers holding XXXX-XXXX line items, and everything else is
            an ordinary statutory section
- charter:  municipal charters organized as ARTICLE I / Section 1, with
            hierarchical numbering instead of flat SECTION numbers
"""

import re
from dataclasses import dataclass, field

SECTION_RE = re.compile(r"^\s*SECTION\s+(\d+[A-Z]{0,2})\s*[.:]", re.MULTILINE)
LINE_ITEM_RE = re.compile(r"^\s*(\d{4}[-–]\d{4})\b", re.MULTILINE)
ARTICLE_RE = re.compile(r"^\s*ARTICLE\s+([IVXLCDM]+|\d+[A-Z]?)\b[.:—\- ]*(.*)$", re.MULTILINE | re.IGNORECASE)
CHARTER_SECTION_RE = re.compile(r"^\s*SECTION\s+(\d+(?:[-.]\d+)*[A-Z]?)\b[.:—\- ]*(.*)$", re.MULTILINE | re.IGNORECASE)
DOLLAR_RE = re.compile(r"\$\s*([\d][\d,]*)")

# Bond-bill appropriation containers per the MA capital bill pattern.
BOND_CONTAINERS = {"2", "2A", "2B", "2C", "2D", "2E"}

MODES = ("standard", "bond", "charter")


@dataclass
class Unit:
    kind: str                 # 'preamble' | 'section' | 'container' | 'line_item'
    number: str | None        # section number, article-qualified number, or account number
    text: str                 # full text of the unit, header included
    container: str | None = None   # for line items: which SECTION 2/2A/2B they sit in
    heading: str = ""              # display heading
    amount: int | None = None      # for line items: appropriation amount in dollars
    order: int = 0

    @property
    def label(self) -> str:
        if self.kind == "line_item":
            return f"Item {self.number}"
        if self.kind == "container":
            return f"SECTION {self.number} (appropriation container)"
        if self.kind == "preamble":
            return "Preamble / title"
        return self.heading or f"SECTION {self.number}"


@dataclass
class ParsedBill:
    mode: str
    units: list[Unit] = field(default_factory=list)


def detect_mode(text: str) -> str:
    has_articles = ARTICLE_RE.search(text) is not None
    has_items = LINE_ITEM_RE.search(text) is not None
    if has_items:
        return "bond"
    if has_articles:
        return "charter"
    return "standard"


def parse_bill(text: str, mode: str = "auto") -> ParsedBill:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if mode == "auto":
        mode = detect_mode(text)
    if mode == "charter":
        units = _parse_charter(text)
    elif mode == "bond":
        units = _parse_sections(text, bond=True)
    else:
        units = _parse_sections(text, bond=False)
    for i, u in enumerate(units):
        u.order = i
    return ParsedBill(mode=mode, units=units)


def _parse_sections(text: str, bond: bool) -> list[Unit]:
    matches = list(SECTION_RE.finditer(text))
    units: list[Unit] = []
    if not matches:
        body = text.strip()
        if body:
            units.append(Unit(kind="section", number=None, text=body,
                              heading="Full text (no SECTION headers found)"))
        return units

    preamble = text[: matches[0].start()].strip()
    if preamble:
        units.append(Unit(kind="preamble", number=None, text=preamble))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        number = m.group(1).upper()
        body = text[m.start():end].strip()
        if bond and number in BOND_CONTAINERS and LINE_ITEM_RE.search(body):
            units.extend(_split_container(number, body))
        else:
            units.append(Unit(kind="section", number=number, text=body,
                              heading=f"SECTION {number}"))
    return units


def _split_container(number: str, body: str) -> list[Unit]:
    """Split a SECTION 2/2A/2B appropriation container into a header band
    plus one unit per XXXX-XXXX line item."""
    items = list(LINE_ITEM_RE.finditer(body))
    header = body[: items[0].start()].strip()
    units = [Unit(kind="container", number=number, text=header,
                  heading=f"SECTION {number}")]
    for i, m in enumerate(items):
        end = items[i + 1].start() if i + 1 < len(items) else len(body)
        item_text = body[m.start():end].strip()
        acct = m.group(1).replace("–", "-")
        units.append(Unit(kind="line_item", number=acct, text=item_text,
                          container=number, heading=f"Item {acct}",
                          amount=_last_amount(item_text)))
    return units


def _last_amount(text: str) -> int | None:
    amounts = DOLLAR_RE.findall(text)
    if not amounts:
        return None
    return int(amounts[-1].replace(",", ""))


def _parse_charter(text: str) -> list[Unit]:
    """Split charter text on ARTICLE and Section headers. Section numbers are
    qualified by their article (e.g. 'II/3') so Section 3 of Article II never
    collides with Section 3 of Article V."""
    boundaries = []
    for m in ARTICLE_RE.finditer(text):
        boundaries.append(("article", m))
    for m in CHARTER_SECTION_RE.finditer(text):
        boundaries.append(("section", m))
    boundaries.sort(key=lambda pair: pair[1].start())

    units: list[Unit] = []
    if not boundaries:
        body = text.strip()
        if body:
            units.append(Unit(kind="section", number=None, text=body,
                              heading="Full text (no ARTICLE/Section headers found)"))
        return units

    preamble = text[: boundaries[0][1].start()].strip()
    if preamble:
        units.append(Unit(kind="preamble", number=None, text=preamble))

    current_article = None
    current_article_title = ""
    for i, (kind, m) in enumerate(boundaries):
        end = boundaries[i + 1][1].start() if i + 1 < len(boundaries) else len(text)
        body = text[m.start():end].strip()
        if kind == "article":
            current_article = m.group(1).upper()
            current_article_title = (m.group(2) or "").strip()
            heading = f"ARTICLE {current_article}"
            if current_article_title:
                heading += f" — {current_article_title}"
            units.append(Unit(kind="container", number=current_article,
                              text=body, heading=heading))
        else:
            number = m.group(1)
            qualified = f"{current_article or '?'}/{number}"
            heading = f"Art. {current_article or '?'}, Section {number}"
            title = (m.group(2) or "").strip()
            if title:
                heading += f" — {title[:60]}"
            units.append(Unit(kind="section", number=qualified, text=body,
                              container=current_article, heading=heading))
    return units
