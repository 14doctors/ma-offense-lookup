"""Paste-Up Suite — conference paste-up generator for Massachusetts bills.

Upload House and Senate versions (DOCX, PDF, or plain text), pick a
comparison mode (or let it auto-detect), and get a side-by-side word-level
paste-up as interactive HTML plus a downloadable Word document.
"""

import html
import os
import tempfile
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from .extract import ExtractionError, extract_text
from .match import match_bills
from .render_docx import render_docx
from .render_html import render_html
from .segment import MODES, parse_bill

app = FastAPI(title="Paste-Up Suite")

JOBS: dict[str, dict] = {}
MAX_JOBS = 50
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "pasteup-suite")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODE_CHOICES = [
    ("auto", "Auto-detect"),
    ("standard", "Standard bill (SECTION 1, 2, 3 …)"),
    ("bond", "Bond bill (SECTION 2/2A/2B containers with XXXX-XXXX items)"),
    ("charter", "Municipal charter (ARTICLE / Section)"),
]

INDEX_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paste-Up Suite</title>
<style>
  :root { --ink:#1a1c22; --muted:#5b6272; --line:#e3e6ec; --accent:#232733; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.6 system-ui,-apple-system,sans-serif; color:var(--ink);
         background:#f4f5f8; }
  .wrap { max-width:640px; margin:0 auto; padding:48px 20px; }
  h1 { font-size:26px; margin:0 0 4px; }
  .tag { color:var(--muted); margin-bottom:28px; }
  form { background:#fff; border:1px solid var(--line); border-radius:10px; padding:24px; }
  fieldset { border:0; padding:0; margin:0 0 18px; }
  label.head { display:block; font-weight:600; font-size:13px; text-transform:uppercase;
               letter-spacing:.05em; margin-bottom:6px; }
  input[type=file] { display:block; width:100%; padding:10px; border:1px dashed #b8bfcc;
                     border-radius:8px; background:#fafbfd; }
  select { width:100%; padding:9px 10px; border:1px solid var(--line); border-radius:8px;
           font:inherit; background:#fff; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  button { width:100%; padding:12px; border:0; border-radius:8px; background:var(--accent);
           color:#fff; font:600 15px/1 system-ui; cursor:pointer; }
  button:hover { background:#343a4c; }
  .hint { font-size:12.5px; color:var(--muted); margin-top:6px; }
  .err { background:#fdecea; color:#b3261e; border:1px solid #f5c6c0; border-radius:8px;
         padding:12px 14px; margin-bottom:18px; font-size:14px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Paste-Up Suite</h1>
  <div class="tag">Word-for-word conference paste-ups for Massachusetts bills —
    standard bills, capital bond bills, and municipal charters.</div>
  {error}
  <form method="post" action="/compare" enctype="multipart/form-data">
    <div class="row">
      <fieldset>
        <label class="head" for="left">House version</label>
        <input type="file" id="left" name="left" accept=".docx,.pdf,.txt" required>
      </fieldset>
      <fieldset>
        <label class="head" for="right">Senate version</label>
        <input type="file" id="right" name="right" accept=".docx,.pdf,.txt" required>
      </fieldset>
    </div>
    <fieldset>
      <label class="head" for="mode">Comparison mode</label>
      <select id="mode" name="mode">{mode_options}</select>
      <div class="hint">Auto-detect looks for XXXX-XXXX line items (bond bill) and
        ARTICLE headers (charter); otherwise it treats the file as a standard bill.</div>
    </fieldset>
    <button type="submit">Generate paste-up</button>
  </form>
</div>
</body>
</html>"""


def _index(error: str = "") -> str:
    options = "".join(
        f'<option value="{value}">{label}</option>' for value, label in MODE_CHOICES
    )
    err_html = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return INDEX_PAGE.replace("{mode_options}", options).replace("{error}", err_html)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _index()


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/compare")
async def compare(
    left: UploadFile = File(...),
    right: UploadFile = File(...),
    mode: str = Form("auto"),
):
    if mode not in ("auto", *MODES):
        raise HTTPException(status_code=400, detail=f"Unknown mode '{mode}'")
    try:
        left_text = extract_text(left.filename, await left.read())
        right_text = extract_text(right.filename, await right.read())
    except ExtractionError as exc:
        return HTMLResponse(_index(error=str(exc)), status_code=422)

    left_bill = parse_bill(left_text, mode)
    # Hold both chambers to the same shape: auto-detection runs on the House
    # file and the Senate file is parsed the same way.
    right_bill = parse_bill(right_text, left_bill.mode)

    pairs = match_bills(left_bill.units, right_bill.units)
    page = render_html(pairs, left_bill.mode, left.filename, right.filename)

    job_id = uuid.uuid4().hex[:12]
    docx_path = os.path.join(OUTPUT_DIR, f"pasteup-{job_id}.docx")
    render_docx(pairs, left_bill.mode, left.filename, right.filename, docx_path)

    while len(JOBS) >= MAX_JOBS:
        oldest = next(iter(JOBS))
        stale = JOBS.pop(oldest)
        if os.path.exists(stale["docx"]):
            os.unlink(stale["docx"])
    JOBS[job_id] = {"html": page, "docx": docx_path, "mode": left_bill.mode}
    return RedirectResponse(url=f"/result/{job_id}", status_code=303)


def _get_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Result not found — results are kept in memory and expire "
                   "when the server restarts. Re-run the comparison.",
        )
    return job


@app.get("/result/{job_id}", response_class=HTMLResponse)
def result(job_id: str) -> str:
    job = _get_job(job_id)
    toolbar = (
        '<div style="position:fixed;bottom:16px;right:16px;z-index:50;'
        'font-family:system-ui;font-size:13px">'
        f'<a href="/download/{job_id}" style="background:#232733;color:#fff;'
        'padding:10px 16px;border-radius:8px;text-decoration:none;'
        'box-shadow:0 2px 10px rgba(0,0,0,.25)">&#8595; Download Word (.docx)</a>'
        '&nbsp;<a href="/" style="background:#fff;color:#232733;padding:10px 16px;'
        'border-radius:8px;text-decoration:none;border:1px solid #c9ced9">New comparison</a>'
        "</div>"
    )
    return job["html"].replace("</body>", toolbar + "</body>")


@app.get("/download/{job_id}")
def download(job_id: str) -> FileResponse:
    job = _get_job(job_id)
    return FileResponse(
        job["docx"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"pasteup-{job['mode']}-{job_id}.docx",
    )
