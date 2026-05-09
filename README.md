# MA Master Crime List — Offense Seriousness Lookup

A static lookup tool over the Massachusetts Sentencing Commission's
*Felony and Misdemeanor Master Crime List* (December 2015 edition,
2,186 offenses). Search by keyword, citation, or section number;
filter by seriousness level (1–9), penalty type, and Note K
(tentative) status. Click any offense to see its position on the
sentencing guidelines grid (Figure 3) with zone colors and
presumptive sentence ranges across all five criminal-history columns.

## What this is

- One static HTML file plus one JSON corpus file. No build step, no
  server, no framework, no dependencies.
- The JSON corpus is loaded once via `fetch()` on page load and is
  cached aggressively; subsequent searches are instant client-side
  filters.
- Designed for legislative-drafting reference use. Source-document
  caveats (2015 vintage, Note K tentative rankings) are surfaced in
  the UI rather than buried.
- Hostable unchanged on GitHub Pages, Vercel, Netlify, S3, or any
  other static host (the fetch path is relative).

## File layout

```
ma-offense-lookup/
├── index.html              # The app — UI, styles, and search logic
├── data/
│   └── crime_list.json     # Extracted corpus (compact array format)
├── .nojekyll               # Tells GitHub Pages to skip Jekyll processing
├── vercel.json             # Optional — cache headers if hosted on Vercel
├── .gitignore
└── README.md
```

## Deploy to GitHub Pages

GitHub Pages is the simplest path for this app. Two options:

### Option A — Web UI (no command line)

1. Create a new repository at https://github.com/new. Name it
   `ma-offense-lookup` (or anything you like). Make it Public if you
   want a free Pages site, or Private if you have a paid plan that
   supports private Pages.
2. On the new repo's page, click **uploading an existing file**.
   Drag the entire contents of this folder — `index.html`,
   `data/`, `.nojekyll`, all of it — into the upload area. Commit.
3. Go to **Settings → Pages**.
4. Under **Source**, select **Deploy from a branch**.
5. Under **Branch**, select **main** and **/ (root)**. Save.
6. Wait ~30–60 seconds. The page will show your live URL, typically
   `https://[your-username].github.io/ma-offense-lookup/`.

### Option B — Command line

```bash
cd ma-offense-lookup
git init
git add .
git commit -m "Initial commit"
gh repo create ma-offense-lookup --public --source=. --push
# Then in the GitHub UI: Settings → Pages → Source: Deploy from branch
# → Branch: main / (root) → Save
```

To update later:

```bash
# edit files, then:
git add .
git commit -m "Describe what you changed"
git push
# Pages re-deploys automatically within ~30 seconds
```

### After deploy — verify it worked

Visit the Pages URL. The app should load and show "Showing 2,186 of
2,186 offenses". If you see "Failed to load data: HTTP 404", check
the deployed file tree by visiting your Pages URL with
`/data/crime_list.json` appended — that file must return JSON, not
404. If it 404s, the `data/` directory wasn't pushed.

## Deploy to Vercel (alternative)

If you'd rather host on Vercel:

```bash
cd ma-offense-lookup
npx vercel             # follow prompts
npx vercel --prod      # promote to production
```

Or push to GitHub and connect the repo in the Vercel dashboard
(*Add New → Project → Import*). No framework preset; leave build
command empty; output directory = root. The included `vercel.json`
adds long-lived cache headers on `/data/*`.

## Local development

```bash
cd ma-offense-lookup
python3 -m http.server 3000
# open http://localhost:3000
```

You cannot just open `index.html` directly with `file://` — browsers
block `fetch()` on file:// origins. Use a local server.

## Updating the corpus

The corpus in `data/crime_list.json` is extracted from a 162-page
PDF. The compact array-of-arrays format is intentional — it's
~270 KB versus ~880 KB for the equivalent verbose JSON.

Format:

```json
{
  "fields":   ["level_number", "level_status", "notes", "offense_ref",
               "penalty_ref", "offense_title", "penalty_type",
               "staircase", "mand_time", "min_hc", "max_hc",
               "min_prison", "max_prison", "grid"],
  "status_map": {"F": "final", "T": "tentative", "C": "contingent"},
  "rows":      [["3", "F", "", "c. 265 s. 13A(a)", "", "A&B", "Misd.",
                 "", "", "", "2 1/2 years", "", "", "Yes"], ...]
}
```

To update with a newer Sentencing Commission publication, replace
`data/crime_list.json` and bump the date stamp in `index.html`'s
caveat banner. On GitHub Pages this propagates within a minute of
push; on Vercel the cache headers (1-day browser, 30-day CDN with
stale-while-revalidate) mean updates show up promptly without
explicit invalidation.

## Known caveats (also surfaced in the UI)

1. **December 2015 vintage.** Several material amendments since
   (e.g., domestic A&B felony enhancement St. 2014 c. 260; criminal
   justice reform St. 2018 c. 69; bail reform). Verify any specific
   penalty against current M.G.L.

2. **Note K — tentative rankings.** 372 of 2,186 entries (≈17%) are
   marked Note K — the Sentencing Commission published these as
   working classifications but never adopted them by full vote. They
   render in amber italics and can be hidden with the "Hide Note K"
   toggle.

3. **Extraction artifacts.** The corpus was extracted by
   character-level coordinate parsing from the source PDF. A small
   number of records have minor formatting irregularities (e.g.,
   wrapped-line citations that bled across columns). The offense
   title, level, citation, and penalty type are reliable; some
   staircase-factor and notes fields have residual fragments. Search
   treats all columns as one case-insensitive corpus, so this rarely
   affects findability.

4. **Keyword vocabulary mismatch.** The source uses MA-specific
   shorthand: `B&E` (not "breaking"), `OUI` (not "DUI"), `A&B` (not
   "battery"), `UFL` (unlawful firearm), etc. Searches for English
   concept words sometimes return zero hits. The empty-state hint
   surfaces a few common aliases; a deliberate synonym layer would be
   a worthwhile future addition.

5. **Sentencing grid is also 2015-vintage.** The grid shown in the
   reference panel is Figure 3 from the same December 2015
   publication. The MA grid hasn't been formally re-promulgated
   since. Treat the grid as a structural reference, not a current
   sentencing calculator.

## Source

Massachusetts Sentencing Commission, *Felony and Misdemeanor Master
Crime List: Reference List of Massachusetts Sentencing Laws and
Cases* (Dec. 2015). 162 pp. OCLC 945770334. Sentencing zones and
2/3-of-maximum parole rule are drawn from *Sentencing Guidelines:
Step 5, Chapter 5* (Mass.gov, April 26, 2019).
