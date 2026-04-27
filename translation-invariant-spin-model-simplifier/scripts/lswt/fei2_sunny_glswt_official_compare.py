#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lswt.fei2_sunny_glswt_cases import (
    classify_fei2_sunny_glswt_result,
    official_fei2_reference_metadata,
)
from lswt.sun_gswt_driver import run_sun_gswt


def _load_case_payload(case):
    if isinstance(case.get("gswt_payload"), dict):
        return dict(case["gswt_payload"])
    payload_path = case.get("gswt_payload_path")
    if payload_path:
        return json.loads(Path(payload_path).read_text(encoding="utf-8"))
    raise ValueError(f"case {case.get('case_id')!r} is missing gswt_payload or gswt_payload_path")


def _default_cases():
    return []


def _write_markdown_summary(path, payload):
    lines = [
        "# FeI2 Sunny GLSWT Official Comparison",
        "",
        f"- Cases: {len(payload.get('cases', []))}",
        "",
    ]
    for case in payload.get("cases", []):
        lines.append(f"- `{case['case_id']}`: `{case['category']}`")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_official_compare(*, output_json, output_markdown, cases=None, julia_cmd=None):
    cases = _default_cases() if cases is None else list(cases)
    case_summaries = []
    for case in cases:
        payload = _load_case_payload(case)
        result = run_sun_gswt(payload, julia_cmd=julia_cmd)
        summary = classify_fei2_sunny_glswt_result(case.get("case_id", "unknown"), result)
        summary["source"] = case.get("source")
        case_summaries.append(summary)

    output_payload = {
        "official_reference": official_fei2_reference_metadata(),
        "cases": case_summaries,
    }
    output_json = Path(output_json)
    output_markdown = Path(output_markdown)
    output_json.write_text(json.dumps(output_payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown_summary(output_markdown, output_payload)
    return output_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    parser.add_argument("--cases-json")
    parser.add_argument("--julia-cmd")
    args = parser.parse_args()

    cases = None
    if args.cases_json:
        cases = json.loads(Path(args.cases_json).read_text(encoding="utf-8"))

    run_official_compare(
        output_json=args.output_json,
        output_markdown=args.output_markdown,
        cases=cases,
        julia_cmd=args.julia_cmd,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
