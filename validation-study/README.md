# Validation Study (Phase 1)

This directory is the phase-specific workspace for the validation study.

Shared stimuli and reusable code intentionally remain at the repository root:

- `../data/`
- `../docs/`
- `../scripts/`
- `../background.md`

This directory should hold only validation-study collected/derived items:

- `analysis/`: generated reports, CSV exports, and figures.
- `collected-samples/`: collected SQLite response databases/backups.
- `study.db*`: local/default SQLite response database files written by `../scripts/study-server.py`.
