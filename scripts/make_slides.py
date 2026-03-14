#!/usr/bin/env python3
"""
make_slides.py — Generate Marp slides for ParliamentRAG evaluation results.
Reads from outputs/ and writes outputs/slides_risultati.md + PDF.
"""

import json
import re
import subprocess
import math
from pathlib import Path

OUTPUTS = Path("outputs")

# ── helpers ──────────────────────────────────────────────────────────────────

def nd(val, decimals=2):
    try:
        if val is None:
            return "N/D"
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/D"

def delta_str(sys_val, base_val, decimals=2):
    try:
        d = float(sys_val) - float(base_val)
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:.{decimals}f}"
    except (TypeError, ValueError):
        return "N/D"

def sigma_from_ci(ci_low, ci_high, n):
    try:
        return (float(ci_high) - float(ci_low)) / (2 * 1.96) * math.sqrt(n)
    except (TypeError, ValueError):
        return None

def cohen_label(d):
    try:
        d = abs(float(d))
        if d < 0.2:   return "neg."
        elif d < 0.5: return "S"
        elif d < 0.8: return "M"
        else:          return "L"
    except (TypeError, ValueError):
        return "N/D"

def parse_tex_rows(tex_path):
    rows = []
    try:
        text = Path(tex_path).read_text()
        in_table = False
        for line in text.splitlines():
            line = line.strip()
            if r"\midrule" in line:
                in_table = True
                continue
            if r"\bottomrule" in line:
                break
            if in_table and "\\\\" in line:
                row_str = line.rstrip("\\").strip()
                cells = [c.strip() for c in row_str.split("&")]
                rows.append(cells)
    except Exception:
        pass
    return rows

def _pdf_to_png(pdf: Path, png: Path) -> bool:
    try:
        stem = str(png).removesuffix(".png")
        subprocess.run(
            ["pdftoppm", "-png", "-r", "200", "-singlefile", str(pdf), stem],
            capture_output=True,
        )
        if png.exists():
            return True
    except FileNotFoundError:
        pass
    try:
        subprocess.run(
            ["sips", "-s", "format", "png", str(pdf), "--out", str(png)],
            capture_output=True,
        )
        if png.exists():
            return True
    except FileNotFoundError:
        pass
    try:
        subprocess.run(
            ["convert", "-density", "200", f"{pdf}[0]", str(png)],
            capture_output=True,
        )
        if png.exists():
            return True
    except FileNotFoundError:
        pass
    return False

def convert_pdfs_to_png():
    figs = [
        "fig_automated_metrics",
        "fig_human_ratings",
        "fig_preference_distribution",
        "fig_authority_by_topic",
        "fig_radar_chart",
        "fig_heatmap_topics",
        "fig_topic_preference",
        "fig_evaluator_bias",
        "fig_citation_comparison",
        "fig_attribution_accuracy",
        "fig_citation_issues",
        "fig_group_authority",
        "fig_completion_matrix",
    ]
    converted = []
    for fig in figs:
        pdf = OUTPUTS / f"{fig}.pdf"
        png = OUTPUTS / f"{fig}.png"
        if not pdf.exists():
            print(f"  [warn] PDF not found: {pdf}")
            continue
        if png.exists():
            converted.append(fig)
            continue
        if _pdf_to_png(pdf, png):
            converted.append(fig)
        else:
            print(f"  [warn] Could not convert {pdf} -> PNG")
    return converted

# ── load data ─────────────────────────────────────────────────────────────────

def load_dashboard():
    try:
        with open(OUTPUTS / "raw_dashboard.json") as f:
            return json.load(f)
    except Exception as e:
        print(f"[error] Could not read raw_dashboard.json: {e}")
        return {}

def load_summary():
    try:
        return (OUTPUTS / "summary.txt").read_text()
    except Exception:
        return ""

def load_feedback():
    try:
        return (OUTPUTS / "feedback_report.txt").read_text()
    except Exception:
        return ""

# ── slide builders ────────────────────────────────────────────────────────────

def build_frontmatter():
    return """\
---
marp: true
theme: default
paginate: true
math: mathjax
style: |
  section {
    font-family: 'Calibri', 'Segoe UI', sans-serif;
    background-color: #FAFBFE;
    color: #1E293B;
  }
  section.lead {
    background-color: #1B2A4A;
    color: #FFFFFF;
    text-align: center;
  }
  section.lead h1 {
    color: #C4A35A;
  }
  h1 {
    color: #1B2A4A;
    border-bottom: 2px solid #C4A35A;
    padding-bottom: 8px;
  }
  h2 { color: #2D5F8A; }
  table { font-size: 0.72em; }
  th { background-color: #1B2A4A; color: white; }
  td { border-bottom: 1px solid #E2E8F0; }
  .highlight { color: #C4A35A; font-weight: bold; }
  .green { color: #16a34a; }
  .red { color: #dc2626; }
  img { max-height: 420px; }
  footer { font-size: 0.6em; color: #94A3B8; }
---"""


def slide_01_title():
    return """\
<!-- _class: lead -->

# Risultati della Valutazione Sperimentale

## ParliamentRAG vs. NotebookLM — A/B Test Blind

15 topic · 6 evaluatori esperti · 9 dimensioni Likert"""


def slide_02_setup():
    return """\
# Setup Sperimentale

- **15 topic** selezionati tramite questionario partecipativo (17 rispondenti)
- **Baseline:** Google NotebookLM — stesso corpus, prompt strutturato equivalente
- **Valutazione su 2 livelli:**
  - **Level 1 — 5 metriche automatiche** (copertura gruppi, completezza, fedeltà citazioni, authority)
  - **Level 2 — 9 dimensioni umane** su scala Likert 1–5
- **Evaluatori:** Christian (15), Luca (15), Alessandro (11), Edoardo (10), Federico (9), Nicolò (7) = **67 survey**
- **Piano statistico:** Wilcoxon signed-rank, Cohen's *d*, Krippendorff's α"""


def slide_03_automated_table(dash):
    aa = dash.get("automated_aggregate", {})
    n  = aa.get("total_chats", 16)

    rows_data = [
        ("Groups with Citation",  aa.get("avg_party_coverage"),        aa.get("ci_party_coverage"),        aa.get("avg_baseline_party_coverage")),
        ("Completeness",          aa.get("avg_response_completeness"),  aa.get("ci_response_completeness"),  aa.get("avg_baseline_response_completeness")),
        ("Citation Faithfulness", aa.get("avg_verbatim_match"),         aa.get("ci_verbatim_match"),         aa.get("avg_baseline_citation_fidelity")),
        ("Mean Authority",        aa.get("avg_authority_utilization"),  aa.get("ci_authority_utilization"),  aa.get("avg_baseline_authority")),
        ("Authority Std Dev",     aa.get("avg_authority_discrimination"),aa.get("ci_authority_discrimination"), None),
    ]

    header = "| Metrica | Sistema (μ ± σ) | Baseline (μ) | Δ |"
    sep    = "|---------|----------------|--------------|---|"
    lines  = [header, sep]

    for name, sys_val, ci, base_val in rows_data:
        sig     = sigma_from_ci(ci[0], ci[1], n) if ci else None
        sys_str = f"{nd(sys_val)} ± {nd(sig)}" if sig is not None else nd(sys_val)
        base_str = nd(base_val) if base_val is not None else "—"
        d_str    = delta_str(sys_val, base_val) if base_val is not None else "—"
        lines.append(f"| {name} | {sys_str} | {base_str} | {d_str} |")

    table = "\n".join(lines)
    return f"""\
# Metriche Automatiche — Tabella (Level 1)

{table}

> *GC, Completeness, CF = 1.0 by design per il sistema; il valore informativo è nel Δ.*"""


def slide_04_automated_fig():
    return """\
# Metriche Automatiche — Grafico

![Automated Metrics](fig_automated_metrics.png)"""


def slide_05_human_table(dash):
    ha       = dash.get("human_aggregate", {})
    sys_dim  = ha.get("system_avg_per_dimension",   {})
    base_dim = ha.get("baseline_avg_per_dimension", {})

    dim_map = [
        ("answer_quality",       "Answer Quality"),
        ("answer_clarity",       "Answer Clarity"),
        ("answer_completeness",  "Answer Completeness"),
        ("citations_relevance",  "Citations Relevance"),
        ("balance_perception",   "Balance Perception"),
        ("balance_fairness",     "Balance Fairness"),
        ("source_relevance",     "Source Relevance"),
        ("source_authority",     "Source Authority"),
        ("source_coverage",      "Source Coverage"),
    ]

    header = "| Dimensione | Sistema | Baseline | Δ |"
    sep    = "|-----------|---------|----------|---|"
    lines  = [header, sep]
    for key, label in dim_map:
        s = sys_dim.get(key)
        b = base_dim.get(key)
        lines.append(f"| {label} | {nd(s)} | {nd(b)} | {delta_str(s, b)} |")

    sys_overall  = ha.get("system_avg_overall")
    base_overall = ha.get("baseline_avg_overall")
    lines.append(f"| **Overall Satisfaction** | **{nd(sys_overall)}** | **{nd(base_overall)}** | **{delta_str(sys_overall, base_overall)}** |")

    total = ha.get("total_surveys", "N/D")
    return f"""\
# Valutazione Umana — Rating Medi (Level 2)

{chr(10).join(lines)}

*N = {total} survey · Scala Likert 1–5*"""


def slide_06_human_fig():
    return """\
# Valutazione Umana — Grafico Rating

![Human Ratings](fig_human_ratings.png)"""


def slide_07_stats_compact():
    """Simplified stats slide: Wilcoxon + Cohen's d only (no Holm)."""
    rows = parse_tex_rows(OUTPUTS / "tab_statistical_summary.tex")

    header = "| Dimensione | μ sys | μ base | Δ | p (raw) | d | Effect |"
    sep    = "|-----------|-------|--------|---|---------|---|--------|"
    lines  = [header, sep]

    for cells in rows:
        if len(cells) < 7:
            continue
        # columns: Dimension, mu_sys, mu_base, delta, W, p_raw, cohen_d, effect
        dim    = cells[0]
        mu_s   = cells[1]
        mu_b   = cells[2]
        delta  = cells[3]
        p_raw  = cells[5] if len(cells) > 5 else "---"
        d_val  = cells[6] if len(cells) > 6 else "---"
        effect = cells[7] if len(cells) > 7 else cohen_label(d_val)
        lines.append(f"| {dim} | {mu_s} | {mu_b} | {delta} | {p_raw} | {d_val} | {effect} |")

    table = "\n".join(lines)
    return f"""\
# Test Statistici — Wilcoxon + Cohen's *d*

{table}

*Effect: neg. < 0.2 · S(mall) < 0.5 · M(edium) < 0.8 · L(arge) · N=67 survey, no Holm correction*"""


def slide_08_preferences(dash):
    ha       = dash.get("human_aggregate", {})
    sys_win  = ha.get("system_win_rate",   "N/D")
    base_win = ha.get("baseline_win_rate", "N/D")
    tie      = ha.get("tie_rate",          "N/D")

    binom_p = "N/D"
    try:
        summary = load_summary()
        m = re.search(r"[Bb]inomial.*?p\s*=\s*([\d.]+)", summary)
        if m:
            binom_p = m.group(1)
    except Exception:
        pass

    return f"""\
# Preferenze A/B — Overall

- **Win rate:** Sistema **{nd(sys_win, 1)}%** · Baseline **{nd(base_win, 1)}%** · Pari **{nd(tie, 1)}%**
- **Test binomiale** (escluse parità): p = {binom_p}

![Preferences](fig_preference_distribution.png)"""


def slide_09_authority():
    return """\
# Authority Score per Topic

![Authority by Topic](fig_authority_by_topic.png)

> L'authority score varia per topic, confermando la *query-dependence* del ranking."""


def slide_10_agreement():
    rows = parse_tex_rows(OUTPUTS / "tab_agreement.tex")

    header = "| Dimensione | α | Interpretazione |"
    sep    = "|-----------|---|-----------------|"
    lines  = [header, sep]
    for cells in rows:
        if len(cells) >= 3:
            lines.append(f"| {cells[0]} | {cells[1]} | {cells[2]} |")

    total_surveys = "N/D"
    try:
        with open(OUTPUTS / "raw_dashboard.json") as f:
            d = json.load(f)
        total_surveys = d.get("human_aggregate", {}).get("total_surveys", "N/D")
    except Exception:
        pass

    return f"""\
# Inter-Rater Agreement — Krippendorff's α

{chr(10).join(lines)}

*α < 0 = peggio del caso; α ∈ [0.20, 0.45] = tentativo.*
**Stato survey:** {total_surveys} valutazioni su 15 topic × 6 evaluatori."""


def slide_11_topic_heatmap():
    return """\
# Analisi per Topic — Heatmap dei Delta

![Topic Heatmap](fig_heatmap_topics.png)

*Ogni cella = Δ (sistema − baseline) per dimensione × topic. Blu = sistema meglio, Arancio = baseline meglio.*"""


def slide_12_topic_preference():
    return """\
# Analisi per Topic — Preferenze

![Topic Preference](fig_topic_preference.png)

*Per ogni topic: % evaluatori che hanno preferito sistema / pari / baseline (overall satisfaction).*"""


def slide_13_citation_quality():
    rows = parse_tex_rows(OUTPUTS / "tab_citation_quality.tex")

    header = "| Metrica | Sistema μ | Baseline μ | Δ | n sys | n base |"
    sep    = "|---------|-----------|------------|---|-------|--------|"
    lines  = [header, sep]
    for cells in rows:
        if len(cells) >= 4:
            row = cells + ["—"] * 6
            lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |")

    return f"""\
# Qualita delle Citazioni

{chr(10).join(lines)}

![Citation Comparison](fig_citation_comparison.png)"""


def slide_14_attribution():
    return """\
# Attribution Accuracy delle Citazioni

![Attribution Accuracy](fig_attribution_accuracy.png)

![Citation Issues](fig_citation_issues.png)"""


def slide_15_group_authority():
    return """\
# Authority per Gruppo Parlamentare

![Group Authority](fig_group_authority.png)

*Stacked bar: per ogni gruppo, quanti evaluatori ritengono che il sistema abbia esperti migliori, equivalenti o peggiori della baseline.*"""


def slide_16_completion_matrix():
    summary_text = load_summary()
    completion_line = "N/D"
    m = re.search(r"Total completed:\s*(\d+\s*/\s*\d+.*?\%\))", summary_text)
    if m:
        completion_line = m.group(1)

    return f"""\
# Matrice di Completamento

![Completion Matrix](fig_completion_matrix.png)

*Completamento: {completion_line}*"""


def slide_17_evaluator_profile():
    rows = parse_tex_rows(OUTPUTS / "tab_per_evaluator.tex")

    header = "| Evaluator | n topics | μ sys | μ base | Δ | % pref sys |"
    sep    = "|-----------|----------|-------|--------|---|------------|"
    lines  = [header, sep]
    for cells in rows:
        if len(cells) >= 5:
            row = cells + ["—"] * 6
            lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |")

    return f"""\
# Profilo Valutatori

{chr(10).join(lines)}

![Evaluator Bias](fig_evaluator_bias.png)"""


def slide_18_feedback():
    feedback = load_feedback()
    # Extract would_recommend line
    rec_line = "N/D"
    m = re.search(r"Would recommend: (YES=\d+, NO=\d+)", feedback)
    if m:
        rec_line = m.group(1)

    # Extract up to 6 unique positive lines
    positives = re.findall(r"^\s+\d+\. (.+)$", feedback, re.MULTILINE)
    # Take first 5
    positives_sample = positives[:5]

    pos_bullets = "\n".join(f"  - {p[:90]}" for p in positives_sample)

    return f"""\
# Feedback Qualitativo

- **Would recommend:** {rec_line}

**Punti positivi (campione):**
{pos_bullets if pos_bullets else "  *(nessun feedback raccolto)*"}

> Feedback completo in `outputs/feedback_report.txt`"""


def slide_19_rq(dash):
    aa = dash.get("automated_aggregate", {})

    gc_sys   = nd(aa.get("avg_party_coverage"), 2)
    gc_base  = nd(aa.get("avg_baseline_party_coverage"), 2)
    ma_sys   = nd(aa.get("avg_authority_utilization"), 2)
    ma_base  = nd(aa.get("avg_baseline_authority"), 2)
    ma_delta = delta_str(aa.get("avg_authority_utilization"), aa.get("avg_baseline_authority"))
    cf_sys   = nd(aa.get("avg_verbatim_match"), 2)
    comp_sys  = nd(aa.get("avg_response_completeness"), 2)
    comp_base = nd(aa.get("avg_baseline_response_completeness"), 2)

    return f"""\
# Sintesi per Research Question

| RQ | Risultato | Supporto |
|----|-----------|----------|
| **RQ1** Multi-View Coverage | GC = {gc_sys} vs. baseline {gc_base} (Δ = {delta_str(aa.get('avg_party_coverage'), aa.get('avg_baseline_party_coverage'))}) | forte |
| **RQ2** Authority Ranking | MA = {ma_sys} vs. {ma_base} (Δ = {ma_delta}) | moderato |
| **RQ3** Citation Faithfulness | CF = {cf_sys} (by construction), baseline = {nd(aa.get('avg_baseline_citation_fidelity'), 2)} | forte |
| **RQ4** Bilanciamento | Completeness = {comp_sys} vs. {comp_base} | neutro |

*Nessuna dimensione umana raggiunge soglia convenzionale p < 0.05 (N = 67 su 15 topic).*"""


def slide_20_limitations():
    return """\
<!-- _class: lead -->

# Limitazioni e Prossimi Passi

- **Small sample** (15 topic, 6 evaluatori) — Cohen's *d* come misura primaria
- **Krippendorff's α** calcolabile solo su topic con ≥ 2 valutatori
- **Citation evaluation** parziale — non tutti gli evaluatori hanno compilato
- Next: analisi qualitativa approfondita dei feedback testuali"""


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    dash = load_dashboard()

    print("Converting PDFs to PNG...")
    converted = convert_pdfs_to_png()
    print(f"  Converted: {converted}")

    print("Building slides...")
    slides = [
        build_frontmatter(),
        slide_01_title(),
        slide_02_setup(),
        slide_03_automated_table(dash),
        slide_04_automated_fig(),
        slide_05_human_table(dash),
        slide_06_human_fig(),
        slide_07_stats_compact(),
        slide_08_preferences(dash),
        slide_09_authority(),
        slide_10_agreement(),
        # New slides
        slide_11_topic_heatmap(),
        slide_12_topic_preference(),
        slide_13_citation_quality(),
        slide_14_attribution(),
        slide_15_group_authority(),
        slide_16_completion_matrix(),
        slide_17_evaluator_profile(),
        slide_18_feedback(),
        slide_19_rq(dash),
        slide_20_limitations(),
    ]

    md = slides[0] + "\n\n---\n\n" + "\n\n---\n\n".join(slides[1:]) + "\n"

    out_path = OUTPUTS / "slides_risultati.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"  Written: {out_path}")

    print("Generating PDF with marp-cli...")
    result = subprocess.run(
        [
            "npx", "@marp-team/marp-cli",
            str(out_path),
            "--pdf",
            "--allow-local-files",
            "--output", str(OUTPUTS / "slides_risultati.pdf"),
        ],
        capture_output=False,
    )
    if result.returncode == 0:
        print(f"  PDF: {OUTPUTS / 'slides_risultati.pdf'}")
    else:
        print(f"  [warn] marp-cli exited with code {result.returncode}")

    print("Done.")


if __name__ == "__main__":
    main()
