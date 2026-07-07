# Paste-Up Suite

Word-for-word conference paste-ups for Massachusetts legislation, as a web
app. Upload the House and Senate versions of a bill (DOCX, PDF, or plain
text) and get a side-by-side comparison with every word- and
punctuation-level difference highlighted — as an interactive HTML page and a
downloadable Word document.

Consolidates three workflows into one tool with three modes:

| Mode | Document shape | Matching |
|---|---|---|
| **Standard bill** | `SECTION 1.`, `SECTION 2.`, … | Sections matched by language similarity, not section number, so chamber renumbering doesn't break alignment |
| **Bond bill** | `SECTION 2/2A/2B` appropriation containers holding `XXXX-XXXX` line items | Statutory sections by similarity; containers rendered as header bands; line items matched by account number, with a flag when the two chambers' dollar amounts diverge |
| **Charter** | `ARTICLE I` / `Section 1` hierarchy | Sections matched by article-qualified number first, then similarity |

Auto-detect picks the mode from the House file: `XXXX-XXXX` line items →
bond; `ARTICLE` headers → charter; otherwise standard.

## What the output shows

- Every section pair carries a status badge: **IDENTICAL**, **DIFFERENCES**,
  **HOUSE ONLY**, or **SENATE ONLY**.
- In differing sections, yellow highlights mark House language absent from
  the Senate version and blue (turquoise in Word) marks Senate language
  absent from the House version. Whitespace differences are ignored;
  punctuation differences are not.
- Renumbering alone is not a difference — section headers are stripped
  before comparison.
- Bond mode flags line items where the appropriation amount differs and
  shows the delta.
- A "show only differences" toggle hides identical sections; summary counts
  sit at the top. The page prints cleanly for markup by hand.

## Run locally

```bash
cd pasteup-suite
pip install -r requirements.txt
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

Generate demo document pairs and try them:

```bash
python samples/make_samples.py
```

Run the tests:

```bash
pip install pytest httpx
python -m pytest tests/ -q
```

## Deploy to Railway

This app lives in a subdirectory of the repo, so point Railway at it:

1. Create a new Railway project → **Deploy from GitHub repo** → select this
   repository.
2. In the service settings, set **Root Directory** to `pasteup-suite`.
   Railway will find the `Dockerfile` and `railway.json` there.
3. Generate a domain under **Settings → Networking**. No environment
   variables or database are required; Railway injects `PORT` automatically.

Every push to the deployed branch redeploys automatically.

> **Note on privacy:** engrossed bills are public documents, but if you
> ever feed this pre-release drafts, put the Railway service behind an
> access layer first (Railway's private networking + an auth proxy, or
> IP allowlisting). The app keeps results only in memory and a temp
> directory; nothing persists across restarts.

## Architecture

```
app/
├── main.py         FastAPI routes: upload form, compare, result, download
├── extract.py      DOCX (python-docx) and PDF (PyMuPDF) → plain text
├── segment.py      text → units: sections, containers, line items; mode auto-detect
├── match.py        House↔Senate alignment: exact keys, then greedy similarity
├── wdiff.py        word/punctuation tokenizer + difflib alignment
├── render_html.py  standalone HTML paste-up
└── render_docx.py  Word paste-up (two-column tables, highlighted runs)
```

The whole pipeline is deterministic — no AI calls, no per-request cost, and
the same two files always produce the same paste-up.
