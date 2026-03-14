"""
thesis_analysis.py — Statistical analysis for ParliamentRAG master's thesis.

Calls the FastAPI backend and produces LaTeX tables, matplotlib/seaborn figures,
and a summary.txt covering 8 analysis sections.

Usage:
    python scripts/thesis_analysis.py
    # backend must be running at http://localhost:8000
"""

import json
import math
import os
import sys
import warnings
from collections import defaultdict
from io import StringIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from scipy import stats as scipy_stats

try:
    import seaborn as sns
except ImportError:
    sys.exit("seaborn not found. pip install seaborn")

try:
    import krippendorff
except ImportError:
    sys.exit("krippendorff not found. pip install krippendorff")

# ── Style ───────────────────────────────────────────────────────────────────────
SYSTEM_COLOR   = "#2196F3"
BASELINE_COLOR = "#FF9800"
EQUAL_COLOR    = "#9E9E9E"
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size":   11,
    "axes.grid":   True,
    "grid.alpha":  0.3,
    "figure.dpi":  150,
})

# ── Configuration ───────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
OUT_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

AUTOMATED_METRICS_LABELS = {
    "party_coverage":           "Groups with Citation (GC)",
    "response_completeness":    "Completeness",
    "citation_fidelity":        "Citation Faithfulness (CF)",
    "authority_utilization":    "Mean Authority (MA)",
    "authority_discrimination": "Authority Std Dev (ASD)",
}

CORE_DIMS    = ["answer_quality","answer_clarity","answer_completeness",
                "citations_relevance","balance_perception","balance_fairness"]
OPTIONAL_DIMS = ["source_relevance","source_authority","source_coverage"]

DIM_LABELS = {
    "answer_quality":       "Answer Quality",
    "answer_clarity":       "Answer Clarity",
    "answer_completeness":  "Answer Completeness",
    "citations_relevance":  "Citations Relevance",
    "balance_perception":   "Balance Perception",
    "balance_fairness":     "Balance Fairness",
    "source_relevance":     "Source Relevance",
    "source_authority":     "Source Authority",
    "source_coverage":      "Source Coverage",
    "overall_satisfaction": "Overall Satisfaction",
}

SUMMARY_LINES = []


def log(msg: str):
    print(msg)
    SUMMARY_LINES.append(msg)


# ── Math helpers ────────────────────────────────────────────────────────────────

def mean(vals):
    return sum(vals) / len(vals) if vals else float("nan")

def std(vals):
    if len(vals) < 2:
        return 0.0
    m = mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))

def ci95(vals):
    n = len(vals)
    if n == 0:
        return (float("nan"), float("nan"))
    if n == 1:
        return (vals[0], vals[0])
    m = mean(vals)
    s = std(vals)
    se = s / math.sqrt(n)
    t = 2.0 if n < 30 else 1.96
    return (m - t * se, m + t * se)

def cohens_d(sys_vals, base_vals):
    n1, n2 = len(sys_vals), len(base_vals)
    if n1 < 2 or n2 < 2:
        return float("nan")
    s1, s2 = std(sys_vals), std(base_vals)
    pooled = math.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    if pooled == 0:
        return float("nan")
    return (mean(sys_vals) - mean(base_vals)) / pooled

def d_category(d):
    if math.isnan(d):
        return "n/a"
    ad = abs(d)
    if ad < 0.2:  return "negligible"
    if ad < 0.5:  return "small"
    if ad < 0.8:  return "medium"
    return "large"

def fmt(val, decimals=2):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "---"
    return f"{val:.{decimals}f}"


# ── LaTeX helpers ───────────────────────────────────────────────────────────────

def booktabs_table(headers, rows, caption="", label=""):
    col_spec = "l" + "r" * (len(headers) - 1)
    lines = [
        r"\begin{table}[htbp]", r"\centering",
        f"\\caption{{{caption}}}", f"\\label{{{label}}}",
        r"\small", f"\\begin{{tabular}}{{{col_spec}}}",
        r"\toprule", " & ".join(headers) + r" \\", r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(str(c) for c in row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)

def save_tex(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> saved {os.path.relpath(path)}")

def save_fig(fig, name):
    """Save as both PDF and PNG."""
    for ext in ("pdf", "png"):
        p = os.path.join(OUT_DIR, f"{name}.{ext}")
        fig.savefig(p, bbox_inches="tight")
        print(f"  -> saved {os.path.relpath(p)}")
    plt.close(fig)


# ── Step 1: Data Extraction ─────────────────────────────────────────────────────

def fetch_data():
    log("=" * 60)
    log("STEP 1 — Fetching data from API")
    log("=" * 60)

    try:
        r = requests.get(f"{BASE_URL}/api/evaluation/dashboard", timeout=120)
        r.raise_for_status()
        dashboard = r.json()
    except Exception as e:
        sys.exit(f"Failed to fetch dashboard: {e}")

    with open(os.path.join(OUT_DIR, "raw_dashboard.json"), "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)
    log(f"  dashboard saved  ({len(json.dumps(dashboard))} chars)")

    try:
        r2 = requests.get(f"{BASE_URL}/api/evaluation/export/csv", timeout=120)
        r2.raise_for_status()
        csv_text = r2.text
    except Exception as e:
        sys.exit(f"Failed to fetch CSV export: {e}")

    with open(os.path.join(OUT_DIR, "raw_export.csv"), "w", encoding="utf-8") as f:
        f.write(csv_text)
    log(f"  CSV saved  ({len(csv_text)} chars)")

    try:
        r3 = requests.get(
            f"{BASE_URL}/api/surveys",
            params={"limit": 200, "include_stats": "false"},
            timeout=120,
        )
        r3.raise_for_status()
        surveys_resp = r3.json()
        all_surveys = [item["survey"] for item in surveys_resp.get("surveys", [])]
        log(f"  individual surveys fetched: {len(all_surveys)}")
    except Exception as e:
        warnings.warn(f"Failed to fetch surveys list: {e}")
        all_surveys = []

    return dashboard, csv_text, all_surveys


# ── De-blinding ─────────────────────────────────────────────────────────────────

def deblind_rating(rating_a, rating_b, preference, is_a_system):
    sys_r  = rating_a if is_a_system else rating_b
    base_r = rating_b if is_a_system else rating_a
    if preference == "A":
        pref_db = "system" if is_a_system else "baseline"
    elif preference == "B":
        pref_db = "baseline" if is_a_system else "system"
    else:
        pref_db = "equal"
    return sys_r, base_r, pref_db

def extract_survey_ratings(all_surveys):
    sys_ratings   = defaultdict(list)
    base_ratings  = defaultdict(list)
    pref_counts   = defaultdict(lambda: {"system": 0, "baseline": 0, "equal": 0})
    paired_by_dim = defaultdict(list)

    all_dims = CORE_DIMS + OPTIONAL_DIMS

    for s in all_surveys:
        ab = s.get("ab_assignment")
        if not ab:
            continue
        is_a_system = ab.get("A") == "system"
        ev_id   = s.get("evaluator_id") or "unknown"
        chat_id = s.get("chat_id", "")

        for dim in all_dims:
            dim_data = s.get(dim)
            if not dim_data or not isinstance(dim_data, dict):
                continue
            r_a  = dim_data.get("rating_a")
            r_b  = dim_data.get("rating_b")
            pref = dim_data.get("preference", "equal")
            if r_a is None or r_b is None:
                continue
            sr, br, pr = deblind_rating(r_a, r_b, pref, is_a_system)
            sys_ratings[dim].append(float(sr))
            base_ratings[dim].append(float(br))
            pref_counts[dim][pr] += 1
            paired_by_dim[dim].append((float(sr), float(br), ev_id, chat_id))

        sat_a = s.get("overall_satisfaction_a")
        sat_b = s.get("overall_satisfaction_b")
        overall_pref = s.get("overall_preference", "equal")
        if sat_a is not None and sat_b is not None:
            sr, br, pr = deblind_rating(sat_a, sat_b, overall_pref, is_a_system)
            sys_ratings["overall_satisfaction"].append(float(sr))
            base_ratings["overall_satisfaction"].append(float(br))
            pref_counts["overall_satisfaction"][pr] += 1
            paired_by_dim["overall_satisfaction"].append((float(sr), float(br), ev_id, chat_id))

    return dict(sys_ratings), dict(base_ratings), dict(pref_counts), dict(paired_by_dim)


# ── Section 1: Automated Metrics ────────────────────────────────────────────────

def analyse_automated(dashboard, df):
    log("\n" + "=" * 60)
    log("SECTION 1 — Automated Metrics (Level 1)")
    log("=" * 60)

    agg = dashboard.get("automated_aggregate", {})

    metric_csv_cols = {
        "party_coverage":           "party_coverage",
        "response_completeness":    "response_completeness",
        "citation_fidelity":        "citation_fidelity",
        "authority_utilization":    "authority_utilization",
        "authority_discrimination": "authority_discrimination",
    }

    sys_vals = {}
    if df is not None and not df.empty:
        for key, col in metric_csv_cols.items():
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce").dropna().tolist()
                if vals:
                    sys_vals[key] = vals

    if not sys_vals:
        field_map = {
            "party_coverage":           "party_coverage_score",
            "response_completeness":    "response_completeness",
            "citation_fidelity":        "verbatim_match_score",
            "authority_utilization":    "authority_utilization",
            "authority_discrimination": "authority_discrimination",
        }
        for chat in dashboard.get("per_chat", []):
            a = chat.get("automated", {})
            for key, field in field_map.items():
                v = a.get(field)
                if v is not None:
                    sys_vals.setdefault(key, []).append(float(v))

    baseline_map = {
        "party_coverage":           ("avg_baseline_party_coverage",         "ci_baseline_party_coverage"),
        "response_completeness":    ("avg_baseline_response_completeness",   "ci_baseline_response_completeness"),
        "citation_fidelity":        ("avg_baseline_citation_fidelity",       "ci_baseline_citation_fidelity"),
        "authority_utilization":    ("avg_baseline_authority",               "ci_baseline_authority"),
        "authority_discrimination": (None, None),
    }

    rows_tex = []
    results  = {}

    for key, label in AUTOMATED_METRICS_LABELS.items():
        vals = sys_vals.get(key, [])
        if not vals:
            warnings.warn(f"No data for automated metric '{key}', skipping.")
            continue
        m_sys = mean(vals)
        s_sys = std(vals)
        lo, hi = ci95(vals)
        bm_key, bci_key = baseline_map.get(key, (None, None))
        m_base = agg.get(bm_key) if bm_key else None
        b_ci   = agg.get(bci_key) if bci_key else None
        delta  = (m_sys - m_base) if m_base is not None else float("nan")

        sys_str   = f"{fmt(m_sys)} $\\pm$ {fmt(s_sys)} [{fmt(lo)}, {fmt(hi)}]"
        base_str  = (f"{fmt(m_base)} [{fmt(b_ci[0])}, {fmt(b_ci[1])}]"
                     if m_base is not None and b_ci and len(b_ci) == 2
                     else fmt(m_base) if m_base is not None else "---")
        delta_str = f"{'+' if delta >= 0 else ''}{fmt(delta)}" if not math.isnan(delta) else "---"

        rows_tex.append([label, sys_str, base_str, delta_str])
        results[key] = {"mean_sys": m_sys, "std_sys": s_sys, "ci": (lo, hi),
                        "mean_base": m_base, "delta": delta, "vals": vals}
        log(f"  {label}: mu={fmt(m_sys)} sigma={fmt(s_sys)} CI=[{fmt(lo)},{fmt(hi)}]"
            f"  baseline={fmt(m_base)}  delta={delta_str}")

    headers = ["Metric",
               r"ParliamentRAG ($\mu \pm \sigma$) [95\% CI]",
               r"NotebookLM ($\mu$) [95\% CI]",
               r"$\Delta$"]
    save_tex(os.path.join(OUT_DIR, "tab_automated_metrics.tex"),
             booktabs_table(headers, rows_tex,
                            caption=r"Automated metrics: ParliamentRAG vs.\ NotebookLM.",
                            label="tab:automated_metrics"))
    return results


# ── Section 2: Human Metrics (simplified stats) ──────────────────────────────────

def analyse_human(dashboard, all_surveys):
    log("\n" + "=" * 60)
    log("SECTION 2 — Human Survey Metrics (Level 2)")
    log("=" * 60)

    ab_agg = dashboard.get("ab_comparison") or {}
    sys_ratings, base_ratings, pref_counts, paired_by_dim = extract_survey_ratings(all_surveys)

    active_dims = list(CORE_DIMS)
    for d in OPTIONAL_DIMS:
        if d in sys_ratings and len(sys_ratings[d]) > 0:
            active_dims.append(d)
    log(f"  Active dimensions ({len(active_dims)}): {active_dims}")

    if not sys_ratings and ab_agg:
        log("  WARNING: no individual surveys, using aggregate from ab_comparison")
        for dim, m in (ab_agg.get("system_avg_ratings") or {}).items():
            sys_ratings[dim] = [m]
        for dim, m in (ab_agg.get("baseline_avg_ratings") or {}).items():
            base_ratings[dim] = [m]

    all_dims_plus_overall = active_dims + (
        ["overall_satisfaction"] if "overall_satisfaction" in sys_ratings else []
    )

    # Rating means table
    rows_ratings = []
    for dim in all_dims_plus_overall:
        sv = sys_ratings.get(dim, [])
        bv = base_ratings.get(dim, [])
        if not sv:
            continue
        rows_ratings.append([
            DIM_LABELS.get(dim, dim),
            f"{fmt(mean(sv))} $\\pm$ {fmt(std(sv))}",
            f"{fmt(mean(bv))} $\\pm$ {fmt(std(bv))}",
            str(len(sv)),
        ])
    save_tex(os.path.join(OUT_DIR, "tab_human_ratings.tex"),
             booktabs_table(
                 ["Dimension", r"ParliamentRAG ($\mu \pm \sigma$)", r"NotebookLM ($\mu \pm \sigma$)", "$n$"],
                 rows_ratings,
                 caption=r"Mean ratings (1--5) per dimension: ParliamentRAG vs.\ NotebookLM.",
                 label="tab:human_ratings"))

    # Simplified statistical test: Wilcoxon + Cohen's d only
    test_dims = [d for d in active_dims if d in sys_ratings and len(sys_ratings[d]) >= 2]
    w_stats, p_raws, d_vals = {}, {}, {}

    for dim in test_dims:
        pairs = paired_by_dim.get(dim, [])
        sv_p = [p[0] for p in pairs]
        bv_p = [p[1] for p in pairs]
        diffs = [s - b for s, b in zip(sv_p, bv_p)]
        if all(x == 0 for x in diffs):
            w_stats[dim], p_raws[dim] = 0.0, 1.0
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = scipy_stats.wilcoxon(sv_p, bv_p, alternative="two-sided")
                w_stats[dim] = res.statistic
                p_raws[dim]  = res.pvalue
            except Exception as ex:
                warnings.warn(f"Wilcoxon failed for {dim}: {ex}")
                w_stats[dim] = float("nan")
                p_raws[dim]  = float("nan")
        d_vals[dim] = cohens_d(sys_ratings[dim], base_ratings[dim])

    # Simplified stat summary (no Holm)
    sum_rows = []
    for dim in all_dims_plus_overall:
        sv = sys_ratings.get(dim, [])
        bv = base_ratings.get(dim, [])
        if not sv:
            continue
        delta = mean(sv) - mean(bv)
        d     = d_vals.get(dim, float("nan"))
        p_r   = p_raws.get(dim, float("nan"))
        W     = w_stats.get(dim, float("nan"))
        sum_rows.append([
            DIM_LABELS.get(dim, dim),
            fmt(mean(sv)), fmt(mean(bv)),
            f"{'+' if delta >= 0 else ''}{fmt(delta)}",
            fmt(W, 1) if not math.isnan(W) else "---",
            fmt(p_r, 4),
            fmt(d),
            d_category(d),
        ])
    save_tex(os.path.join(OUT_DIR, "tab_statistical_summary.tex"),
             booktabs_table(
                 ["Dimension", r"$\mu_\text{sys}$", r"$\mu_\text{base}$",
                  r"$\Delta$", r"$W$", r"$p$ (raw)", r"Cohen's $d$", "Effect"],
                 sum_rows,
                 caption=r"Statistical summary: Wilcoxon + Cohen's $d$ per dimension.",
                 label="tab:statistical_summary"))

    # Preference table
    for dim, pc in (ab_agg.get("per_dimension_preference") or {}).items():
        pref_counts[dim] = pc
    overall_pc = pref_counts.get("overall_satisfaction", {})
    n_sys  = overall_pc.get("system", 0)
    n_base = overall_pc.get("baseline", 0)
    n_tie  = overall_pc.get("equal", 0)
    n_decided = n_sys + n_base
    binom_p = scipy_stats.binomtest(n_sys, n_decided, p=0.5, alternative="two-sided").pvalue \
              if n_decided >= 1 else float("nan")
    log(f"\n  Overall preference: system={n_sys}, baseline={n_base}, tie={n_tie}")
    log(f"  Binomial test (excl. ties): p={fmt(binom_p, 4)}")

    pref_rows = []
    for dim in active_dims + (["overall_satisfaction"] if n_sys + n_base + n_tie > 0 else []):
        pc = pref_counts.get(dim, {})
        ns, nb, ne = pc.get("system", 0), pc.get("baseline", 0), pc.get("equal", 0)
        total = ns + nb + ne
        if total == 0:
            continue
        pref_rows.append([
            DIM_LABELS.get(dim, dim),
            f"{ns} ({100*ns/total:.0f}\\%)",
            f"{ne} ({100*ne/total:.0f}\\%)",
            f"{nb} ({100*nb/total:.0f}\\%)",
        ])
    save_tex(os.path.join(OUT_DIR, "tab_preferences.tex"),
             booktabs_table(
                 ["Dimension", "ParliamentRAG preferred", "Equal", "NotebookLM preferred"],
                 pref_rows,
                 caption="A/B preference counts per dimension (all evaluations).",
                 label="tab:preferences"))

    # Krippendorff alpha
    alpha_vals = {}
    for dim in active_dims:
        pairs = paired_by_dim.get(dim, [])
        if len(pairs) < 4:
            alpha_vals[dim] = float("nan")
            continue
        evaluators = sorted(set(p[2] for p in pairs))
        topics     = sorted(set(p[3] for p in pairs))
        ev_idx     = {e: i for i, e in enumerate(evaluators)}
        top_idx    = {t: j for j, t in enumerate(topics)}
        matrix     = np.full((len(evaluators), len(topics)), np.nan)
        for sys_r, _, ev_id, chat_id in pairs:
            i = ev_idx.get(ev_id)
            j = top_idx.get(chat_id)
            if i is not None and j is not None:
                matrix[i, j] = sys_r
        non_nan = [r for r in matrix if not np.all(np.isnan(r))]
        # count topics with >= 2 raters
        n_useful = sum(1 for j in range(matrix.shape[1])
                       if np.sum(~np.isnan(matrix[:, j])) >= 2)
        if len(non_nan) < 2:
            alpha_vals[dim] = float("nan")
            continue
        try:
            alpha_vals[dim] = krippendorff.alpha(reliability_data=matrix,
                                                  level_of_measurement="ordinal")
        except Exception as ex:
            warnings.warn(f"Krippendorff alpha failed for {dim}: {ex}")
            alpha_vals[dim] = float("nan")
        log(f"  Krippendorff alpha {dim}: {fmt(alpha_vals[dim], 3)}  (topics >=2 raters: {n_useful})")

    def alpha_interp(a):
        if math.isnan(a): return "---"
        if a < 0.667:     return "tentative"
        if a < 0.8:       return "acceptable"
        return "good"

    save_tex(os.path.join(OUT_DIR, "tab_agreement.tex"),
             booktabs_table(
                 ["Dimension", r"Krippendorff $\alpha$", "Interpretation"],
                 [[DIM_LABELS.get(d, d), fmt(alpha_vals.get(d, float("nan")), 3),
                   alpha_interp(alpha_vals.get(d, float("nan")))]
                  for d in active_dims],
                 caption=r"Inter-rater agreement (Krippendorff's $\alpha$, ordinal).",
                 label="tab:agreement"))

    return {
        "active_dims": active_dims,
        "sys_ratings": sys_ratings,
        "base_ratings": base_ratings,
        "pref_counts": pref_counts,
        "paired_by_dim": paired_by_dim,
        "w_stats": w_stats,
        "p_raws": p_raws,
        "d_vals": d_vals,
        "alpha_vals": alpha_vals,
        "binom_p": binom_p,
        "n_sys": n_sys,
        "n_base": n_base,
        "n_tie": n_tie,
    }


# ── Section 3: Per-Topic Analysis ───────────────────────────────────────────────

def analyse_per_topic(dashboard, all_surveys):
    log("\n" + "=" * 60)
    log("SECTION 3 — Analysis per Topic")
    log("=" * 60)

    # Build mapping chat_id -> topic label and automated metrics
    chat_meta = {}
    for chat in dashboard.get("per_chat", []):
        cid  = chat.get("chat_id") or chat.get("id", "")
        q    = chat.get("chat_query", "")[:50]
        auto = chat.get("automated", {})
        chat_meta[cid] = {
            "label":          q,
            "auth_sys":       auto.get("authority_utilization"),
            "auth_base":      auto.get("baseline_authority"),
            "n_citations_sys":  auto.get("n_citations"),
            "n_citations_base": auto.get("baseline_n_citations"),
            "party_coverage": auto.get("party_coverage_score"),
        }

    # Group surveys by chat_id (= topic)
    topic_surveys = defaultdict(list)
    for s in all_surveys:
        cid = s.get("chat_id", "")
        topic_surveys[cid].append(s)

    all_dims = CORE_DIMS + ["overall_satisfaction"]
    topic_rows = []

    for cid, surveys in sorted(topic_surveys.items()):
        label = chat_meta.get(cid, {}).get("label", cid[:30])
        n_eval = len(surveys)

        # De-blind and collect ratings
        sys_v_all, base_v_all = defaultdict(list), defaultdict(list)
        pref_sys = pref_base = pref_eq = 0
        for s in surveys:
            ab = s.get("ab_assignment")
            if not ab:
                continue
            is_a_system = ab.get("A") == "system"
            # overall preference
            op = s.get("overall_preference", "equal")
            if op == "A":
                pref_sym = "system" if is_a_system else "baseline"
            elif op == "B":
                pref_sym = "baseline" if is_a_system else "system"
            else:
                pref_sym = "equal"
            if pref_sym == "system":   pref_sys  += 1
            elif pref_sym == "baseline": pref_base += 1
            else:                        pref_eq   += 1

            for dim in CORE_DIMS + OPTIONAL_DIMS:
                dd = s.get(dim)
                if dd and isinstance(dd, dict):
                    ra, rb = dd.get("rating_a"), dd.get("rating_b")
                    if ra is not None and rb is not None:
                        sr, br, _ = deblind_rating(ra, rb, dd.get("preference", "equal"), is_a_system)
                        sys_v_all[dim].append(float(sr))
                        base_v_all[dim].append(float(br))
            # overall sat
            sa, sb = s.get("overall_satisfaction_a"), s.get("overall_satisfaction_b")
            if sa is not None and sb is not None:
                sr, br, _ = deblind_rating(sa, sb, s.get("overall_preference", "equal"), is_a_system)
                sys_v_all["overall_satisfaction"].append(float(sr))
                base_v_all["overall_satisfaction"].append(float(br))

        # Average across dims for this topic (use overall_satisfaction as summary)
        mean_sys  = mean(sys_v_all.get("overall_satisfaction", []))
        mean_base = mean(base_v_all.get("overall_satisfaction", []))
        delta     = mean_sys - mean_base if not math.isnan(mean_sys) and not math.isnan(mean_base) else float("nan")

        meta = chat_meta.get(cid, {})
        auth_sys  = meta.get("auth_sys")
        auth_base = meta.get("auth_base")

        topic_rows.append({
            "cid": cid, "label": label, "n_eval": n_eval,
            "mean_sys": mean_sys, "mean_base": mean_base, "delta": delta,
            "pref_sys": pref_sys, "pref_base": pref_base, "pref_eq": pref_eq,
            "auth_sys": auth_sys, "auth_base": auth_base,
            "sys_v_all": dict(sys_v_all), "base_v_all": dict(base_v_all),
        })
        log(f"  Topic '{label[:35]}': n={n_eval} mean_sys={fmt(mean_sys)} mean_base={fmt(mean_base)}"
            f"  delta={fmt(delta)}  pref S/E/B={pref_sys}/{pref_eq}/{pref_base}")

    if not topic_rows:
        warnings.warn("No per-topic data available.")
        return topic_rows

    # LaTeX table
    tex_rows = []
    for tr in topic_rows:
        label_short = tr["label"][:35]
        pref_str    = f"S:{tr['pref_sys']} E:{tr['pref_eq']} B:{tr['pref_base']}"
        delta_str   = f"{'+' if tr['delta'] >= 0 else ''}{fmt(tr['delta'])}" \
                      if not math.isnan(tr["delta"]) else "---"
        tex_rows.append([
            label_short,
            str(tr["n_eval"]),
            fmt(tr["mean_sys"]),
            fmt(tr["mean_base"]),
            delta_str,
            pref_str,
            fmt(tr["auth_sys"]),
            fmt(tr["auth_base"]),
        ])
    save_tex(os.path.join(OUT_DIR, "tab_per_topic.tex"),
             booktabs_table(
                 ["Topic", "$n$", r"$\mu_\text{sys}$", r"$\mu_\text{base}$",
                  r"$\Delta$", "Pref (S/E/B)", r"Auth$_\text{sys}$", r"Auth$_\text{base}$"],
                 tex_rows,
                 caption="Per-topic evaluation summary (overall satisfaction mean \\pm preferences).",
                 label="tab:per_topic"))

    # Heatmap: topic x dimension, colored by delta sys-base
    active_dims_for_heatmap = CORE_DIMS + OPTIONAL_DIMS + ["overall_satisfaction"]
    dim_labels_short = {
        "answer_quality":       "Quality",
        "answer_clarity":       "Clarity",
        "answer_completeness":  "Completeness",
        "citations_relevance":  "Cit. Rel.",
        "balance_perception":   "Bal. Perc.",
        "balance_fairness":     "Bal. Fair.",
        "source_relevance":     "Src. Rel.",
        "source_authority":     "Src. Auth.",
        "source_coverage":      "Src. Cov.",
        "overall_satisfaction": "Overall",
    }
    heat_data = []
    heat_labels = []
    for tr in topic_rows:
        row = []
        for dim in active_dims_for_heatmap:
            sv = tr["sys_v_all"].get(dim, [])
            bv = tr["base_v_all"].get(dim, [])
            if sv and bv:
                row.append(mean(sv) - mean(bv))
            else:
                row.append(float("nan"))
        heat_data.append(row)
        heat_labels.append(tr["label"][:30])

    heat_arr = np.array(heat_data, dtype=float)
    col_labels = [dim_labels_short.get(d, d) for d in active_dims_for_heatmap]

    if heat_arr.size > 0:
        fig, ax = plt.subplots(figsize=(max(8, len(col_labels) * 1.3), max(5, len(heat_labels) * 0.55)))
        sns.heatmap(heat_arr, ax=ax, annot=True, fmt=".2f", center=0,
                    cmap="RdBu", vmin=-1.5, vmax=1.5,
                    xticklabels=col_labels, yticklabels=heat_labels,
                    linewidths=0.5, linecolor="#cccccc",
                    cbar_kws={"label": "Delta (ParliamentRAG - NotebookLM)"})
        ax.set_title("Per-Topic Delta: ParliamentRAG - NotebookLM by Dimension")
        ax.set_xlabel("")
        ax.tick_params(axis="y", labelsize=8)
        plt.xticks(rotation=30, ha="right")
        save_fig(fig, "fig_heatmap_topics")

    # Topic preference bar chart
    if topic_rows:
        topic_labels = [tr["label"][:30] for tr in topic_rows]
        sys_pct  = [100 * tr["pref_sys"]  / max(tr["pref_sys"] + tr["pref_base"] + tr["pref_eq"], 1)
                    for tr in topic_rows]
        eq_pct   = [100 * tr["pref_eq"]   / max(tr["pref_sys"] + tr["pref_base"] + tr["pref_eq"], 1)
                    for tr in topic_rows]
        base_pct = [100 * tr["pref_base"] / max(tr["pref_sys"] + tr["pref_base"] + tr["pref_eq"], 1)
                    for tr in topic_rows]

        fig, ax = plt.subplots(figsize=(8, max(4, len(topic_labels) * 0.5)))
        y = np.arange(len(topic_labels))
        ax.barh(y, sys_pct,  0.6, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
        ax.barh(y, eq_pct,   0.6, left=sys_pct,          label="Equal",        color=EQUAL_COLOR,    alpha=0.7)
        ax.barh(y, base_pct, 0.6,
                left=[s + e for s, e in zip(sys_pct, eq_pct)],
                label="NotebookLM", color=BASELINE_COLOR, alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(topic_labels, fontsize=8)
        ax.set_xlabel("Percentage (%)")
        ax.set_xlim(0, 100)
        ax.axvline(50, color="black", linestyle="--", alpha=0.4)
        ax.set_title("Overall Preference per Topic")
        ax.legend(loc="lower right")
        plt.tight_layout()
        save_fig(fig, "fig_topic_preference")

    return topic_rows


# ── Section 4: Per-Evaluator Analysis ───────────────────────────────────────────

def analyse_per_evaluator(all_surveys):
    log("\n" + "=" * 60)
    log("SECTION 4 — Analysis per Evaluator")
    log("=" * 60)

    ev_data = defaultdict(lambda: {"sys": [], "base": [], "pref_sys": 0, "pref_base": 0,
                                   "pref_eq": 0, "topics": set()})
    for s in all_surveys:
        ab = s.get("ab_assignment")
        if not ab:
            continue
        ev_id       = s.get("evaluator_id") or "unknown"
        is_a_system = ab.get("A") == "system"
        cid         = s.get("chat_id", "")
        ev_data[ev_id]["topics"].add(cid)

        # overall preference
        op = s.get("overall_preference", "equal")
        if op == "A":
            pref_sym = "system" if is_a_system else "baseline"
        elif op == "B":
            pref_sym = "baseline" if is_a_system else "system"
        else:
            pref_sym = "equal"
        if pref_sym == "system":    ev_data[ev_id]["pref_sys"]  += 1
        elif pref_sym == "baseline": ev_data[ev_id]["pref_base"] += 1
        else:                        ev_data[ev_id]["pref_eq"]   += 1

        # ratings
        for dim in CORE_DIMS:
            dd = s.get(dim)
            if dd and isinstance(dd, dict):
                ra, rb = dd.get("rating_a"), dd.get("rating_b")
                if ra is not None and rb is not None:
                    sr, br, _ = deblind_rating(ra, rb, dd.get("preference", "equal"), is_a_system)
                    ev_data[ev_id]["sys"].append(float(sr))
                    ev_data[ev_id]["base"].append(float(br))

    tex_rows = []
    ev_order  = sorted(ev_data.keys())
    ev_summary = {}
    for ev_id in ev_order:
        d = ev_data[ev_id]
        n_t     = len(d["topics"])
        m_sys   = mean(d["sys"])
        m_base  = mean(d["base"])
        delta   = m_sys - m_base if not math.isnan(m_sys) and not math.isnan(m_base) else float("nan")
        total_p = d["pref_sys"] + d["pref_base"] + d["pref_eq"]
        pct_sys = 100 * d["pref_sys"] / total_p if total_p > 0 else float("nan")
        ev_summary[ev_id] = {"n_topics": n_t, "mean_sys": m_sys, "mean_base": m_base,
                              "delta": delta, "pct_sys": pct_sys}
        delta_str = f"{'+' if delta >= 0 else ''}{fmt(delta)}" if not math.isnan(delta) else "---"
        tex_rows.append([ev_id, str(n_t), fmt(m_sys), fmt(m_base), delta_str, fmt(pct_sys)])
        log(f"  {ev_id}: n={n_t} sys={fmt(m_sys)} base={fmt(m_base)} delta={delta_str} pct_sys={fmt(pct_sys)}%")

    save_tex(os.path.join(OUT_DIR, "tab_per_evaluator.tex"),
             booktabs_table(
                 ["Evaluator", r"$n_\mathrm{topics}$",
                  r"$\mu_\mathrm{sys}$", r"$\mu_\mathrm{base}$",
                  r"$\Delta$", "\\% pref sys"],
                 tex_rows,
                 caption="Per-evaluator rating summary (mean across all dimensions and topics).",
                 label="tab:per_evaluator"))

    if ev_summary:
        evs = list(ev_summary.keys())
        ms  = [ev_summary[e]["mean_sys"]  for e in evs]
        mb  = [ev_summary[e]["mean_base"] for e in evs]
        x   = np.arange(len(evs))
        w   = 0.35
        fig, ax = plt.subplots(figsize=(max(7, len(evs) * 1.2), 5))
        ax.bar(x - w/2, ms, w, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
        ax.bar(x + w/2, mb, w, label="NotebookLM",   color=BASELINE_COLOR, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(evs, rotation=20, ha="right")
        ax.set_ylabel("Mean Rating [1-5]")
        ax.set_ylim(0, 6)
        ax.set_title("Evaluator Bias: Mean Ratings Given (ParliamentRAG vs NotebookLM)")
        ax.legend()
        save_fig(fig, "fig_evaluator_bias")

    return ev_summary


# ── Section 5: Citation Analysis ────────────────────────────────────────────────

def analyse_citations(all_surveys):
    log("\n" + "=" * 60)
    log("SECTION 5 — Citation Quality Analysis")
    log("=" * 60)

    sys_cit  = {"relevance": [], "faithfulness": [], "informativeness": []}
    base_cit = {"relevance": [], "faithfulness": [], "informativeness": []}
    sys_attr  = {"correct": 0, "incorrect": 0, "unverifiable": 0}
    base_attr = {"correct": 0, "incorrect": 0, "unverifiable": 0}
    sys_issues  = defaultdict(int)
    base_issues = defaultdict(int)

    for s in all_surveys:
        ab = s.get("ab_assignment")
        if not ab:
            continue
        is_a_system = ab.get("A") == "system"

        for side, label in [("a", is_a_system), ("b", not is_a_system)]:
            target = sys_cit if label else base_cit
            attr   = sys_attr if label else base_attr
            issues = sys_issues if label else base_issues

            cits = s.get(f"citation_evaluations_{side}", [])
            if not isinstance(cits, list):
                continue
            for cit in cits:
                if not isinstance(cit, dict):
                    continue
                for metric in ("relevance", "faithfulness", "informativeness"):
                    v = cit.get(metric)
                    if v is not None:
                        try:
                            target[metric].append(float(v))
                        except (TypeError, ValueError):
                            pass
                atb = cit.get("attribution")
                if atb in attr:
                    attr[atb] += 1
                for issue in (cit.get("issues") or []):
                    if issue and issue != "none":
                        issues[issue] += 1

    log(f"  System citations evaluated: {len(sys_cit['relevance'])}")
    log(f"  Baseline citations evaluated: {len(base_cit['relevance'])}")

    # Quality table
    tex_rows = []
    for metric in ("relevance", "faithfulness", "informativeness"):
        sv = sys_cit[metric]
        bv = base_cit[metric]
        if not sv and not bv:
            continue
        ms  = mean(sv)
        mb  = mean(bv)
        delta = ms - mb if not math.isnan(ms) and not math.isnan(mb) else float("nan")
        delta_s = f"{'+' if delta >= 0 else ''}{fmt(delta)}" if not math.isnan(delta) else "---"
        tex_rows.append([metric.capitalize(), fmt(ms), fmt(mb), delta_s,
                          str(len(sv)), str(len(bv))])
        log(f"  {metric}: sys={fmt(ms)} base={fmt(mb)} delta={delta_s}")
    if tex_rows:
        save_tex(os.path.join(OUT_DIR, "tab_citation_quality.tex"),
                 booktabs_table(
                     ["Metric", r"System $\mu$", r"Baseline $\mu$", r"$\Delta$", "$n$ sys", "$n$ base"],
                     tex_rows,
                     caption="Citation quality: mean scores per metric (1-5 scale).",
                     label="tab:citation_quality"))

    # Figure: grouped bar relevance/faithfulness/informativeness
    metrics = [m for m in ("relevance", "faithfulness", "informativeness")
               if sys_cit[m] or base_cit[m]]
    if metrics:
        ms_vals = [mean(sys_cit[m])  for m in metrics]
        mb_vals = [mean(base_cit[m]) for m in metrics]
        x = np.arange(len(metrics))
        w = 0.35
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(x - w/2, ms_vals, w, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
        ax.bar(x + w/2, mb_vals, w, label="NotebookLM",   color=BASELINE_COLOR, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels([m.capitalize() for m in metrics])
        ax.set_ylabel("Mean Score [1-5]")
        ax.set_ylim(0, 6)
        ax.set_title("Citation Quality: ParliamentRAG vs NotebookLM")
        ax.legend()
        save_fig(fig, "fig_citation_comparison")

    # Attribution accuracy
    total_sys  = sum(sys_attr.values())
    total_base = sum(base_attr.values())
    log(f"  Attribution sys:  {sys_attr}  (total={total_sys})")
    log(f"  Attribution base: {base_attr}  (total={total_base})")
    if total_sys > 0 or total_base > 0:
        labels = ["correct", "incorrect", "unverifiable"]
        sys_pct  = [100 * sys_attr[l]  / max(total_sys,  1) for l in labels]
        base_pct = [100 * base_attr[l] / max(total_base, 1) for l in labels]
        x   = np.arange(len(labels))
        w   = 0.35
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(x - w/2, sys_pct,  w, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
        ax.bar(x + w/2, base_pct, w, label="NotebookLM",   color=BASELINE_COLOR, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels([l.capitalize() for l in labels])
        ax.set_ylabel("Percentage (%)")
        ax.set_ylim(0, 110)
        ax.set_title("Attribution Accuracy: ParliamentRAG vs NotebookLM")
        ax.legend()
        save_fig(fig, "fig_attribution_accuracy")

    # Issue prevalence
    all_issue_tags = sorted(set(list(sys_issues.keys()) + list(base_issues.keys())))
    if all_issue_tags:
        sys_counts  = [sys_issues.get(t, 0)  for t in all_issue_tags]
        base_counts = [base_issues.get(t, 0) for t in all_issue_tags]
        x = np.arange(len(all_issue_tags))
        w = 0.35
        fig, ax = plt.subplots(figsize=(max(7, len(all_issue_tags) * 1.3), 4))
        ax.bar(x - w/2, sys_counts,  w, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
        ax.bar(x + w/2, base_counts, w, label="NotebookLM",   color=BASELINE_COLOR, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels([t.replace("_", " ") for t in all_issue_tags], rotation=20, ha="right")
        ax.set_ylabel("Count")
        ax.set_title("Citation Issues: ParliamentRAG vs NotebookLM")
        ax.legend()
        save_fig(fig, "fig_citation_issues")

    return {"sys_cit": sys_cit, "base_cit": base_cit,
            "sys_attr": sys_attr, "base_attr": base_attr,
            "sys_issues": dict(sys_issues), "base_issues": dict(base_issues)}


# ── Section 6: Group Authority Analysis ─────────────────────────────────────────

def analyse_group_authority(all_surveys):
    log("\n" + "=" * 60)
    log("SECTION 6 — Group Authority Votes")
    log("=" * 60)

    # group_authority_votes: {party_name: -1 (A better) | 0 (equal) | 1 (B better)}
    # we de-blind to system/baseline
    group_votes = defaultdict(lambda: {"sys_better": 0, "equal": 0, "base_better": 0})

    for s in all_surveys:
        ab = s.get("ab_assignment")
        if not ab:
            continue
        is_a_system = ab.get("A") == "system"
        votes = s.get("group_authority_votes")
        if not isinstance(votes, dict):
            continue
        for party, v in votes.items():
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
            # -1 = A better, 0 = equal, 1 = B better
            if v == 0:
                group_votes[party]["equal"] += 1
            elif v == -1:
                # A is better
                if is_a_system:
                    group_votes[party]["sys_better"] += 1
                else:
                    group_votes[party]["base_better"] += 1
            elif v == 1:
                # B is better
                if is_a_system:
                    group_votes[party]["base_better"] += 1
                else:
                    group_votes[party]["sys_better"] += 1

    if not group_votes:
        warnings.warn("No group_authority_votes data found.")
        return {}

    parties = sorted(group_votes.keys())
    tex_rows = []
    for p in parties:
        d = group_votes[p]
        tex_rows.append([p, str(d["sys_better"]), str(d["equal"]), str(d["base_better"])])
        log(f"  {p}: sys_better={d['sys_better']} equal={d['equal']} base_better={d['base_better']}")

    save_tex(os.path.join(OUT_DIR, "tab_group_authority.tex"),
             booktabs_table(
                 ["Parliamentary Group", "ParliamentRAG Better", "Equal", "NotebookLM Better"],
                 tex_rows,
                 caption="Group authority votes: which system has better experts per parliamentary group.",
                 label="tab:group_authority"))

    # Horizontal stacked bar
    sys_v  = [group_votes[p]["sys_better"]  for p in parties]
    eq_v   = [group_votes[p]["equal"]        for p in parties]
    base_v = [group_votes[p]["base_better"] for p in parties]

    fig, ax = plt.subplots(figsize=(9, max(4, len(parties) * 0.55)))
    y = np.arange(len(parties))
    ax.barh(y, sys_v,  0.6, label="ParliamentRAG Better", color=SYSTEM_COLOR,   alpha=0.85)
    ax.barh(y, eq_v,   0.6, left=sys_v,                  label="Equal",        color=EQUAL_COLOR,    alpha=0.7)
    ax.barh(y, base_v, 0.6, left=[s + e for s, e in zip(sys_v, eq_v)],
            label="NotebookLM Better", color=BASELINE_COLOR, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(parties, fontsize=8)
    ax.set_xlabel("Number of votes")
    ax.set_title("Group Authority Votes per Parliamentary Group")
    ax.legend()
    plt.tight_layout()
    save_fig(fig, "fig_group_authority")

    return dict(group_votes)


# ── Section 7: Qualitative Feedback ─────────────────────────────────────────────

def analyse_feedback(all_surveys):
    log("\n" + "=" * 60)
    log("SECTION 7 — Qualitative Feedback")
    log("=" * 60)

    ev_feedback = defaultdict(lambda: {"positive": [], "improvement": [], "recommend": []})
    n_recommend_true  = 0
    n_recommend_false = 0

    for s in all_surveys:
        ev_id = s.get("evaluator_id") or "unknown"
        fp = s.get("feedback_positive")
        fi = s.get("feedback_improvement")
        wr = s.get("would_recommend")
        if fp:
            ev_feedback[ev_id]["positive"].append(fp.strip())
        if fi:
            ev_feedback[ev_id]["improvement"].append(fi.strip())
        if wr is True:
            n_recommend_true  += 1
            ev_feedback[ev_id]["recommend"].append("yes")
        elif wr is False:
            n_recommend_false += 1
            ev_feedback[ev_id]["recommend"].append("no")

    lines = ["=" * 60, "QUALITATIVE FEEDBACK REPORT", "=" * 60, ""]
    lines.append(f"Would recommend: YES={n_recommend_true}, NO={n_recommend_false}")
    lines.append("")
    for ev_id in sorted(ev_feedback.keys()):
        d = ev_feedback[ev_id]
        lines.append(f"{'='*40}")
        lines.append(f"Evaluator: {ev_id}  |  recommend: {', '.join(d['recommend']) or 'N/A'}")
        lines.append("POSITIVE:")
        for i, txt in enumerate(d["positive"], 1):
            lines.append(f"  {i}. {txt}")
        lines.append("IMPROVEMENT:")
        for i, txt in enumerate(d["improvement"], 1):
            lines.append(f"  {i}. {txt}")
        lines.append("")

    path = os.path.join(OUT_DIR, "feedback_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  -> saved {os.path.relpath(path)}")
    log(f"  would_recommend: yes={n_recommend_true}, no={n_recommend_false}")

    return {"n_yes": n_recommend_true, "n_no": n_recommend_false}


# ── Section 8: Completion Matrix ────────────────────────────────────────────────

def analyse_completion_matrix(all_surveys, dashboard):
    log("\n" + "=" * 60)
    log("SECTION 8 — Completion Matrix")
    log("=" * 60)

    # Build topic labels from dashboard
    topic_labels = {}
    for chat in dashboard.get("per_chat", []):
        cid = chat.get("chat_id") or chat.get("id", "")
        topic_labels[cid] = chat.get("chat_query", cid)[:35]

    evaluators = sorted(set((s.get("evaluator_id") or "unknown") for s in all_surveys))
    topics     = sorted(set(s.get("chat_id", "") for s in all_surveys))

    if not evaluators or not topics:
        warnings.warn("Not enough data for completion matrix.")
        return

    ev_idx  = {e: i for i, e in enumerate(evaluators)}
    top_idx = {t: j for j, t in enumerate(topics)}
    # 0=not evaluated, 1=system preferred, 2=equal/tie, 3=baseline preferred
    matrix  = np.zeros((len(evaluators), len(topics)), dtype=int)

    for s in all_surveys:
        ev_id = s.get("evaluator_id") or "unknown"
        cid   = s.get("chat_id", "")
        if ev_id not in ev_idx or cid not in top_idx:
            continue
        ab = s.get("ab_assignment") or {}
        is_a_system  = ab.get("A") == "system"
        overall_pref = s.get("overall_preference", "equal")
        _, _, pr = deblind_rating(0, 0, overall_pref, is_a_system)
        val = {"system": 1, "equal": 2, "baseline": 3}.get(pr, 2)
        matrix[ev_idx[ev_id], top_idx[cid]] = val

    completed = np.sum(matrix > 0)
    log(f"  Evaluators: {len(evaluators)}, Topics: {len(topics)}")
    log(f"  Total completed: {completed} / {matrix.size}"
        f"  ({100*completed/max(matrix.size,1):.1f}%)")

    topic_short = [topic_labels.get(t, t[:15]) for t in topics]
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch
    colors   = ["#F5F5F5", SYSTEM_COLOR, EQUAL_COLOR, BASELINE_COLOR]
    cmap_pref = ListedColormap(colors)
    norm      = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], ncolors=4)
    fig, ax = plt.subplots(figsize=(max(8, len(topics) * 0.7), max(3, len(evaluators) * 0.6)))
    ax.pcolormesh(matrix, cmap=cmap_pref, norm=norm, edgecolors="#cccccc", linewidth=0.5)
    ax.set_xticks(np.arange(len(topics)) + 0.5)
    ax.set_xticklabels(topic_short, rotation=35, ha="right", fontsize=7)
    ax.set_yticks(np.arange(len(evaluators)) + 0.5)
    ax.set_yticklabels(evaluators, fontsize=8)
    ax.invert_yaxis()
    legend_elements = [
        Patch(facecolor=SYSTEM_COLOR,   label="ParliamentRAG preferito"),
        Patch(facecolor=EQUAL_COLOR,    label="Pari"),
        Patch(facecolor=BASELINE_COLOR, label="NotebookLM preferita"),
        Patch(facecolor="#F5F5F5", edgecolor="#cccccc", label="Non valutato"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", bbox_to_anchor=(1.28, 1.02), fontsize=9)
    ax.set_title("Completion Matrix: Evaluator x Topic (colore = preferenza overall: ParliamentRAG/NotebookLM)")
    plt.tight_layout()
    save_fig(fig, "fig_completion_matrix")


# ── Existing figures ─────────────────────────────────────────────────────────────

def fig_automated_metrics(auto_results):
    keys   = list(auto_results.keys())
    labels = [AUTOMATED_METRICS_LABELS[k] for k in keys]
    sys_means  = [auto_results[k]["mean_sys"]  for k in keys]
    base_means = [auto_results[k]["mean_base"] if auto_results[k]["mean_base"] is not None else 0
                  for k in keys]
    sys_lo = [auto_results[k]["mean_sys"] - auto_results[k]["ci"][0] for k in keys]
    sys_hi = [auto_results[k]["ci"][1]   - auto_results[k]["mean_sys"] for k in keys]

    x, w = np.arange(len(keys)), 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - w/2, sys_means,  w, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
    ax.bar(x + w/2, base_means, w, label="NotebookLM",   color=BASELINE_COLOR, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Score [0, 1]")
    ax.set_ylim(0, 1.15)
    ax.set_title("Automated Metrics: ParliamentRAG vs. NotebookLM")
    ax.legend()
    save_fig(fig, "fig_automated_metrics")


def fig_human_ratings(human_results):
    dims      = human_results["active_dims"]
    labels    = [DIM_LABELS.get(d, d) for d in dims]
    sys_means  = [mean(human_results["sys_ratings"].get(d, [])) for d in dims]
    base_means = [mean(human_results["base_ratings"].get(d, [])) for d in dims]
    sys_stds   = [std(human_results["sys_ratings"].get(d, [])) for d in dims]
    base_stds  = [std(human_results["base_ratings"].get(d, [])) for d in dims]

    x, w = np.arange(len(dims)), 0.35
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - w/2, sys_means,  w, yerr=sys_stds,  label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85, capsize=4)
    ax.bar(x + w/2, base_means, w, yerr=base_stds, label="NotebookLM",   color=BASELINE_COLOR, alpha=0.85, capsize=4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Mean Rating [1-5]")
    ax.set_ylim(0, 6)
    ax.set_title("Human Ratings: ParliamentRAG vs. NotebookLM (mean +/- SD)")
    ax.legend()
    save_fig(fig, "fig_human_ratings")


def fig_preference_distribution(human_results):
    all_dims    = human_results["active_dims"]
    pref_counts = human_results["pref_counts"]
    has_overall = "overall_satisfaction" in pref_counts
    if has_overall:
        all_dims = all_dims + ["overall_satisfaction"]

    labels, sys_pct, eq_pct, base_pct = [], [], [], []
    for dim in all_dims:
        pc = pref_counts.get(dim, {})
        ns, ne, nb = pc.get("system", 0), pc.get("equal", 0), pc.get("baseline", 0)
        total = ns + ne + nb
        if total == 0:
            continue
        labels.append(DIM_LABELS.get(dim, dim))
        sys_pct.append(100 * ns / total)
        eq_pct.append(100 * ne / total)
        base_pct.append(100 * nb / total)

    fig, ax = plt.subplots(figsize=(9, max(3, 0.55 * len(labels) + 1)))
    y = np.arange(len(labels))
    ax.barh(y, sys_pct,  0.6, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
    ax.barh(y, eq_pct,   0.6, left=sys_pct,          label="Equal",        color=EQUAL_COLOR,    alpha=0.7)
    ax.barh(y, base_pct, 0.6,
            left=[s + e for s, e in zip(sys_pct, eq_pct)],
            label="NotebookLM", color=BASELINE_COLOR, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Percentage (%)")
    ax.set_xlim(0, 100)
    ax.axvline(50, color="black", linestyle="--", alpha=0.5)
    ax.set_title("Preference Distribution per Dimension")
    ax.legend(loc="lower right")
    plt.tight_layout()
    save_fig(fig, "fig_preference_distribution")


def fig_authority_by_topic(dashboard):
    per_chat   = dashboard.get("per_chat", [])
    topic_data = []
    for chat in per_chat:
        q         = chat.get("chat_query", "")[:40]
        a         = chat.get("automated", {})
        auth_sys  = a.get("authority_utilization")
        auth_base = a.get("baseline_authority")
        if auth_sys is not None:
            topic_data.append({
                "topic":    q,
                "system":   float(auth_sys),
                "baseline": float(auth_base) if auth_base is not None else float("nan"),
            })
    if not topic_data:
        warnings.warn("No per-chat authority data.")
        return
    topic_data.sort(key=lambda x: x["system"] - (x["baseline"] if not math.isnan(x["baseline"]) else x["system"]))

    labels = [d["topic"] for d in topic_data]
    sys_v  = [d["system"] for d in topic_data]
    base_v = [d["baseline"] for d in topic_data]
    x, w   = np.arange(len(labels)), 0.35
    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 0.75), 5))
    ax.bar(x - w/2, sys_v,  w, label="ParliamentRAG", color=SYSTEM_COLOR,   alpha=0.85)
    ax.bar(x + w/2, base_v, w, label="NotebookLM",   color=BASELINE_COLOR, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
    ax.set_ylabel("Mean Authority Score [0, 1]")
    ax.set_ylim(0, 1.05)
    ax.set_title("Authority Utilization per Topic (sorted by delta)")
    ax.legend()
    save_fig(fig, "fig_authority_by_topic")


def fig_radar_chart(human_results):
    dims = human_results["active_dims"]
    if not dims:
        return
    sys_means  = [mean(human_results["sys_ratings"].get(d, [3])) for d in dims]
    base_means = [mean(human_results["base_ratings"].get(d, [3])) for d in dims]
    N      = len(dims)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles    += angles[:1]
    sys_means  += sys_means[:1]
    base_means += base_means[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, sys_means,  "o-", color=SYSTEM_COLOR,   linewidth=2, label="ParliamentRAG")
    ax.fill(angles, sys_means,  alpha=0.15, color=SYSTEM_COLOR)
    ax.plot(angles, base_means, "s-", color=BASELINE_COLOR, linewidth=2, label="NotebookLM")
    ax.fill(angles, base_means, alpha=0.15, color=BASELINE_COLOR)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([DIM_LABELS.get(d, d) for d in dims], fontsize=8)
    ax.set_ylim(1, 5)
    ax.set_title("Radar Chart: Human Evaluation Dimensions", pad=15)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    save_fig(fig, "fig_radar_chart")


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    dashboard, csv_text, all_surveys = fetch_data()

    try:
        df = pd.read_csv(StringIO(csv_text))
        log(f"  CSV rows: {len(df)}, columns: {len(df.columns)}")
    except Exception as e:
        warnings.warn(f"Failed to parse CSV: {e}")
        df = None

    auto_results  = analyse_automated(dashboard, df)
    human_results = analyse_human(dashboard, all_surveys)
    topic_rows    = analyse_per_topic(dashboard, all_surveys)
    ev_summary    = analyse_per_evaluator(all_surveys)
    cit_results   = analyse_citations(all_surveys)
    group_votes   = analyse_group_authority(all_surveys)
    feedback      = analyse_feedback(all_surveys)
    analyse_completion_matrix(all_surveys, dashboard)

    log("\n" + "=" * 60)
    log("Generating remaining figures")
    log("=" * 60)
    if auto_results:
        fig_automated_metrics(auto_results)
    if human_results["active_dims"]:
        fig_human_ratings(human_results)
        fig_preference_distribution(human_results)
        fig_radar_chart(human_results)
    fig_authority_by_topic(dashboard)

    # ── Final summary ────────────────────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("FINAL SUMMARY")
    log("=" * 60)
    ab = dashboard.get("ab_comparison") or {}
    log(f"  Total chats evaluated: {dashboard.get('total_chats', '?')}")
    log(f"  A/B total evaluations: {ab.get('total_evaluations', '?')}")
    log(f"  ParliamentRAG win rate: {fmt(ab.get('system_win_rate', 0))}%")
    log(f"  NotebookLM win rate:    {fmt(ab.get('baseline_win_rate', 0))}%")
    log(f"  Tie rate:          {fmt(ab.get('tie_rate', 0))}%")
    log(f"\n  Overall preference binomial p = {fmt(human_results.get('binom_p', float('nan')), 4)}")
    log(f"  (system={human_results.get('n_sys')}, baseline={human_results.get('n_base')}, "
        f"tie={human_results.get('n_tie')})")
    log(f"\n  Would recommend: yes={feedback.get('n_yes','?')}, no={feedback.get('n_no','?')}")
    log("\n  Cohen's d per dimension:")
    for d in human_results.get("active_dims", []):
        dv = human_results["d_vals"].get(d, float("nan"))
        log(f"    {DIM_LABELS.get(d, d)}: d={fmt(dv)} ({d_category(dv)})")
    log("\n  Output files written to: outputs/")

    summary_path = os.path.join(OUT_DIR, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(SUMMARY_LINES))
    print(f"\n  -> saved {os.path.relpath(summary_path)}")
    print("\nDone.")


if __name__ == "__main__":
    main()
