"""Render an aligned paste-up as a standalone HTML document."""

import html

from .match import Pair
from .segment import Unit
from .wdiff import PARA, DiffResult, Token, diff_units

STATUS_META = {
    "identical": ("IDENTICAL", "status-identical"),
    "different": ("DIFFERENCES", "status-different"),
    "left_only": ("HOUSE ONLY", "status-left"),
    "right_only": ("SENATE ONLY", "status-right"),
}

MODE_TITLES = {
    "standard": "Conference Paste-Up",
    "bond": "Bond Bill Conference Paste-Up",
    "charter": "Charter Paste-Up",
}


def render_tokens(marked: list[tuple[Token, bool]], css_class: str) -> str:
    out: list[str] = []
    for token, changed in marked:
        if token.text == PARA:
            out.append("<br><br>")
            continue
        piece = html.escape(token.text)
        if changed:
            piece = f'<mark class="{css_class}">{piece}</mark>'
        if token.space_before and out and not out[-1].endswith("<br><br>"):
            out.append(" ")
        out.append(piece)
    return "".join(out)


def _amount_flag(pair: Pair) -> str:
    left, right = pair.left, pair.right
    if not (left and right and left.kind == "line_item"):
        return ""
    if left.amount is None or right.amount is None or left.amount == right.amount:
        return ""
    delta = right.amount - left.amount
    sign = "+" if delta > 0 else "−"
    return (
        '<div class="amount-flag">&#9873; Amounts differ: House '
        f"${left.amount:,} vs Senate ${right.amount:,} "
        f"({sign}${abs(delta):,} Senate relative to House)</div>"
    )


def _side_html(unit: Unit | None, diff: DiffResult | None, side: str) -> str:
    if unit is None:
        return '<div class="cell empty">&mdash; no counterpart &mdash;</div>'
    if diff is None:
        body = render_tokens([(t, False) for t in _tok(unit)], "")
    else:
        marked = diff.left_marked if side == "left" else diff.right_marked
        css = "diff-left" if side == "left" else "diff-right"
        body = render_tokens(marked, css)
    return f'<div class="cell">{body}</div>'


def _tok(unit: Unit):
    from .wdiff import tokenize
    return tokenize(unit.text)


def render_html(pairs: list[Pair], mode: str, left_name: str, right_name: str,
                left_label: str = "House", right_label: str = "Senate") -> str:
    counts = {"identical": 0, "different": 0, "left_only": 0, "right_only": 0}
    amount_flags = 0
    rows: list[str] = []
    for i, pair in enumerate(pairs):
        status = pair.status
        counts[status] += 1
        badge_text, badge_class = STATUS_META[status]
        badge_text = badge_text.replace("HOUSE", left_label.upper()).replace("SENATE", right_label.upper())

        diff = None
        if status == "different":
            diff = diff_units(pair.left.text, pair.right.text)

        heading = (pair.left or pair.right).label
        right_heading = pair.right.label if pair.right else ""
        if pair.left and pair.right and pair.left.label != pair.right.label:
            heading = f"{pair.left.label} &nbsp;&harr;&nbsp; {right_heading}"

        unit = pair.left or pair.right
        is_container = unit.kind == "container"
        flag = _amount_flag(pair)
        if flag:
            amount_flags += 1

        if is_container and status == "identical":
            rows.append(
                f'<div class="band" data-status="{status}">'
                f'<span class="band-title">{html.escape(unit.label)}</span>'
                f'<span class="badge {badge_class}">{badge_text}</span></div>'
            )
            continue

        sim = f'<span class="sim">match confidence {pair.similarity:.0%}</span>' \
            if 0 < pair.similarity < 1 and status == "different" else ""
        rows.append(f"""
<section class="pair {'band-pair' if is_container else ''}" data-status="{status}" id="u{i}">
  <header>
    <span class="pair-title">{heading}</span>
    <span class="badge {badge_class}">{badge_text}</span>{sim}
  </header>
  {flag}
  <div class="columns">
    {_side_html(pair.left, diff, "left")}
    {_side_html(pair.right, diff, "right")}
  </div>
</section>""")

    title = MODE_TITLES.get(mode, "Paste-Up")
    flag_stat = (
        f'<div class="stat flagged"><b>{amount_flags}</b><span>amount flags</span></div>'
        if mode == "bond" else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}: {html.escape(left_name)} vs {html.escape(right_name)}</title>
<style>
  :root {{
    --ink: #1a1c22; --paper: #ffffff; --muted: #5b6272; --line: #e3e6ec;
    --left-mark: #ffe2a8; --right-mark: #c4e4ff;
    --identical: #2e7d32; --different: #b3541e; --only: #7b1fa2;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 15px/1.55 Georgia, 'Times New Roman', serif;
         color: var(--ink); background: #f4f5f8; }}
  .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px 20px 80px; }}
  h1 {{ font-size: 22px; margin: 0 0 2px; }}
  .subtitle {{ color: var(--muted); font-family: system-ui, sans-serif;
               font-size: 13px; margin-bottom: 18px; }}
  .stats {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0 6px;
            font-family: system-ui, sans-serif; }}
  .stat {{ background: var(--paper); border: 1px solid var(--line); border-radius: 8px;
           padding: 8px 14px; text-align: center; min-width: 96px; }}
  .stat b {{ display: block; font-size: 20px; }}
  .stat span {{ font-size: 11px; color: var(--muted); text-transform: uppercase;
                letter-spacing: .04em; }}
  .stat.flagged b {{ color: #b3261e; }}
  .controls {{ font-family: system-ui, sans-serif; font-size: 13px; margin: 10px 0 18px; }}
  .controls label {{ margin-right: 16px; cursor: pointer; }}
  .legend {{ font-family: system-ui, sans-serif; font-size: 12px; color: var(--muted);
             margin-bottom: 16px; }}
  .legend mark {{ padding: 0 4px; border-radius: 3px; }}
  mark.diff-left {{ background: var(--left-mark); }}
  mark.diff-right {{ background: var(--right-mark); }}
  .colheads {{ position: sticky; top: 0; z-index: 5; display: grid;
               grid-template-columns: 1fr 1fr; gap: 12px;
               font-family: system-ui, sans-serif; font-weight: 600; font-size: 13px;
               background: #f4f5f8; padding: 8px 2px; border-bottom: 2px solid var(--ink); }}
  .pair {{ background: var(--paper); border: 1px solid var(--line); border-radius: 8px;
           margin: 14px 0; overflow: hidden; }}
  .pair header {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
                  padding: 8px 14px; background: #fafbfd;
                  border-bottom: 1px solid var(--line);
                  font-family: system-ui, sans-serif; font-size: 13px; }}
  .pair-title {{ font-weight: 650; }}
  .sim {{ color: var(--muted); font-size: 11px; }}
  .badge {{ font-size: 10.5px; font-weight: 700; letter-spacing: .05em; padding: 2px 8px;
            border-radius: 20px; font-family: system-ui, sans-serif; }}
  .status-identical {{ background: #e5f2e6; color: var(--identical); }}
  .status-different {{ background: #fdeadd; color: var(--different); }}
  .status-left, .status-right {{ background: #f2e5f7; color: var(--only); }}
  .columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
  .cell {{ padding: 12px 16px; white-space: normal; overflow-wrap: anywhere; }}
  .columns .cell:first-child {{ border-right: 1px solid var(--line); }}
  .cell.empty {{ color: var(--muted); font-style: italic;
                 font-family: system-ui, sans-serif; font-size: 13px; }}
  .band {{ margin: 22px 0 10px; padding: 8px 14px; background: #232733; color: #fff;
           border-radius: 6px; font-family: system-ui, sans-serif; font-size: 13px;
           display: flex; gap: 12px; align-items: center; }}
  .band-title {{ font-weight: 700; letter-spacing: .03em; }}
  .band .badge {{ background: rgba(255,255,255,.15); color: #d7e6d8; }}
  .band-pair header {{ background: #232733; color: #fff; }}
  .amount-flag {{ font-family: system-ui, sans-serif; font-size: 13px; font-weight: 600;
                  color: #b3261e; background: #fdecea; padding: 6px 14px;
                  border-bottom: 1px solid var(--line); }}
  .hidden {{ display: none; }}
  @media (max-width: 800px) {{
    .columns {{ grid-template-columns: 1fr; }}
    .columns .cell:first-child {{ border-right: 0; border-bottom: 1px solid var(--line); }}
    .colheads {{ display: none; }}
  }}
  @media print {{
    body {{ background: #fff; }}
    .controls {{ display: none; }}
    .pair {{ break-inside: avoid; border-color: #999; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="subtitle">{left_label}: {html.escape(left_name)} &nbsp;&bull;&nbsp;
    {right_label}: {html.escape(right_name)} &nbsp;&bull;&nbsp;
    word-for-word comparison, sections matched by language</div>
  <div class="stats">
    <div class="stat"><b>{counts['different']}</b><span>with differences</span></div>
    <div class="stat"><b>{counts['identical']}</b><span>identical</span></div>
    <div class="stat"><b>{counts['left_only']}</b><span>{left_label} only</span></div>
    <div class="stat"><b>{counts['right_only']}</b><span>{right_label} only</span></div>
    {flag_stat}
  </div>
  <div class="controls">
    <label><input type="checkbox" id="only-diffs"> Show only differences</label>
  </div>
  <div class="legend">
    <mark class="diff-left">highlight</mark> = {left_label} language not in {right_label}
    &nbsp;&nbsp;<mark class="diff-right">highlight</mark> = {right_label} language not in {left_label}
  </div>
  <div class="colheads"><div>{left_label}</div><div>{right_label}</div></div>
  {''.join(rows)}
</div>
<script>
  document.getElementById('only-diffs').addEventListener('change', function () {{
    const hide = this.checked;
    document.querySelectorAll('.pair, .band').forEach(el => {{
      el.classList.toggle('hidden', hide && el.dataset.status === 'identical');
    }});
  }});
</script>
</body>
</html>"""
