# MaloSound: continue independently

The website source lives at https://github.com/marcelozap/malosound.
Production is https://malosound.ai, hosted by Vercel from the master branch.
The chatgpt.site deployment is separate and is not evidence of production health.

## Open in a standalone website editor

Extract website-source.zip into a new folder. Open that folder in the editor.
The homepage is index.html; journal.js handles the calendar and selected entry;
journal.css handles styling. Content is JSON under content/.
The Python build has no requirement to call a ChatGPT model.

With Python 3 installed, run from the extracted folder:

```sh
python -X utf8 tools/build_website.py
python -m http.server 8080 --directory build
```

Open http://localhost:8080. Use HTTP, not a file:// page, because the journal
fetches JSON. The build may retrieve recordings from GitHub releases; a fully
offline audio package has not yet been prepared. Preserve those releases and
local recordings separately. The generated build/ directory is the static site
to import into an editor that accepts only HTML/CSS/JS assets.

## Publishing

Vercel's configured build command is python3 tools/build_website.py and its
output directory is build. Changes should be reviewed and committed on an
isolated branch, then integrated into master. Confirm the Vercel deployment
succeeded and inspect malosound.ai after publishing. Keep the existing DNS.
Access to GitHub, Vercel, the domain registrar, and their billing is independent
and must remain available through the owner's own accounts.

## Private material to preserve separately

- C:\MaloSound\Sessions\market-journal: private trade archive and reconciliation.
- C:\MaloSound\handoff\website: coordination notes and source-gap reports.
- Original broker exports and locally saved recordings.
- Archived XIV$ conversation exports used as source evidence.

These are not in the source ZIP. Keep a private second copy on another drive.
Do not import private broker files or chat transcripts into a public publish folder.

## Outstanding work

June and July currently use hourly market observations. September includes
minute observations. The desired UI is a thin line across the trading day.
Seven hourly observations cannot reconstruct September's minute-level detail.
The chart generator currently draws candles; the requested line conversion is
pending coordination with the chart owner.

Execution colors currently mean reviewed good/misplayed stretches. Do not
convert daily profit into execution quality. A separate trade-result mode needs
an agreed legend and verified per-trade timing and results before publication.
Existing unreviewed days remain unreviewed.

Missing dates in represented calendar months are selectable. Missing entries
and missing charts are distinct. Complete archive coverage, valid-date hash
handling, chart-load failures, and full desktop/mobile checks still need attention.

## Re-export

From a Git checkout, run:

```sh
python tools/export_portable_site.py C:\MaloSound\handoff\portable-next
```

Choose a new destination each time. The archive contains committed source only;
manifest.json records its commit and SHA-256 checksum. Preserve uncommitted work
separately before moving computers.
