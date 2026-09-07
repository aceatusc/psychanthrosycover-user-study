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
- `internal-study.db*`: local/default SQLite response database files written by `../scripts/internal-study-server.py`.

## Internal manipulation validation study

This separate internal study compares each fixed-anchor original conversation (`a.json` / `b.json`, i.e. professional/unprofessional anchors) against each changed version (`-hs`, `-ls`, `-ha`, `-la`). It asks only comparative ratings for human-likeness, sycophancy, and empathy; no Prolific or demographics are used.

Run from the repository root:

```bash
node scripts/build-pages.mjs
python3 scripts/internal-study-server.py --port 5222
# open http://localhost:5222/internal-study.html
```

Responses are saved to `validation-study/internal-study.db` by default. Progress is saved per username/session and the comparison order plus A/B placement are fixed for all researchers.

Useful API endpoints:

- `GET /progress?username=Sadra&session_id=<session>`
- `GET /health`
- `GET /agreement`
- `GET /agreement?users=Sadra,Yalda&dimensions=sycophancy,human_likeness`
- `GET /agreement?change_type=anthropomorphism&direction=increased`

Backward-compatible `/internal-*` aliases also work. The agreement endpoint returns per-rater-pair and pooled overall exact agreement / Cohen’s kappa, plus the exact comparison keys used for each agreement calculation.
