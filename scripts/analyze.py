"""
Analysis pipeline for the validation study — Phase 1.

Reads the SQLite database written by ``study-server.py`` and produces a
manipulation-check report: do clinicians rate the *professional* conversation
(underlying file ``a``) higher than the *unprofessional* one (file ``b``) on
professionalism and clinical/ethical alignment, and flag the unprofessional one
as problematic more often?

The pipeline is idempotent and incremental — run it again as more responses
land and it recomputes from whatever is currently in the DB.

Usage (from user-study/):
    .venv/bin/python scripts/analyze.py                        # print report to stdout
    .venv/bin/python scripts/analyze.py --db study.server.db
    .venv/bin/python scripts/analyze.py --report out/report.md --csv out/responses_long.csv

Filtering:
    Test/junk participants are dropped. By default a participant is included
    only if they finished the study (``submitted_at`` set) and their free-text
    ``field`` is not in the exclude list. Seed data from local testing used
    "Sadra" and "football" as the field, so those are excluded by default.

        --exclude-field NAME     drop participants whose field == NAME (repeatable,
                                 case-insensitive; default: Sadra, football)
        --include-incomplete     also include participants who never submitted
        --keep-all-fields        do not apply the field-based exclude list

Only stdlib is required (no pandas/scipy), so it runs against any Python 3.
"""

import argparse
import csv
import json
import math
import os
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict

# Underlying file → experimental condition. Per README: a* = professional, b* = unprofessional.
CONDITION = {"a": "professional", "b": "unprofessional"}

# Likert questions rated per conversation (1–7). b1 is a yes/no problematic flag.
LIKERT = {
    "a1": "Professionalism of AI conduct",
    "a2": "Alignment with clinical/ethical standards",
}

DEFAULT_EXCLUDE_FIELDS = ["sadra", "football"]


# ─── Loading & filtering ──────────────────────────────────────────────────────

def load(db_path):
    if not os.path.exists(db_path):
        sys.exit(f"error: database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    participants = [dict(r) for r in conn.execute("SELECT * FROM participants")]
    responses = [dict(r) for r in conn.execute("SELECT * FROM responses")]
    conn.close()
    return participants, responses


def valid_participant_ids(participants, exclude_fields, require_submitted, apply_field_filter):
    """Return (kept_ids, dropped) where dropped is a list of (pid, reason)."""
    excluded = {f.strip().lower() for f in exclude_fields}
    kept, dropped = set(), []
    for p in participants:
        pid = p["participant_id"]
        field = (p.get("field") or "").strip()
        if require_submitted and not p.get("submitted_at"):
            dropped.append((pid, f"incomplete (field={field or '—'!r})"))
            continue
        if apply_field_filter and field.lower() in excluded:
            dropped.append((pid, f"excluded field={field!r}"))
            continue
        kept.add(pid)
    return kept, dropped


def build_long(participants, responses, kept_ids):
    """One tidy row per rated conversation, joined with participant + condition."""
    by_id = {p["participant_id"]: p for p in participants}
    rows = []
    for r in responses:
        pid = r["participant_id"]
        if pid not in kept_ids:
            continue
        underlying = r["underlying_file"]
        pair_key = r["pair_key"]
        rows.append({
            "participant_id": pid,
            "field": (by_id.get(pid) or {}).get("field"),
            "pair_key": pair_key,
            "category": pair_key.split("/")[0],
            "pair_num": pair_key.split("/")[-1],
            "conv_label": r["conv_label"],
            "underlying_file": underlying,
            "condition": CONDITION.get(underlying, underlying),
            "a1": r["a1"],
            "a2": r["a2"],
            "b1_flagged": r["b1_flagged"],
            "b1_text": (r["b1_text"] or "").strip(),
        })
    return rows


# ─── Stats helpers (stdlib only) ──────────────────────────────────────────────

def summarize(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "mean": None, "sd": None}
    return {
        "n": len(vals),
        "mean": statistics.mean(vals),
        "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
    }


def sign_test_p(pos, neg):
    """Two-sided exact sign test p-value (ties excluded before calling)."""
    n = pos + neg
    if n == 0:
        return None
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def wilcoxon_p(diffs):
    """Wilcoxon signed-rank test, normal approximation with tie & continuity
    correction. Returns (W, z, p) or None if too few nonzero diffs."""
    nz = [d for d in diffs if d != 0]
    n = len(nz)
    if n < 6:  # normal approximation is unreliable below ~6; caller falls back to sign test
        return None
    ranks = _rank([abs(d) for d in nz])
    w_plus = sum(r for d, r in zip(nz, ranks) if d > 0)
    w_minus = sum(r for d, r in zip(nz, ranks) if d < 0)
    W = min(w_plus, w_minus)
    mean_w = n * (n + 1) / 4
    tie_term = _tie_correction([abs(d) for d in nz])
    var_w = (n * (n + 1) * (2 * n + 1) - tie_term) / 24
    if var_w <= 0:
        return None
    z = (W - mean_w + 0.5) / math.sqrt(var_w)  # continuity correction toward the mean
    p = 2 * _norm_sf(abs(z))
    return W, z, min(1.0, p)


def _rank(values):
    """Average ranks (1-based), ties share the mean of their rank span."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # 1-based average rank
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _tie_correction(values):
    total = 0
    for _, c in Counter(values).items():
        if c > 1:
            total += c ** 3 - c
    return total


def _norm_sf(x):
    """Upper-tail of the standard normal via erfc."""
    return 0.5 * math.erfc(x / math.sqrt(2))


# ─── Analyses ─────────────────────────────────────────────────────────────────

def by_condition(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[r["condition"]].append(r[key])
    return {cond: summarize(vals) for cond, vals in groups.items()}


def paired_diffs(rows, key):
    """Within participant×pair, professional_rating − unprofessional_rating.

    Each pair is shown to a participant as conversation A and B; one is the
    professional file and one the unprofessional. This yields a paired design.
    """
    cells = defaultdict(dict)  # (pid, pair_key) -> {condition: value}
    for r in rows:
        if r[key] is not None and r["condition"] in ("professional", "unprofessional"):
            cells[(r["participant_id"], r["pair_key"])][r["condition"]] = r[key]
    diffs = []
    for _, d in cells.items():
        if "professional" in d and "unprofessional" in d:
            diffs.append(d["professional"] - d["unprofessional"])
    return diffs


def flag_rate_by_condition(rows):
    counts = defaultdict(lambda: {"flagged": 0, "n": 0})
    for r in rows:
        f = r["b1_flagged"]
        if f is None:
            continue
        c = counts[r["condition"]]
        c["n"] += 1
        c["flagged"] += 1 if f else 0
    return counts


def by_category(rows, key):
    groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[r["category"]][r["condition"]].append(r[key])
    out = {}
    for cat, conds in sorted(groups.items()):
        out[cat] = {cond: summarize(vals) for cond, vals in conds.items()}
    return out


def demographics(participants, kept_ids):
    kept = [p for p in participants if p["participant_id"] in kept_ids]
    fields = ["field", "education", "licensed", "seeing_clients",
              "years_experience", "orientation", "ai_familiarity", "ai_appropriateness"]
    summary = {f: Counter((p.get(f) or "—") for p in kept) for f in fields}
    ages = [p["age"] for p in kept if p.get("age") is not None]
    return kept, summary, summarize(ages)


# ─── Reporting ────────────────────────────────────────────────────────────────

def fmt(m):
    if m["mean"] is None:
        return "  —   (n=0)"
    return f"{m['mean']:.2f} ± {m['sd']:.2f} (n={m['n']})"


def build_report(participants, responses, rows, kept_ids, dropped):
    L = []
    w = L.append

    w("# Validation Study — Analysis Report\n")

    # 1. Overview
    submitted = sum(1 for p in participants if p.get("submitted_at"))
    w("## 1. Data overview\n")
    w(f"- Participants in DB: **{len(participants)}** ({submitted} submitted, "
      f"{len(participants) - submitted} in progress)")
    w(f"- Participants kept for analysis: **{len(kept_ids)}**")
    w(f"- Rated conversations kept: **{len(rows)}** "
      f"(of {len(responses)} response rows in DB)")
    if dropped:
        w("- Dropped participants:")
        for pid, reason in dropped:
            w(f"    - `{pid}` — {reason}")
    w("")

    if not rows:
        w("_No valid responses to analyze yet._")
        return "\n".join(L)

    # 2. Sample / demographics
    kept, demo, age = demographics(participants, kept_ids)
    w("## 2. Sample\n")
    w(f"- Age: {fmt(age)}")
    for f, counter in demo.items():
        parts = ", ".join(f"{k}: {v}" for k, v in counter.most_common())
        w(f"- {f}: {parts}")
    w("")

    # 3. Manipulation check — the core result
    w("## 3. Manipulation check — professional vs unprofessional\n")
    w("Higher = better. Paired diff = professional − unprofessional (positive = "
      "professional rated higher, the expected direction).\n")
    for key, label in LIKERT.items():
        cond = by_condition(rows, key)
        prof = cond.get("professional", {"n": 0, "mean": None, "sd": None})
        unpr = cond.get("unprofessional", {"n": 0, "mean": None, "sd": None})
        diffs = paired_diffs(rows, key)
        w(f"### {key} — {label}\n")
        w(f"- Professional:   {fmt(prof)}")
        w(f"- Unprofessional: {fmt(unpr)}")
        if diffs:
            pos = sum(1 for d in diffs if d > 0)
            neg = sum(1 for d in diffs if d < 0)
            tie = sum(1 for d in diffs if d == 0)
            mean_d = statistics.mean(diffs)
            w(f"- Paired diff: mean **{mean_d:+.2f}** over {len(diffs)} pairs "
              f"({pos} favor professional, {neg} favor unprofessional, {tie} tied)")
            wil = wilcoxon_p(diffs)
            if wil:
                _, z, p = wil
                w(f"- Wilcoxon signed-rank: z={z:.2f}, p={p:.4f}")
            sp = sign_test_p(pos, neg)
            if sp is not None:
                w(f"- Sign test (exact): p={sp:.4f}")
        else:
            w("- Paired diff: not enough paired data yet")
        w("")

    # 4. Problematic-flag rate
    w("## 4. Problematic flag (b1) rate by condition\n")
    fr = flag_rate_by_condition(rows)
    for cond in ("professional", "unprofessional"):
        c = fr.get(cond)
        if c and c["n"]:
            pct = 100 * c["flagged"] / c["n"]
            w(f"- {cond}: {c['flagged']}/{c['n']} flagged ({pct:.0f}%)")
        else:
            w(f"- {cond}: no data")
    w("")

    # 5. By category
    w("## 5. By category (professional / unprofessional mean)\n")
    for key, label in LIKERT.items():
        w(f"### {key} — {label}\n")
        cats = by_category(rows, key)
        for cat, conds in cats.items():
            p = conds.get("professional", {}).get("mean")
            u = conds.get("unprofessional", {}).get("mean")
            ps = f"{p:.2f}" if p is not None else "—"
            us = f"{u:.2f}" if u is not None else "—"
            w(f"- {cat}: {ps} / {us}")
        w("")

    # 6. Qualitative flags
    flagged = [r for r in rows if r["b1_flagged"] and r["b1_text"]]
    w("## 6. Flagged concerns (free text)\n")
    if flagged:
        for r in flagged:
            w(f"- **[{r['condition']}]** {r['category']} — {r['participant_id']}: "
              f"\"{r['b1_text']}\"")
    else:
        w("_No free-text concerns recorded._")
    w("")

    return "\n".join(L)


def write_csv(rows, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    cols = ["participant_id", "field", "pair_key", "category", "pair_num",
            "conv_label", "underlying_file", "condition", "a1", "a2",
            "b1_flagged", "b1_text"]
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="study.server.db", help="SQLite DB (default: study.server.db)")
    ap.add_argument("--exclude-field", action="append", default=None,
                    help="drop participants whose field equals this (repeatable, case-insensitive)")
    ap.add_argument("--keep-all-fields", action="store_true",
                    help="do not apply the field-based exclude list")
    ap.add_argument("--include-incomplete", action="store_true",
                    help="also include participants who never submitted")
    ap.add_argument("--report", help="also write the markdown report to this path")
    ap.add_argument("--csv", help="also write a tidy long-format CSV to this path")
    args = ap.parse_args()

    exclude_fields = args.exclude_field if args.exclude_field is not None else DEFAULT_EXCLUDE_FIELDS

    participants, responses = load(args.db)
    kept_ids, dropped = valid_participant_ids(
        participants, exclude_fields,
        require_submitted=not args.include_incomplete,
        apply_field_filter=not args.keep_all_fields,
    )
    rows = build_long(participants, responses, kept_ids)

    report = build_report(participants, responses, rows, kept_ids, dropped)
    print(report)

    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w") as f:
            f.write(report + "\n")
        print(f"\n[wrote report → {args.report}]", file=sys.stderr)
    if args.csv:
        write_csv(rows, args.csv)
        print(f"[wrote csv → {args.csv}]", file=sys.stderr)


if __name__ == "__main__":
    main()
