#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from lswt.fei2_sunny_glswt_cases import (
    classify_fei2_sunny_glswt_result,
    dispersion_summary_from_result,
)
from lswt.python_glswt_driver import run_python_glswt_driver
from lswt.sun_gswt_driver import run_sun_gswt


def _difference_bucket(python_summary, sunny_summary):
    python_q = python_summary.get("omega_min_q_vector")
    sunny_q = sunny_summary.get("omega_min_q_vector")
    python_omega = python_summary.get("omega_min")
    sunny_omega = sunny_summary.get("omega_min")
    if python_q == sunny_q and python_omega is not None and sunny_omega is not None:
        if abs(float(python_omega) - float(sunny_omega)) <= 0.05:
            return "match_or_near_match"
        return "backend_physics_difference"
    return "state_difference"


def compare_python_vs_sunny_case(*, case_id, python_result, sunny_result):
    sunny_case_summary = classify_fei2_sunny_glswt_result(case_id, sunny_result)
    if sunny_case_summary["category"] == "blocked_by_contract":
        return {
            "case_id": str(case_id),
            "comparison_status": "skipped",
            "reason": "sunny-contract-invalid",
            "sunny_category": sunny_case_summary["category"],
            "sunny_error_code": sunny_case_summary.get("error_code"),
        }

    python_summary = dispersion_summary_from_result(python_result)
    sunny_summary = dispersion_summary_from_result(sunny_result)
    return {
        "case_id": str(case_id),
        "comparison_status": "compared",
        "python": python_summary,
        "sunny": sunny_summary,
        "difference_bucket": _difference_bucket(python_summary, sunny_summary),
    }


def _load_case_payload(case, payload_key):
    payload = case.get(payload_key)
    if isinstance(payload, dict):
        return dict(payload)
    payload_path = case.get(f"{payload_key}_path")
    if payload_path:
        return json.loads(Path(payload_path).read_text(encoding="utf-8"))
    raise ValueError(f"case {case.get('case_id')!r} is missing {payload_key} or {payload_key}_path")


def _write_markdown_summary(path, payload):
    lines = [
        "# FeI2 Python vs Sunny GLSWT Comparison",
        "",
        f"- Cases: {len(payload.get('cases', []))}",
        "",
    ]
    for case in payload.get("cases", []):
        lines.append(f"- `{case['case_id']}`: `{case['comparison_status']}`")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_python_vs_sunny_compare(*, output_json, output_markdown, cases, julia_cmd=None):
    case_summaries = []
    for case in cases:
        python_payload = _load_case_payload(case, "python_gswt_payload")
        sunny_payload = _load_case_payload(case, "sunny_gswt_payload")
        python_result = run_python_glswt_driver(python_payload)
        sunny_result = run_sun_gswt(sunny_payload, julia_cmd=julia_cmd)
        case_summaries.append(
            compare_python_vs_sunny_case(
                case_id=case.get("case_id", "unknown"),
                python_result=python_result,
                sunny_result=sunny_result,
            )
        )

    output_payload = {"cases": case_summaries}
    output_json = Path(output_json)
    output_markdown = Path(output_markdown)
    output_json.write_text(json.dumps(output_payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown_summary(output_markdown, output_payload)
    return output_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    parser.add_argument("--cases-json", required=True)
    parser.add_argument("--julia-cmd")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases_json).read_text(encoding="utf-8"))
    run_python_vs_sunny_compare(
        output_json=args.output_json,
        output_markdown=args.output_markdown,
        cases=cases,
        julia_cmd=args.julia_cmd,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
