# Therapeutic Inquiries Taxonomy

This repository contains a small dataset of therapeutic-style LLM conversations, organized by inquiry category and paired professional/unprofessional variants.

## Structure

- `background.md`: literature review, summary, and references.
- `data/`: JSON conversation data.
- `docs/`: source files for the lightweight GitHub Pages viewer.
- `scripts/build-pages.mjs`: builds the static Pages artifact from the current `data/` directory.

Each conversation file is standalone:

```text
data/<category>/<pair>/a*.json
data/<category>/<pair>/b*.json
```

`a*` files are professional-condition conversations, and `b*` files are unprofessional-condition conversations. Each file includes:

- `condition`
- `turns`
- `metadata.reasons`

## Pages Viewer

GitHub Pages is built through `.github/workflows/pages.yml`. The workflow scans `data/` at build time, generates `_site/assets/site-data.js`, and deploys `_site`.

To build locally:

```sh
node scripts/build-pages.mjs
```

Then open `_site/index.html`.

## Validation Study (Phase 1)

**One-time setup**

```sh
cd user-study
python -m venv .venv
.venv/bin/pip install flask flask-cors
```

**Run**

```sh
node scripts/build-pages.mjs
.venv/bin/python scripts/study-server.py
```

Open <http://localhost:5111/study.html>.

Responses are stored in `user-study/study.db` (SQLite). To inspect:

```sh
sqlite3 study.db "SELECT * FROM participants;"
sqlite3 study.db "SELECT * FROM responses;"
```
