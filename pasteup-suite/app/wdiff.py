"""Word- and punctuation-level diffing between two blocks of bill text.

Text is tokenized into words and individual punctuation marks, with each
token remembering whether whitespace preceded it in the original. The two
token streams are aligned with difflib, and each side is re-rendered from
its own tokens (so original spacing survives) with differing tokens marked.
"""

import difflib
import re
from dataclasses import dataclass

# A token is a word (allowing internal apostrophes/hyphens/periods, e.g.
# "G.L", "one-half", "commissioner's") or a single punctuation character.
TOKEN_RE = re.compile(r"[\w$]+(?:[.'’‐-―/-][\w]+)*|[^\w\s]")
PARA = "¶"  # paragraph-break sentinel token


@dataclass
class Token:
    text: str
    space_before: bool


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    paragraphs = re.split(r"\n\s*\n|\n", text)
    for p_index, para in enumerate(paragraphs):
        if p_index > 0:
            tokens.append(Token(PARA, space_before=False))
        for m in TOKEN_RE.finditer(para):
            start = m.start()
            space = start > 0 and para[start - 1].isspace()
            tokens.append(Token(m.group(), space_before=space))
    return tokens


def normalize(text: str) -> str:
    """Whitespace-insensitive form used for equality and similarity checks."""
    return " ".join(text.split()).lower()


@dataclass
class DiffResult:
    left_marked: list[tuple[Token, bool]]   # (token, is_difference)
    right_marked: list[tuple[Token, bool]]
    identical: bool
    ratio: float


def diff_units(left_text: str, right_text: str) -> DiffResult:
    left, right = tokenize(left_text), tokenize(right_text)
    a = [t.text for t in left]
    b = [t.text for t in right]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    left_marked: list[tuple[Token, bool]] = []
    right_marked: list[tuple[Token, bool]] = []
    identical = True
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        changed = op != "equal"
        if changed and (i2 > i1 or j2 > j1):
            identical = False
        left_marked.extend((t, changed) for t in left[i1:i2])
        right_marked.extend((t, changed) for t in right[j1:j2])
    return DiffResult(left_marked, right_marked, identical, sm.ratio())
