"""
Comparative plot for the validation study — professional vs unprofessional,
averaged across the 7 use-case categories, for each rating question.

Renders a grouped bar chart with ±1 SEM error bars and direct value labels as a
standalone SVG (vector, paper-ready, opens in any browser, converts to PDF/PNG).
Pure stdlib — reuses the loading/stats functions in ``analyze.py`` so it stays in
sync as more responses arrive.

Usage (from user-study/):
    .venv/bin/python scripts/plot.py                       # writes analysis/comparison.svg
    .venv/bin/python scripts/plot.py --db study.server.db --out figure.svg
    .venv/bin/python scripts/plot.py --include-incomplete --keep-all-fields

Filtering flags mirror analyze.py (same test-participant exclusion by default).
"""

import argparse
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A  # noqa: E402

# Condition → categorical hue (validated blue/orange pair, colorblind-safe).
COLORS = {"professional": "#2a78d6", "unprofessional": "#eb6834"}
COND_ORDER = ["professional", "unprofessional"]

# Short, readable labels for the 7 use-case categories (fall back to a generated
# short form for any future category not listed here).
SHORT = {
    "advice-seeking-and-coping-strategies": "Advice & coping",
    "diagnosis-and-sense-making-of-symptoms": "Diagnosis & sense-making",
    "fear-of-judgment-and-safe-disclosure": "Fear of judgment",
    "general-emotional-support-and-validation": "Emotional support",
    "insight-building-and-meaning-making": "Insight building",
    "managing-interpersonal-and-romantic-relationships": "Relationships",
    "moments-of-emergency-and-crisis": "Emergency & crisis",
}


def short_cat(cat):
    if cat in SHORT:
        return SHORT[cat]
    s = cat.replace("-and-", " & ").replace("-", " ")
    return s[:26] + "…" if len(s) > 27 else s


# Compact row labels for the difference plot (full names live in the axis titles).
SHORT_MEASURE = {"a1": "Professionalism", "a2": "Clinical alignment"}


def paired_by_category(rows, key):
    """Per-category list of within-pair (professional − unprofessional) diffs."""
    cells, cat_of = defaultdict(dict), {}
    for r in rows:
        if r[key] is not None and r["condition"] in ("professional", "unprofessional"):
            k = (r["participant_id"], r["pair_key"])
            cells[k][r["condition"]] = r[key]
            cat_of[k] = r["category"]
    out = defaultdict(list)
    for k, d in cells.items():
        if "professional" in d and "unprofessional" in d:
            out[cat_of[k]].append(d["professional"] - d["unprofessional"])
    return out

# Design tokens (light chart surface — a paper figure commits to one mode).
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def sem(m):
    """Standard error of the mean from a summarize() dict."""
    if m["mean"] is None or m["n"] < 2:
        return 0.0
    return m["sd"] / math.sqrt(m["n"])


def build_svg(rows, measures, title, subtitle):
    W, H = 760, 480
    ml, mr, mt, mb = 64, 28, 96, 96  # margins
    plot_w = W - ml - mr
    plot_h = H - mt - mb
    y_min, y_max = 0, 7  # Likert floor at 0 keeps bars honest (no truncation)

    def y(v):
        return mt + plot_h * (1 - (v - y_min) / (y_max - y_min))

    parts = []
    a = parts.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" font-family=\'{FONT}\'>')
    a(f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>')

    # Title + subtitle
    a(f'<text x="{ml}" y="34" font-size="18" font-weight="600" fill="{INK}">{esc(title)}</text>')
    if subtitle:
        a(f'<text x="{ml}" y="55" font-size="12.5" fill="{INK_SECONDARY}">{esc(subtitle)}</text>')

    # Legend (top-right)
    lx = W - mr
    for cond in reversed(COND_ORDER):
        label = cond.capitalize()
        tw = 8.2 * len(label)
        lx -= tw + 16
        a(f'<rect x="{lx}" y="40" width="11" height="11" rx="2" fill="{COLORS[cond]}"/>')
        a(f'<text x="{lx + 16}" y="49.5" font-size="12.5" fill="{INK_SECONDARY}">{esc(label)}</text>')
        lx -= 4

    # Gridlines + y ticks
    for v in range(y_min, y_max + 1):
        yy = y(v)
        a(f'<line x1="{ml}" y1="{yy:.1f}" x2="{ml + plot_w}" y2="{yy:.1f}" '
          f'stroke="{GRID if v else BASELINE}" stroke-width="{1.4 if v == 0 else 1}"/>')
        a(f'<text x="{ml - 10}" y="{yy + 4:.1f}" font-size="11.5" text-anchor="end" '
          f'fill="{MUTED}">{v}</text>')
    a(f'<text x="16" y="{mt + plot_h / 2:.1f}" font-size="12" fill="{INK_SECONDARY}" '
      f'text-anchor="middle" transform="rotate(-90 16 {mt + plot_h / 2:.1f})">'
      f'Mean rating (1–7)</text>')

    # Grouped bars
    n_groups = len(measures)
    group_w = plot_w / n_groups
    n_bars = len(COND_ORDER)
    bar_w = min(64, (group_w * 0.62) / n_bars)
    gap = 4  # surface gap between adjacent bars

    for gi, (key, label) in enumerate(measures):
        gx = ml + group_w * gi + group_w / 2
        cluster_w = n_bars * bar_w + (n_bars - 1) * gap
        x0 = gx - cluster_w / 2
        stats = A.by_condition(rows, key)
        for bi, cond in enumerate(COND_ORDER):
            m = stats.get(cond, {"n": 0, "mean": None, "sd": None})
            bx = x0 + bi * (bar_w + gap)
            if m["mean"] is None:
                continue
            top = y(m["mean"])
            h = (mt + plot_h) - top
            a(f'<rect x="{bx:.1f}" y="{top:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
              f'rx="3" fill="{COLORS[cond]}"/>')
            # error bar (±1 SEM)
            e = sem(m)
            if e > 0:
                cx = bx + bar_w / 2
                yhi, ylo = y(m["mean"] + e), y(m["mean"] + -e)
                a(f'<line x1="{cx:.1f}" y1="{yhi:.1f}" x2="{cx:.1f}" y2="{ylo:.1f}" '
                  f'stroke="{INK_SECONDARY}" stroke-width="1.5"/>')
                for yy in (yhi, ylo):
                    a(f'<line x1="{cx - 4:.1f}" y1="{yy:.1f}" x2="{cx + 4:.1f}" y2="{yy:.1f}" '
                      f'stroke="{INK_SECONDARY}" stroke-width="1.5"/>')
            # direct value label
            a(f'<text x="{bx + bar_w / 2:.1f}" y="{y(m["mean"] + e) - 7:.1f}" '
              f'font-size="12" font-weight="600" text-anchor="middle" fill="{INK}">'
              f'{m["mean"]:.2f}</text>')
        # group label
        a(f'<text x="{gx:.1f}" y="{mt + plot_h + 24:.1f}" font-size="12.5" '
          f'text-anchor="middle" fill="{INK}">{esc(label)}</text>')

    # Footnote
    n = A.by_condition(rows, measures[0][0]).get("professional", {}).get("n", 0)
    a(f'<text x="{ml}" y="{H - 16}" font-size="11" fill="{MUTED}">'
      f'Bars = mean across {n} category-pairs · whiskers = ±1 SEM · 1–7 scale, higher = better</text>')

    a('</svg>')
    return "\n".join(parts)


def build_dumbbell(rows, measures, title, subtitle):
    """Per-category prof vs unprof levels — one connected-dot panel per measure."""
    cats = sorted({r["category"] for r in rows})
    ml, mr, mt, mb = 24, 24, 96, 56
    label_w, panel_gap = 176, 44
    W = 900
    n = len(cats)
    row_h = 46
    H = mt + n * row_h + mb
    plot_h = n * row_h
    avail = W - ml - mr - label_w - panel_gap * (len(measures) - 1)
    pw = avail / len(measures)

    def rx(px0, r):
        return px0 + pw * (r - 1) / 6  # rating 1..7 → x within panel

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family=\'{FONT}\'>',
             f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>']
    a = parts.append
    a(f'<text x="{ml}" y="34" font-size="18" font-weight="600" fill="{INK}">{esc(title)}</text>')
    if subtitle:
        a(f'<text x="{ml}" y="55" font-size="12.5" fill="{INK_SECONDARY}">{esc(subtitle)}</text>')

    # Legend
    lx = W - mr
    for cond in reversed(COND_ORDER):
        label = cond.capitalize()
        lx -= 8.2 * len(label) + 16
        a(f'<circle cx="{lx + 5}" cy="46" r="6" fill="{COLORS[cond]}"/>')
        a(f'<text x="{lx + 16}" y="50" font-size="12.5" fill="{INK_SECONDARY}">{esc(label)}</text>')
        lx -= 6

    # Category row labels (shared across panels)
    for ci, cat in enumerate(cats):
        cy = mt + ci * row_h + row_h / 2
        a(f'<text x="{ml}" y="{cy + 4:.1f}" font-size="12" fill="{INK}">{esc(short_cat(cat))}</text>')

    for mi, (key, label) in enumerate(measures):
        px0 = ml + label_w + mi * (pw + panel_gap)
        cats_stats = A.by_category(rows, key)
        # panel header
        a(f'<text x="{px0 + pw / 2:.1f}" y="{mt - 16:.1f}" font-size="12.5" font-weight="600" '
          f'text-anchor="middle" fill="{INK}">{esc(label)}</text>')
        # vertical gridlines + axis ticks (1,4,7)
        for v in range(1, 8):
            gx = rx(px0, v)
            a(f'<line x1="{gx:.1f}" y1="{mt:.1f}" x2="{gx:.1f}" y2="{mt + plot_h:.1f}" '
              f'stroke="{GRID}" stroke-width="1"/>')
            if v in (1, 4, 7):
                a(f'<text x="{gx:.1f}" y="{mt + plot_h + 20:.1f}" font-size="11" '
                  f'text-anchor="middle" fill="{MUTED}">{v}</text>')
        for ci, cat in enumerate(cats):
            cy = mt + ci * row_h + row_h / 2
            cstat = cats_stats.get(cat, {})
            p = cstat.get("professional", {}).get("mean")
            u = cstat.get("unprofessional", {}).get("mean")
            if p is None or u is None:
                continue
            xp, xu = rx(px0, p), rx(px0, u)
            a(f'<line x1="{xu:.1f}" y1="{cy:.1f}" x2="{xp:.1f}" y2="{cy:.1f}" '
              f'stroke="{BASELINE}" stroke-width="2.5"/>')
            a(f'<circle cx="{xu:.1f}" cy="{cy:.1f}" r="6" fill="{COLORS["unprofessional"]}"/>')
            a(f'<circle cx="{xp:.1f}" cy="{cy:.1f}" r="6" fill="{COLORS["professional"]}"/>')

    a(f'<text x="{ml}" y="{H - 18}" font-size="11" fill="{MUTED}">'
      f'Each row = one category · dots = mean rating (1–7) · connector = the gap</text>')
    a('</svg>')
    return "\n".join(parts)


def build_diff(rows, measures, title, subtitle):
    """Paired within-pair difference (professional − unprofessional) per measure:
    per-category dots, mean point, and ~95% CI whisker against a 0 reference."""
    ml, mr, mt, mb = 190, 40, 92, 80
    W = 760
    row_h = 96
    H = mt + len(measures) * row_h + mb
    d_min, d_max = -1, 6

    def dx(d):
        return ml + (W - ml - mr) * (d - d_min) / (d_max - d_min)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family=\'{FONT}\'>',
             f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>']
    a = parts.append
    a(f'<text x="{24}" y="34" font-size="18" font-weight="600" fill="{INK}">{esc(title)}</text>')
    if subtitle:
        a(f'<text x="{24}" y="55" font-size="12.5" fill="{INK_SECONDARY}">{esc(subtitle)}</text>')

    plot_top, plot_bot = mt, mt + len(measures) * row_h
    # x gridlines + ticks
    for d in range(d_min, d_max + 1):
        gx = dx(d)
        is0 = d == 0
        a(f'<line x1="{gx:.1f}" y1="{plot_top:.1f}" x2="{gx:.1f}" y2="{plot_bot:.1f}" '
          f'stroke="{INK_SECONDARY if is0 else GRID}" stroke-width="{1.5 if is0 else 1}" '
          f'{"stroke-dasharray=\"4 3\"" if is0 else ""}/>')
        a(f'<text x="{gx:.1f}" y="{plot_bot + 20:.1f}" font-size="11" text-anchor="middle" '
          f'fill="{MUTED}">{d:+d}</text>')
    a(f'<text x="{(ml + W - mr) / 2:.1f}" y="{plot_bot + 44:.1f}" font-size="12" text-anchor="middle" '
      f'fill="{INK_SECONDARY}">Difference in rating (professional − unprofessional)</text>')

    for mi, (key, label) in enumerate(measures):
        cy = mt + mi * row_h + row_h / 2
        a(f'<text x="{ml - 18:.1f}" y="{cy - 4:.1f}" font-size="12.5" font-weight="600" '
          f'text-anchor="end" fill="{INK}">{esc(SHORT_MEASURE.get(key, label))}</text>')
        # per-category dots (light), jittered vertically and deterministically
        by_cat = paired_by_category(rows, key)
        flat = [(cat, d) for cat, ds in sorted(by_cat.items()) for d in ds]
        k = len(flat)
        for i, (cat, d) in enumerate(flat):
            jit = (i - (k - 1) / 2) * 6 if k > 1 else 0
            a(f'<circle cx="{dx(d):.1f}" cy="{cy + jit:.1f}" r="4" fill="{COLORS["professional"]}" '
              f'fill-opacity="0.35"/>')
        # mean + ~95% CI
        diffs = A.paired_diffs(rows, key)
        if diffs:
            mean = sum(diffs) / len(diffs)
            m = A.summarize(diffs)
            e = 1.96 * sem(m)
            a(f'<line x1="{dx(mean - e):.1f}" y1="{cy:.1f}" x2="{dx(mean + e):.1f}" y2="{cy:.1f}" '
              f'stroke="{INK}" stroke-width="2"/>')
            for edge in (mean - e, mean + e):
                a(f'<line x1="{dx(edge):.1f}" y1="{cy - 6:.1f}" x2="{dx(edge):.1f}" y2="{cy + 6:.1f}" '
                  f'stroke="{INK}" stroke-width="2"/>')
            a(f'<circle cx="{dx(mean):.1f}" cy="{cy:.1f}" r="6.5" fill="{INK}"/>')
            a(f'<text x="{dx(mean):.1f}" y="{cy - 16:.1f}" font-size="12" font-weight="600" '
              f'text-anchor="middle" fill="{INK}">Δ {mean:+.2f}</text>')

    a(f'<text x="24" y="{plot_bot + 66:.1f}" font-size="11" fill="{MUTED}">'
      f'Dot = mean paired Δ · whisker ≈ 95% CI · faint dots = per-category Δ · dashed line = no difference</text>')
    a('</svg>')
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="study.server.db")
    ap.add_argument("--out-dir", default="analysis", help="directory for the SVG figures")
    ap.add_argument("--exclude-field", action="append", default=None)
    ap.add_argument("--keep-all-fields", action="store_true")
    ap.add_argument("--include-incomplete", action="store_true")
    args = ap.parse_args()

    exclude_fields = args.exclude_field if args.exclude_field is not None else A.DEFAULT_EXCLUDE_FIELDS
    participants, responses = A.load(args.db)
    kept_ids, _ = A.valid_participant_ids(
        participants, exclude_fields,
        require_submitted=not args.include_incomplete,
        apply_field_filter=not args.keep_all_fields,
    )
    rows = A.build_long(participants, responses, kept_ids)
    if not rows:
        sys.exit("no valid responses to plot yet")

    measures = [(k, v) for k, v in A.LIKERT.items()]
    n_cat = len({r["category"] for r in rows})
    n_clin = len(kept_ids)
    figures = {
        "comparison.svg": build_svg(
            rows, measures,
            "Professional vs unprofessional AI conduct",
            f"Averaged across {n_cat} use-case categories, {n_clin} clinician(s)"),
        "by-category.svg": build_dumbbell(
            rows, measures,
            "Ratings by use-case category",
            f"Professional vs unprofessional mean rating per category · {n_clin} clinician(s)"),
        "paired-diff.svg": build_diff(
            rows, measures,
            "Within-pair effect: professional − unprofessional",
            f"Each conversation pair rated by the same clinician · {n_clin} clinician(s)"),
    }
    os.makedirs(os.path.abspath(args.out_dir), exist_ok=True)
    for name, svg in figures.items():
        path = os.path.join(args.out_dir, name)
        with open(path, "w") as f:
            f.write(svg + "\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
