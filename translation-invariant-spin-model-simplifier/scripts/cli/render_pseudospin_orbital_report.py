#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload
from output.render_pseudospin_orbital_report import (
    write_pseudospin_orbital_reports,
    write_stage_markdown,
)
from simplify.group_pseudospin_orbital_terms import group_pseudospin_orbital_terms
from simplify.simplify_pseudospin_orbital_payload import simplify_pseudospin_orbital_payload


def _phase_summary(parsed_payload, simplified_payload, grouped_payload):
    lines = [
        "# Pseudospin-Orbital Report Phase",
        "",
        "## Conventions",
        "",
        "- local space: pseudospin_orbital",
        "- basis order: orbital_major_spin_minor",
        f"- local_dimension: {parsed_payload['inferred']['local_dimension']}",
        f"- orbital_count: {parsed_payload['inferred']['orbital_count']}",
        "",
        "## Process",
        "",
        "- parsed POSCAR into lattice metadata",
        "- parsed wannier-style hr.dat into R-resolved bond blocks",
        "- projected bond matrices into pseudospin-orbital operator basis",
        "- simplified coefficients into readable and residual channels",
        "- grouped bonds by distance shells",
        "",
        "## Current counts",
        "",
        f"- bond blocks: {len(parsed_payload['bond_blocks'])}",
        f"- grouped bonds: {len(grouped_payload['bonds'])}",
        f"- simplification candidates: {len(simplified_payload['simplification']['candidates'])}",
    ]
    return "\n".join(lines)


def render_from_files(poscar_path, hr_path, output_dir, docs_dir, compile_pdf=True, coefficient_tolerance=1e-10):
    parsed_payload = build_pseudospin_orbital_payload(
        poscar_path=poscar_path,
        hr_path=hr_path,
        coefficient_tolerance=coefficient_tolerance,
    )
    simplified_payload = simplify_pseudospin_orbital_payload(parsed_payload)
    grouped_payload = group_pseudospin_orbital_terms(parsed_payload)
    manifest = write_pseudospin_orbital_reports(
        parsed_payload,
        grouped_payload,
        output_dir=output_dir,
        compile_pdf=compile_pdf,
    )

    phase_note = write_stage_markdown(
        _phase_summary(parsed_payload, simplified_payload, grouped_payload),
        docs_dir=docs_dir,
    )

    output_dir = Path(output_dir)
    (output_dir / "parsed_payload.json").write_text(json.dumps(parsed_payload, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "simplified_payload.json").write_text(json.dumps(simplified_payload, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "grouped_terms.json").write_text(json.dumps(grouped_payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest["status"] = "ok"
    manifest["artifacts"] = {
        "parsed_payload": str(output_dir / "parsed_payload.json"),
        "simplified_payload": str(output_dir / "simplified_payload.json"),
        "grouped_terms": str(output_dir / "grouped_terms.json"),
        "phase_note": str(phase_note),
    }
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poscar", required=True)
    parser.add_argument("--hr", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--docs-dir", required=True)
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--coefficient-tolerance", type=float, default=1e-10)
    args = parser.parse_args()

    manifest = render_from_files(
        poscar_path=Path(args.poscar),
        hr_path=Path(args.hr),
        output_dir=Path(args.output_dir),
        docs_dir=Path(args.docs_dir),
        compile_pdf=not args.no_pdf,
        coefficient_tolerance=float(args.coefficient_tolerance),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
