"""Generate matplotlib figures for the Findable Score research paper.

Usage:
    # Generate all figures (requires DB)
    powershell -Command "set PYTHONIOENCODING=utf-8 && python scripts/generate_paper_figures.py"

    # Generate a single figure
    powershell -Command "set PYTHONIOENCODING=utf-8 && python scripts/generate_paper_figures.py --figure 2"

    # Use hardcoded data (no DB required)
    powershell -Command "set PYTHONIOENCODING=utf-8 && python scripts/generate_paper_figures.py --no-db"
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys

# Fix Windows cp1252 encoding for structlog emoji output
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from dataclasses import dataclass
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")  # Non-interactive backend

# ---------------------------------------------------------------------------
# Color palette (matches Findable brand)
# ---------------------------------------------------------------------------
TEAL = "#14b8a6"
RED = "#ef4444"
YELLOW = "#eab308"
SLATE = "#64748b"
BG = "#0a0f1a"
BG_LIGHTER = "#111827"
TEXT_COLOR = "#e2e8f0"
GRID_COLOR = "#1e293b"
TEAL_LIGHT = "#2dd4bf"
RED_LIGHT = "#f87171"

FIGURES_DIR = Path("c:/Users/joeba/Documents/findable/docs/paper/figures")

# Default pillar weights (from calculator_v2.py)
DEFAULT_WEIGHTS = {
    "technical": 12,
    "structure": 18,
    "schema": 13,
    "authority": 12,
    "entity_recognition": 13,
    "retrieval": 22,
    "coverage": 10,
}

DEFAULT_FINDABILITY_THRESHOLD = 30

# Pillar display names for axis labels
PILLAR_LABELS = {
    "technical": "Technical",
    "structure": "Structure",
    "schema": "Schema",
    "authority": "Authority",
    "entity_recognition": "Entity\nRecognition",
    "retrieval": "Retrieval",
    "coverage": "Coverage",
}

# Site type display names
SITE_TYPE_LABELS = {
    "documentation": "Documentation",
    "reference": "Reference",
    "developer_tools": "Developer Tools",
    "blog": "Blog",
    "saas_marketing": "SaaS Marketing",
    "mixed": "Mixed",
    "ecommerce": "E-commerce",
    "ugc_platform": "UGC Platform",
    "news_media": "News Media",
}

# Citation baselines from worker/extraction/site_type.py
CITATION_BASELINES = {
    "documentation": 0.95,
    "reference": 0.85,
    "developer_tools": 0.80,
    "blog": 0.50,
    "saas_marketing": 0.45,
    "mixed": 0.50,
    "ecommerce": 0.35,
    "ugc_platform": 0.20,
    "news_media": 0.10,
}

# Per-question-category citation rates by tier (from CATEGORY_CITATION_RATES)
CATEGORY_RATES_HIGH = {
    "identity": 0.75,
    "differentiation": 0.92,
    "expertise": 0.93,
    "comparison": 0.67,
    "offerings": 0.85,
}
CATEGORY_RATES_LOW = {
    "identity": 0.12,
    "differentiation": 0.11,
    "expertise": 0.18,
    "comparison": 0.08,
    "offerings": 0.14,
}


# ---------------------------------------------------------------------------
# Dataclass for a simplified sample record
# ---------------------------------------------------------------------------
@dataclass
class SampleRecord:
    """Simplified representation of a CalibrationSample for figure generation."""

    pillar_scores: dict[str, float]
    obs_cited: bool
    obs_mentioned: bool
    site_type: str | None
    question_category: str
    site_id: str
    findable_score: float = 0.0  # computed from pillar_scores + weights

    def compute_findable_score(self, weights: dict[str, float] | None = None) -> float:
        """Compute the findable score from pillar_scores using given weights."""
        w = weights or DEFAULT_WEIGHTS
        score = 0.0
        for pillar, weight in w.items():
            pillar_val = self.pillar_scores.get(pillar, 0.0) or 0.0
            score += pillar_val * (weight / 100.0)
        self.findable_score = score
        return score


# ---------------------------------------------------------------------------
# Apply dark theme styling
# ---------------------------------------------------------------------------
def apply_dark_theme() -> None:
    """Configure matplotlib dark theme with custom Findable colors."""
    plt.style.use("dark_background")
    plt.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": BG_LIGHTER,
            "axes.edgecolor": GRID_COLOR,
            "axes.labelcolor": TEXT_COLOR,
            "axes.grid": True,
            "grid.color": GRID_COLOR,
            "grid.alpha": 0.5,
            "text.color": TEXT_COLOR,
            "xtick.color": TEXT_COLOR,
            "ytick.color": TEXT_COLOR,
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.facecolor": BG,
            "savefig.edgecolor": BG,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.3,
        }
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
async def load_samples_from_db() -> list[SampleRecord]:
    """Load CalibrationSample rows from PostgreSQL and convert to SampleRecord."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from api.config import get_settings
    from api.models.calibration import CalibrationSample

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(CalibrationSample)
            .where(CalibrationSample.pillar_scores.isnot(None))
            .order_by(CalibrationSample.created_at)
        )
        rows = list(result.scalars().all())

    await engine.dispose()

    samples: list[SampleRecord] = []
    for row in rows:
        if not row.pillar_scores:
            continue
        # Filter for sufficient weight coverage (>=70%)
        covered = sum(
            DEFAULT_WEIGHTS.get(p, 0)
            for p in DEFAULT_WEIGHTS
            if row.pillar_scores.get(p) is not None
        )
        if covered < 70.0:
            continue

        rec = SampleRecord(
            pillar_scores=row.pillar_scores,
            obs_cited=row.obs_cited,
            obs_mentioned=row.obs_mentioned,
            site_type=row.site_type,
            question_category=row.question_category,
            site_id=str(row.site_id),
        )
        rec.compute_findable_score()
        samples.append(rec)

    return samples


def generate_synthetic_samples() -> list[SampleRecord]:
    """Generate synthetic samples from citation baselines for --no-db mode.

    Produces ~1200 samples with realistic pillar score distributions and citation
    outcomes that match the empirical baselines from the calibration corpus.
    """
    rng = np.random.default_rng(42)
    samples: list[SampleRecord] = []
    categories = ["identity", "differentiation", "expertise", "comparison", "offerings"]

    # Distribution of samples across site types (roughly matches real corpus)
    site_type_counts = {
        "documentation": 160,
        "reference": 120,
        "developer_tools": 140,
        "blog": 120,
        "saas_marketing": 180,
        "mixed": 80,
        "ecommerce": 100,
        "ugc_platform": 120,
        "news_media": 160,
    }

    # Pillar score ranges by site type (high-citation types score differently)
    pillar_profiles: dict[str, dict[str, tuple[float, float]]] = {
        "documentation": {
            "technical": (65, 95),
            "structure": (70, 95),
            "schema": (50, 90),
            "authority": (40, 70),
            "entity_recognition": (50, 85),
            "retrieval": (60, 95),
            "coverage": (55, 95),
        },
        "reference": {
            "technical": (60, 90),
            "structure": (65, 90),
            "schema": (55, 85),
            "authority": (50, 80),
            "entity_recognition": (55, 90),
            "retrieval": (55, 85),
            "coverage": (50, 85),
        },
        "developer_tools": {
            "technical": (60, 90),
            "structure": (55, 85),
            "schema": (45, 80),
            "authority": (45, 75),
            "entity_recognition": (50, 85),
            "retrieval": (50, 80),
            "coverage": (45, 80),
        },
        "blog": {
            "technical": (40, 80),
            "structure": (40, 75),
            "schema": (20, 60),
            "authority": (30, 65),
            "entity_recognition": (35, 70),
            "retrieval": (35, 70),
            "coverage": (30, 70),
        },
        "saas_marketing": {
            "technical": (50, 85),
            "structure": (50, 80),
            "schema": (40, 75),
            "authority": (50, 80),
            "entity_recognition": (55, 85),
            "retrieval": (25, 55),
            "coverage": (20, 60),
        },
        "mixed": {
            "technical": (40, 80),
            "structure": (40, 75),
            "schema": (25, 65),
            "authority": (35, 70),
            "entity_recognition": (40, 75),
            "retrieval": (30, 65),
            "coverage": (30, 65),
        },
        "ecommerce": {
            "technical": (45, 80),
            "structure": (45, 75),
            "schema": (50, 85),
            "authority": (30, 60),
            "entity_recognition": (40, 70),
            "retrieval": (20, 50),
            "coverage": (20, 55),
        },
        "ugc_platform": {
            "technical": (35, 70),
            "structure": (30, 65),
            "schema": (15, 50),
            "authority": (40, 75),
            "entity_recognition": (50, 85),
            "retrieval": (20, 50),
            "coverage": (15, 50),
        },
        "news_media": {
            "technical": (50, 85),
            "structure": (45, 80),
            "schema": (55, 85),
            "authority": (55, 90),
            "entity_recognition": (60, 95),
            "retrieval": (10, 35),
            "coverage": (10, 35),
        },
    }

    site_counter = 0
    for site_type, count in site_type_counts.items():
        citation_rate = CITATION_BASELINES[site_type]
        profile = pillar_profiles[site_type]
        # Group samples into ~3-5 "sites" per type
        n_sites = max(3, count // 40)
        site_ids = [f"{site_type}_{i:03d}" for i in range(n_sites)]

        for i in range(count):
            sid = site_ids[i % n_sites]
            cat = categories[i % len(categories)]

            # Generate pillar scores from profile
            pillars: dict[str, float] = {}
            for pillar, (lo, hi) in profile.items():
                pillars[pillar] = float(np.clip(rng.normal((lo + hi) / 2, (hi - lo) / 5), 0, 100))

            # Determine citation outcome probabilistically
            obs_cited = bool(rng.random() < citation_rate)
            # obs_mentioned is always ~99.8% true
            obs_mentioned = bool(rng.random() < 0.998)

            rec = SampleRecord(
                pillar_scores=pillars,
                obs_cited=obs_cited,
                obs_mentioned=obs_mentioned,
                site_type=site_type,
                question_category=cat,
                site_id=sid,
            )
            rec.compute_findable_score()
            samples.append(rec)

        site_counter += n_sites

    return samples


# ---------------------------------------------------------------------------
# Figure 1: Score Distribution Histogram
# ---------------------------------------------------------------------------
def figure_1_score_distribution(samples: list[SampleRecord]) -> None:
    """Histogram of Findable Scores colored by cited vs not cited."""
    fig, ax = plt.subplots(figsize=(10, 6))

    cited_scores = [s.findable_score for s in samples if s.obs_cited]
    uncited_scores = [s.findable_score for s in samples if not s.obs_cited]

    bins = np.arange(0, 105, 5)

    ax.hist(
        uncited_scores,
        bins=bins,
        color=RED,
        alpha=0.7,
        label=f"Not Cited (n={len(uncited_scores)})",
        edgecolor=RED_LIGHT,
        linewidth=0.5,
    )
    ax.hist(
        cited_scores,
        bins=bins,
        color=TEAL,
        alpha=0.7,
        label=f"Cited (n={len(cited_scores)})",
        edgecolor=TEAL_LIGHT,
        linewidth=0.5,
    )

    # Threshold line
    ax.axvline(
        x=DEFAULT_FINDABILITY_THRESHOLD,
        color=YELLOW,
        linestyle="--",
        linewidth=1.5,
        label=f"Findability Threshold ({DEFAULT_FINDABILITY_THRESHOLD})",
    )

    ax.set_xlabel("Findable Score")
    ax.set_ylabel("Number of Samples")
    ax.set_title("Distribution of Findable Scores Across Calibration Corpus", fontweight="bold")
    ax.legend(loc="upper right", framealpha=0.8, facecolor=BG_LIGHTER, edgecolor=GRID_COLOR)
    ax.set_xlim(0, 100)

    _save_figure(fig, "figure_1_score_distribution")


# ---------------------------------------------------------------------------
# Figure 2: Citation Rate by Site Type
# ---------------------------------------------------------------------------
def figure_2_citation_by_site_type(samples: list[SampleRecord]) -> None:
    """Horizontal bar chart of citation rate by site content type."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Calculate citation rate per site type
    site_type_stats: dict[str, dict[str, int]] = {}
    for s in samples:
        st = s.site_type or "mixed"
        if st not in site_type_stats:
            site_type_stats[st] = {"cited": 0, "total": 0}
        site_type_stats[st]["total"] += 1
        if s.obs_cited:
            site_type_stats[st]["cited"] += 1

    # Sort by citation rate
    sorted_types = sorted(
        site_type_stats.keys(),
        key=lambda t: site_type_stats[t]["cited"] / max(site_type_stats[t]["total"], 1),
        reverse=True,
    )

    labels = [SITE_TYPE_LABELS.get(t, t.replace("_", " ").title()) for t in sorted_types]
    rates = [
        site_type_stats[t]["cited"] / max(site_type_stats[t]["total"], 1) * 100
        for t in sorted_types
    ]
    counts = [site_type_stats[t]["total"] for t in sorted_types]

    # Color gradient from teal (high) to red (low)
    colors = _gradient_colors(rates, high_color=TEAL, low_color=RED)

    bars = ax.barh(
        labels,
        rates,
        color=colors,
        edgecolor=[_darken(c, 0.7) for c in colors],
        linewidth=0.5,
        height=0.65,
    )

    # Add count annotations
    for bar_rect, rate, count in zip(bars, rates, counts, strict=False):
        ax.text(
            rate + 1.5,
            bar_rect.get_y() + bar_rect.get_height() / 2,
            f"{rate:.0f}% (n={count})",
            va="center",
            ha="left",
            fontsize=9,
            color=TEXT_COLOR,
        )

    ax.set_xlabel("Citation Rate (%)")
    ax.set_title("Observed Citation Rate by Site Content Type", fontweight="bold")
    ax.set_xlim(0, 115)
    ax.invert_yaxis()

    _save_figure(fig, "figure_2_citation_by_site_type")


# ---------------------------------------------------------------------------
# Figure 3: Pillar Score Distributions - Cited vs Uncited
# ---------------------------------------------------------------------------
def figure_3_pillar_distributions(samples: list[SampleRecord]) -> None:
    """Box plot of pillar scores for cited vs uncited samples."""
    fig, ax = plt.subplots(figsize=(12, 6))

    pillars = list(DEFAULT_WEIGHTS.keys())
    pillar_labels = [PILLAR_LABELS[p] for p in pillars]

    cited_data = []
    uncited_data = []
    for p in pillars:
        cited_data.append([s.pillar_scores.get(p, 0) or 0 for s in samples if s.obs_cited])
        uncited_data.append([s.pillar_scores.get(p, 0) or 0 for s in samples if not s.obs_cited])

    positions = np.arange(len(pillars))
    width = 0.35

    # Cited boxes
    bp_cited = ax.boxplot(
        cited_data,
        positions=positions - width / 2,
        widths=width * 0.8,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "white", "linewidth": 1.5},
        whiskerprops={"color": TEAL_LIGHT, "linewidth": 1},
        capprops={"color": TEAL_LIGHT, "linewidth": 1},
    )
    for patch in bp_cited["boxes"]:
        patch.set_facecolor(TEAL)
        patch.set_alpha(0.7)
        patch.set_edgecolor(TEAL_LIGHT)

    # Uncited boxes
    bp_uncited = ax.boxplot(
        uncited_data,
        positions=positions + width / 2,
        widths=width * 0.8,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "white", "linewidth": 1.5},
        whiskerprops={"color": RED_LIGHT, "linewidth": 1},
        capprops={"color": RED_LIGHT, "linewidth": 1},
    )
    for patch in bp_uncited["boxes"]:
        patch.set_facecolor(RED)
        patch.set_alpha(0.7)
        patch.set_edgecolor(RED_LIGHT)

    ax.set_xticks(positions)
    ax.set_xticklabels(pillar_labels, fontsize=10)
    ax.set_ylabel("Pillar Score (0-100)")
    ax.set_title("Pillar Score Distributions: Cited vs Uncited Sites", fontweight="bold")
    ax.set_ylim(0, 105)

    # Custom legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=TEAL, alpha=0.7, edgecolor=TEAL_LIGHT, label="Cited"),
        Patch(facecolor=RED, alpha=0.7, edgecolor=RED_LIGHT, label="Not Cited"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="upper right",
        framealpha=0.8,
        facecolor=BG_LIGHTER,
        edgecolor=GRID_COLOR,
    )

    # Weight annotations along the bottom
    for i, p in enumerate(pillars):
        ax.text(
            i,
            -7,
            f"{DEFAULT_WEIGHTS[p]}%",
            ha="center",
            va="top",
            fontsize=8,
            color=SLATE,
            style="italic",
        )

    _save_figure(fig, "figure_3_pillar_distributions")


# ---------------------------------------------------------------------------
# Figure 4: Confusion Matrix
# ---------------------------------------------------------------------------
def figure_4_confusion_matrix(samples: list[SampleRecord]) -> None:
    """2x2 heatmap of predicted vs actual citation outcomes."""
    fig, ax = plt.subplots(figsize=(7, 6))

    # Classify each sample
    tp, fp, fn, tn = 0, 0, 0, 0
    for s in samples:
        predicted_findable = s.findable_score >= DEFAULT_FINDABILITY_THRESHOLD
        if predicted_findable and s.obs_cited:
            tp += 1
        elif predicted_findable and not s.obs_cited:
            fp += 1
        elif not predicted_findable and s.obs_cited:
            fn += 1
        else:
            tn += 1

    total = tp + fp + fn + tn
    matrix = np.array([[tp, fp], [fn, tn]])
    pct_matrix = matrix / max(total, 1) * 100

    # Custom colormap from teal to red
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("findable", [RED, BG_LIGHTER, TEAL], N=256)

    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=max(tp, tn) * 1.2)

    # Labels
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Cited\n(Actual)", "Not Cited\n(Actual)"], fontsize=11)
    ax.set_yticklabels(["Findable\n(Predicted)", "Not Findable\n(Predicted)"], fontsize=11)

    # Cell annotations
    cell_labels = [
        [f"TP\n{tp}\n({pct_matrix[0, 0]:.1f}%)", f"FP\n{fp}\n({pct_matrix[0, 1]:.1f}%)"],
        [f"FN\n{fn}\n({pct_matrix[1, 0]:.1f}%)", f"TN\n{tn}\n({pct_matrix[1, 1]:.1f}%)"],
    ]
    for i in range(2):
        for j in range(2):
            ax.text(
                j,
                i,
                cell_labels[i][j],
                ha="center",
                va="center",
                fontsize=13,
                fontweight="bold",
                color="white",
            )

    # Summary metrics
    accuracy = (tp + tn) / max(total, 1) * 100
    precision = tp / max(tp + fp, 1) * 100
    recall = tp / max(tp + fn, 1) * 100
    f1 = 2 * precision * recall / max(precision + recall, 0.01)

    summary = f"Accuracy: {accuracy:.1f}%  |  Precision: {precision:.1f}%  |  Recall: {recall:.1f}%  |  F1: {f1:.1f}%"
    fig.text(0.5, 0.02, summary, ha="center", fontsize=10, color=SLATE)

    ax.set_title(
        f"Prediction Accuracy: Findable Score vs Observed Citation\n(threshold={DEFAULT_FINDABILITY_THRESHOLD}, n={total})",
        fontweight="bold",
    )

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Count")

    _save_figure(fig, "figure_4_confusion_matrix")


# ---------------------------------------------------------------------------
# Figure 5: Citation Rate by Question Category and Site Tier
# ---------------------------------------------------------------------------
def figure_5_citation_by_category(samples: list[SampleRecord]) -> None:
    """Grouped bar chart showing citation rate by question category and site tier."""
    fig, ax = plt.subplots(figsize=(10, 6))

    categories = ["identity", "differentiation", "expertise", "comparison", "offerings"]
    cat_labels = [c.title() for c in categories]

    # Determine per-site citation tier: HIGH (>=60% cited) vs LOW (<60% cited)
    site_stats: dict[str, dict[str, int]] = {}
    for s in samples:
        if s.site_id not in site_stats:
            site_stats[s.site_id] = {"cited": 0, "total": 0}
        site_stats[s.site_id]["total"] += 1
        if s.obs_cited:
            site_stats[s.site_id]["cited"] += 1

    high_sites = {
        sid
        for sid, st in site_stats.items()
        if st["total"] >= 5 and st["cited"] / st["total"] >= 0.60
    }
    low_sites = {
        sid
        for sid, st in site_stats.items()
        if st["total"] >= 5 and st["cited"] / st["total"] < 0.60
    }

    # Calculate per-category citation rate for each tier
    high_rates = []
    low_rates = []
    for cat in categories:
        # HIGH tier
        h_cited = sum(
            1
            for s in samples
            if s.site_id in high_sites and s.question_category == cat and s.obs_cited
        )
        h_total = sum(1 for s in samples if s.site_id in high_sites and s.question_category == cat)
        high_rates.append(h_cited / max(h_total, 1) * 100)

        # LOW tier
        l_cited = sum(
            1
            for s in samples
            if s.site_id in low_sites and s.question_category == cat and s.obs_cited
        )
        l_total = sum(1 for s in samples if s.site_id in low_sites and s.question_category == cat)
        low_rates.append(l_cited / max(l_total, 1) * 100)

    # If DB data produced no tier separation, fall back to hardcoded baselines
    if not high_sites or not low_sites:
        high_rates = [CATEGORY_RATES_HIGH[c] * 100 for c in categories]
        low_rates = [CATEGORY_RATES_LOW[c] * 100 for c in categories]

    x = np.arange(len(categories))
    width = 0.35

    bars_high = ax.bar(
        x - width / 2,
        high_rates,
        width,
        color=TEAL,
        alpha=0.85,
        label=f"HIGH Tier (n={len(high_sites)} sites)",
        edgecolor=TEAL_LIGHT,
        linewidth=0.5,
    )
    bars_low = ax.bar(
        x + width / 2,
        low_rates,
        width,
        color=RED,
        alpha=0.85,
        label=f"LOW Tier (n={len(low_sites)} sites)",
        edgecolor=RED_LIGHT,
        linewidth=0.5,
    )

    # Value labels on bars
    for bars in [bars_high, bars_low]:
        for bar_rect in bars:
            height = bar_rect.get_height()
            if height > 3:
                ax.text(
                    bar_rect.get_x() + bar_rect.get_width() / 2,
                    height + 1.5,
                    f"{height:.0f}%",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    color=TEXT_COLOR,
                )

    ax.set_xticks(x)
    ax.set_xticklabels(cat_labels, fontsize=11)
    ax.set_ylabel("Citation Rate (%)")
    ax.set_ylim(0, 110)
    ax.set_title("Citation Rate by Question Category and Site Tier", fontweight="bold")
    ax.legend(loc="upper right", framealpha=0.8, facecolor=BG_LIGHTER, edgecolor=GRID_COLOR)

    _save_figure(fig, "figure_5_citation_by_category")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _save_figure(fig: plt.Figure, name: str) -> None:
    """Save figure as both PNG and PDF."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    png_path = FIGURES_DIR / f"{name}.png"
    pdf_path = FIGURES_DIR / f"{name}.pdf"

    fig.savefig(str(png_path))
    fig.savefig(str(pdf_path))
    plt.close(fig)

    print(f"  Saved: {png_path.name} + {pdf_path.name}")


def _gradient_colors(
    values: list[float],
    high_color: str = TEAL,
    low_color: str = RED,
) -> list[str]:
    """Generate a list of hex colors interpolated between low_color and high_color."""
    from matplotlib.colors import LinearSegmentedColormap, to_hex, to_rgb

    if not values:
        return []

    lo = min(values)
    hi = max(values)
    span = hi - lo if hi != lo else 1.0

    cmap = LinearSegmentedColormap.from_list(
        "custom_grad",
        [to_rgb(low_color), to_rgb(high_color)],
        N=256,
    )
    return [to_hex(cmap((v - lo) / span)) for v in values]


def _darken(hex_color: str, factor: float = 0.7) -> str:
    """Darken a hex color by a factor (0=black, 1=unchanged)."""
    from matplotlib.colors import to_hex, to_rgb

    r, g, b = to_rgb(hex_color)
    return to_hex((r * factor, g * factor, b * factor))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
FIGURE_FUNCTIONS = {
    1: ("Score Distribution Histogram", figure_1_score_distribution),
    2: ("Citation Rate by Site Type", figure_2_citation_by_site_type),
    3: ("Pillar Score Distributions", figure_3_pillar_distributions),
    4: ("Confusion Matrix", figure_4_confusion_matrix),
    5: ("Citation Rate by Question Category", figure_5_citation_by_category),
}


async def main(figure_num: int | None = None, no_db: bool = False) -> None:
    """Generate research paper figures."""
    apply_dark_theme()

    print("=" * 60)
    print("FINDABLE SCORE RESEARCH PAPER - FIGURE GENERATOR")
    print("=" * 60)
    print()

    # Load data
    if no_db:
        print("Using synthetic data (--no-db mode)")
        samples = generate_synthetic_samples()
    else:
        print("Loading calibration samples from database...")
        try:
            samples = await load_samples_from_db()
        except Exception as e:
            print(f"  DB error: {e}")
            print("  Falling back to synthetic data.")
            samples = generate_synthetic_samples()

    cited_count = sum(1 for s in samples if s.obs_cited)
    print(f"  Total samples: {len(samples)}")
    print(f"  Cited: {cited_count} ({cited_count / max(len(samples), 1) * 100:.1f}%)")
    print(
        f"  Uncited: {len(samples) - cited_count} ({(len(samples) - cited_count) / max(len(samples), 1) * 100:.1f}%)"
    )

    site_types = {s.site_type for s in samples if s.site_type}
    print(f"  Site types: {len(site_types)}")

    scores = [s.findable_score for s in samples]
    if scores:
        print(f"  Score range: {min(scores):.1f} - {max(scores):.1f} (mean={np.mean(scores):.1f})")
    print()

    # Generate figures
    if figure_num is not None:
        if figure_num not in FIGURE_FUNCTIONS:
            print(
                f"ERROR: Figure {figure_num} does not exist. Valid: {list(FIGURE_FUNCTIONS.keys())}"
            )
            return
        name, func = FIGURE_FUNCTIONS[figure_num]
        print(f"Generating Figure {figure_num}: {name}")
        func(samples)
    else:
        for num, (name, func) in FIGURE_FUNCTIONS.items():
            print(f"Generating Figure {num}: {name}")
            func(samples)

    print()
    print(f"Output directory: {FIGURES_DIR}")
    print("Done.")


def cli() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description="Generate research paper figures")
    parser.add_argument(
        "--figure",
        type=int,
        default=None,
        help="Generate a single figure (1-5). Omit to generate all.",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Use hardcoded synthetic data instead of querying the database.",
    )
    args = parser.parse_args()

    asyncio.run(main(figure_num=args.figure, no_db=args.no_db))


if __name__ == "__main__":
    cli()
