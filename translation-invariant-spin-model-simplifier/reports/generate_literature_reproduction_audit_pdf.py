#!/usr/bin/env python3
"""Generate a PDF report for the strict literature-reproduction audit."""

from __future__ import annotations

import datetime as dt
import sys
import textwrap
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
REPORTS_DIR = PROJECT_ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "literature_reproduction_audit.pdf"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validation.literature_reproduction_audit import build_literature_reproduction_audit


CATEGORY_LABELS = {
    "local_recomputed": "Local recomputed",
    "executable_projection": "Executable projection",
    "reference_only": "Reference only",
}
CATEGORY_COLORS = {
    "local_recomputed": ("#DFF1E8", "#2F7D59"),
    "executable_projection": ("#FFF0D6", "#A6641A"),
    "reference_only": ("#E9ECF2", "#5D687A"),
}
STRICT_CATEGORY_LABELS = {
    "strict_local_recomputed": "Strict local",
    "local_projection_only": "Local projection",
    "executable_projection": "Executable projection",
    "reference_only": "Reference only",
}
STRICT_CATEGORY_COLORS = {
    "strict_local_recomputed": ("#DFF1E8", "#2F7D59"),
    "local_projection_only": ("#FFF0D6", "#A6641A"),
    "executable_projection": ("#FDE2D3", "#A94420"),
    "reference_only": ("#E9ECF2", "#5D687A"),
}


def _wrap(text: object, width: int) -> str:
    return "\n".join(textwrap.wrap(str(text), width=width, break_long_words=True, break_on_hyphens=False)) or ""


def build_reproduction_pdf_payload() -> dict[str, object]:
    audit = build_literature_reproduction_audit()
    strict_count = audit["strict_category_counts"].get("strict_local_recomputed", 0)
    total_count = audit["total_standard_results"]
    remaining_gap_rows = [
        row for row in audit["rows"] if row["strict_literature_match_label"] == "no"
    ]
    if strict_count == total_count:
        direct_answer = (
            f"Yes. {strict_count} of {total_count} registered literature entries currently have a strict local "
            "recomputation, analytic reproduction, or direct published-observable parse matching the registered "
            "observable."
        )
    else:
        direct_answer = (
            f"No. {strict_count} of {total_count} registered literature entries currently have a strict local "
            "recomputation/analytic reproduction matching the registered observable; the rest are projections "
            "or stored references."
        )
    return {
        "generated_date": dt.date.today().isoformat(),
        "total_standard_results": audit["total_standard_results"],
        "category_counts": audit["category_counts"],
        "strict_category_counts": audit["strict_category_counts"],
        "rows": audit["rows"],
        "remaining_gap_rows": remaining_gap_rows,
        "direct_answer": direct_answer,
        "scope_note": (
            "Strict local reproduction requires an analytic formula, exact spectrum, exact enumeration, ED, "
            "GLT/Fourier energy calculation, or similarly direct calculation matching the registered observable. "
            "Local geometry, material-context, candidate-label, and projection checks are tracked separately."
        ),
    }


def _draw_header(fig, title: str, page_number: int) -> None:
    import matplotlib.patches as patches

    fig.patches.append(
        patches.Rectangle((0.0, 0.955), 1.0, 0.045, transform=fig.transFigure, color="#2F6F73", zorder=-1)
    )
    fig.text(0.035, 0.975, title, color="white", fontsize=11, weight="bold", va="center")
    fig.text(0.965, 0.975, f"page {page_number}", color="white", fontsize=8, ha="right", va="center")


def _metric_card(fig, x: float, y: float, w: float, h: float, label: str, value: str, note: str, color: str) -> None:
    import matplotlib.patches as patches

    fig.patches.append(
        patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.006,rounding_size=0.006",
            transform=fig.transFigure,
            facecolor=color,
            edgecolor="#CBD5D9",
            linewidth=0.8,
        )
    )
    fig.text(x + 0.016, y + h - 0.028, label.upper(), color="#5D687A", fontsize=7.5, weight="bold")
    fig.text(x + 0.016, y + h - 0.067, value, color="#172033", fontsize=21, weight="bold")
    fig.text(x + 0.016, y + 0.020, note, color="#5D687A", fontsize=7)


def write_reproduction_pdf(payload: dict[str, object], pdf_path: Path = OUTPUT_PATH) -> Path:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.backends.backend_pdf import PdfPages

    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42
    mpl.rcParams["axes.unicode_minus"] = False

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(payload["rows"])
    remaining_gap_rows = list(payload["remaining_gap_rows"])
    counts = dict(payload["category_counts"])
    strict_counts = dict(payload["strict_category_counts"])
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["strict_audit_category"])].append(row)

    with PdfPages(pdf_path) as pdf:
        page_number = 1
        fig = plt.figure(figsize=(11.69, 8.27), facecolor="white")
        fig.patches.append(patches.Rectangle((0, 0.73), 1, 0.27, transform=fig.transFigure, color="#2F6F73"))
        fig.text(0.055, 0.895, "Literature Reproduction Audit", color="white", fontsize=28, weight="bold")
        fig.text(0.058, 0.845, "Translation-Invariant Spin Model Simplifier", color="#DDEDEE", fontsize=15)
        fig.text(0.058, 0.805, f"Generated {payload['generated_date']} from the strict local-reproduction audit", color="white", fontsize=10)

        _metric_card(
            fig,
            0.055,
            0.58,
            0.20,
            0.11,
            "Total",
            str(payload["total_standard_results"]),
            "registered literature results",
            "#EDF3F4",
        )
        _metric_card(
            fig,
            0.275,
            0.58,
            0.20,
            0.11,
            "Local",
            str(counts.get("local_recomputed", 0)),
            "legacy local count",
            "#DFF1E8",
        )
        _metric_card(
            fig,
            0.495,
            0.58,
            0.20,
            0.11,
            "Projection",
            str(counts.get("executable_projection", 0)),
            "executable but partial",
            "#FFF0D6",
        )
        _metric_card(
            fig,
            0.715,
            0.58,
            0.20,
            0.11,
            "Reference",
            str(counts.get("reference_only", 0)),
            "stored metadata",
            "#E9ECF2",
        )

        fig.text(0.055, 0.49, "Scope", color="#172033", fontsize=16, weight="bold")
        fig.text(0.055, 0.445, _wrap(payload["scope_note"], 135), color="#172033", fontsize=10.5, linespacing=1.45)
        fig.text(0.055, 0.34, "Strict Counts", color="#172033", fontsize=16, weight="bold")
        strict_summary = (
            f"strict_local_recomputed={strict_counts.get('strict_local_recomputed', 0)}, "
            f"local_projection_only={strict_counts.get('local_projection_only', 0)}, "
            f"executable_projection={strict_counts.get('executable_projection', 0)}, "
            f"reference_only={strict_counts.get('reference_only', 0)}."
        )
        fig.text(0.055, 0.305, _wrap(strict_summary, 135), color="#172033", fontsize=10.5, linespacing=1.45)
        fig.text(0.055, 0.245, "Direct Answer", color="#172033", fontsize=16, weight="bold")
        fig.text(0.055, 0.212, _wrap(payload["direct_answer"], 135), color="#172033", fontsize=10.5, linespacing=1.45)
        fig.text(0.055, 0.145, "Current Truth", color="#172033", fontsize=16, weight="bold")
        if strict_counts.get("strict_local_recomputed", 0) == payload["total_standard_results"]:
            truth = (
                f"All {payload['total_standard_results']} entries currently meet the stricter local "
                "recomputation, analytic reproduction, or direct published-observable parse criterion. "
                "There are no remaining strict reproduction gaps in this audit."
            )
        else:
            truth = (
                f"{strict_counts.get('strict_local_recomputed', 0)} of {payload['total_standard_results']} entries "
                "currently meet the stricter local recomputation/analytic reproduction criterion. The remaining "
                "entries require stronger numerical workflows, model parameters, finite-size scaling, or "
                "literature-specific calculations."
            )
        fig.text(0.055, 0.108, _wrap(truth, 135), color="#172033", fontsize=10.5, linespacing=1.45)
        fig.text(0.055, 0.075, f"Source rows: {PROJECT_ROOT / 'reports/literature_reproduction_audit.csv'}", color="#5D687A", fontsize=7)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_number += 1

        summary_rows = []
        for category in ("strict_local_recomputed", "local_projection_only", "executable_projection", "reference_only"):
            for row in grouped.get(category, []):
                if row["audit_category"] == "local_recomputed":
                    evidence = f"{row['local_check_kind']}: {row['local_check_evidence']}"
                elif row["audit_category"] == "executable_projection":
                    evidence = "projection observables: " + ", ".join(row["covered_computable_observables"])
                else:
                    evidence = "stored reference only"
                summary_rows.append(
                    (
                        row["strict_literature_match_label"],
                        STRICT_CATEGORY_LABELS[category],
                        row["name"],
                        row["observable"],
                        row["backend_needed"],
                        evidence,
                        category,
                    )
                )

        rows_per_page = 20
        headers = ["Match?", "Category", "Benchmark", "Observable", "Backend", "Evidence"]
        xs = [0.035, 0.105, 0.235, 0.455, 0.575, 0.695]
        widths = [0.055, 0.115, 0.20, 0.105, 0.105, 0.255]
        for start in range(0, len(summary_rows), rows_per_page):
            fig = plt.figure(figsize=(11.69, 8.27), facecolor="white")
            _draw_header(fig, "Strict Audit Entries", page_number)
            y = 0.90
            fig.patches.append(patches.Rectangle((0.03, y - 0.030), 0.94, 0.038, transform=fig.transFigure, facecolor="#EDF3F4", edgecolor="#CBD5D9"))
            for x, header in zip(xs, headers):
                fig.text(x, y - 0.012, header, color="#172033", fontsize=8.3, weight="bold", va="center")
            y -= 0.047
            for match_label, category_label, name, observable, backend, evidence, category in summary_rows[start : start + rows_per_page]:
                fill, ink = STRICT_CATEGORY_COLORS[str(category)]
                fig.patches.append(patches.Rectangle((0.03, y - 0.031), 0.94, 0.042, transform=fig.transFigure, facecolor="#FFFFFF", edgecolor="#E5EAEC", linewidth=0.5))
                fig.patches.append(patches.Rectangle((0.035, y - 0.024), 0.055, 0.026, transform=fig.transFigure, facecolor=fill, edgecolor=ink, linewidth=0.4))
                fig.patches.append(patches.Rectangle((0.105, y - 0.024), 0.115, 0.026, transform=fig.transFigure, facecolor=fill, edgecolor=ink, linewidth=0.4))
                values = [match_label, category_label, name, observable, backend, evidence]
                for index, (x, width, value) in enumerate(zip(xs, widths, values)):
                    text = _wrap(value, max(8, int(width * 115)))
                    font_name = "DejaVu Sans Mono" if index in (2, 3, 4, 5) else None
                    color = ink if index in (0, 1) else "#172033"
                    weight = "bold" if index in (0, 1) else None
                    fig.text(x, y - 0.010, text, color=color, fontsize=5.8, va="center", fontfamily=font_name, weight=weight, linespacing=1.1)
                y -= 0.042
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            page_number += 1

        fig = plt.figure(figsize=(11.69, 8.27), facecolor="white")
        _draw_header(fig, "Remaining Strict Gaps", page_number)
        fig.text(0.045, 0.895, "Rows Still Not Strictly Reproduced", color="#172033", fontsize=15, weight="bold")
        gap_intro = (
            "These entries have not been counted as strict literature reproductions. The notes below record what "
            "local calculation or probe was tried, and why it is weaker than the registered observable."
        )
        fig.text(0.045, 0.852, _wrap(gap_intro, 142), color="#172033", fontsize=9.5, linespacing=1.35)
        fig.text(
            0.045,
            0.795,
            f"Remaining strict gaps: {len(remaining_gap_rows)} of {payload['total_standard_results']} entries.",
            color="#5D687A",
            fontsize=9,
            weight="bold",
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_number += 1

        page_gap_rows: list[dict[str, object]] = []
        current_height = 0.0
        max_height = 0.805

        def flush_gap_page() -> None:
            nonlocal page_number, page_gap_rows, current_height
            if not page_gap_rows:
                return
            fig = plt.figure(figsize=(11.69, 8.27), facecolor="white")
            _draw_header(fig, "Remaining Strict Gaps", page_number)
            y = 0.895
            for row in page_gap_rows:
                category = str(row["strict_audit_category"])
                fill, ink = STRICT_CATEGORY_COLORS[category]
                title = f"{row['name']}  |  {STRICT_CATEGORY_LABELS[category]}"
                subtitle = f"observable: {row['observable']}    backend: {row['backend_needed']}"
                negative = str(row["strict_reproduction_negative_evidence"])
                gap_action = str(row["strict_reproduction_gap_action"])
                local_check = str(row["local_check_kind"] or "-")
                evidence = (
                    f"local check: {local_check}. "
                    f"negative evidence: {negative} "
                    f"upgrade requirement: {gap_action}"
                )
                evidence_lines = textwrap.wrap(
                    evidence,
                    width=154,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                card_height = max(0.115, 0.080 + 0.017 * len(evidence_lines))
                fig.patches.append(
                    patches.FancyBboxPatch(
                        (0.035, y - card_height),
                        0.93,
                        card_height - 0.010,
                        boxstyle="round,pad=0.004,rounding_size=0.004",
                        transform=fig.transFigure,
                        facecolor="#FFFFFF",
                        edgecolor="#DDE5E8",
                        linewidth=0.6,
                    )
                )
                fig.patches.append(
                    patches.Rectangle(
                        (0.043, y - 0.036),
                        0.20,
                        0.023,
                        transform=fig.transFigure,
                        facecolor=fill,
                        edgecolor=ink,
                        linewidth=0.4,
                    )
                )
                fig.text(0.050, y - 0.024, STRICT_CATEGORY_LABELS[category], color=ink, fontsize=6.5, weight="bold", va="center")
                fig.text(0.255, y - 0.023, _wrap(title, 104), color="#172033", fontsize=7.2, weight="bold", va="center", fontfamily="DejaVu Sans Mono")
                fig.text(0.050, y - 0.053, _wrap(subtitle, 145), color="#5D687A", fontsize=6.8, va="center", fontfamily="DejaVu Sans Mono")
                fig.text(
                    0.050,
                    y - 0.078,
                    "\n".join(evidence_lines),
                    color="#172033",
                    fontsize=6.15,
                    va="top",
                    linespacing=1.18,
                    fontfamily="DejaVu Sans Mono",
                )
                y -= card_height
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            page_number += 1
            page_gap_rows = []
            current_height = 0.0

        for row in remaining_gap_rows:
            evidence = (
                f"local check: {row['local_check_kind'] or '-'}. "
                f"negative evidence: {row['strict_reproduction_negative_evidence']} "
                f"upgrade requirement: {row['strict_reproduction_gap_action']}"
            )
            row_height = max(0.115, 0.080 + 0.017 * len(textwrap.wrap(evidence, width=154)))
            if current_height + row_height > max_height:
                flush_gap_page()
            page_gap_rows.append(row)
            current_height += row_height
        flush_gap_page()

    return pdf_path


def main() -> int:
    payload = build_reproduction_pdf_payload()
    pdf_path = write_reproduction_pdf(payload)
    print(pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
