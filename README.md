# Therapeutic Inquiries Taxonomy

This repository contains materials for a multi-part user study on therapeutic-style AI conversations.

The shared stimulus dataset and reusable study code live at the repository root. Phase-specific collected data and derived outputs live under the relevant phase directory. The currently implemented phase is the **Validation Study (Phase 1)**.

## Repository structure

- `data/`: shared JSON conversation stimuli, organized by inquiry category and pair.
- `background.md`: shared literature review, category rationale, and references used by the viewer.
- `docs/`: reusable static viewer/study UI source.
- `scripts/`: reusable build, server, analysis, and plotting scripts.
- `annotation-instructions/`: guidelines used to generate high/low sycophancy and anthropomorphism variants.
- `validation-study/`: Phase 1 validation-study outputs only.
  - `analysis/`: generated reports, CSV exports, and figures.
  - `collected-samples/`: collected SQLite response databases/backups.
  - `study.db*`: local/default SQLite response database files.

## Shared data format

Each conversation file is standalone:

```text
data/<category>/<pair>/a*.json
data/<category>/<pair>/b*.json
```

For the validation study, `a*` files are professional-condition conversations, and `b*` files are unprofessional-condition conversations. Each file includes:

- `condition`
- `turns`
- `metadata.reasons`

## Static viewer / study UI

GitHub Pages is built through `.github/workflows/pages.yml`. The workflow scans root `data/`, generates `_site/assets/site-data.js`, and deploys `_site`.

To build locally from the repository root:

```sh
node scripts/build-pages.mjs
```

Then open `_site/index.html`.

## Validation Study (Phase 1)

### Run the study server

**One-time setup**

```sh
python -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
```

**Run**

```sh
node scripts/build-pages.mjs
.venv/bin/python scripts/study-server.py
```

Open <http://localhost:5111/study.html>.

Responses are stored by default in `validation-study/study.db` (SQLite). To inspect:

```sh
sqlite3 validation-study/study.db "SELECT * FROM participants;"
sqlite3 validation-study/study.db "SELECT * FROM responses;"
```

### Analyze collected responses

`scripts/analyze.py` reads a validation-study DB and prints a manipulation-check report — professional (`a`) vs unprofessional (`b`) ratings on professionalism (`a1`) and clinical/ethical alignment (`a2`), the paired within-pair difference (Wilcoxon + sign test), problematic-flag rates, per-category means, and free-text concerns.

```sh
.venv/bin/python scripts/analyze.py --db validation-study/collected-samples/study-prolific.server.db
.venv/bin/python scripts/analyze.py --db validation-study/collected-samples/study-prolific.server.db \
  --report validation-study/analysis/report.md \
  --csv validation-study/analysis/responses_long.csv
```

Test/junk participants are dropped by default: only submitted participants are kept, and free-text `field` values containing `sadra`, `football`, or `test` are excluded. Adjust with `--exclude-field NAME` (repeatable), `--keep-all-fields`, or `--include-incomplete`.

`scripts/plot.py` renders SVG figures into `validation-study/analysis/` by default:

```sh
.venv/bin/python scripts/plot.py --db validation-study/collected-samples/study-prolific.server.db
```
