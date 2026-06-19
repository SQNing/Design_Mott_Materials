#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.solve_pseudospin_orbital_pipeline import solve_from_parsed_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed-payload", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--docs-dir", required=True)
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument(
        "--classical-bond_label",
        choices=["spin-only", "cpn"],
        default=None,
    )
    parser.add_argument(
        "--classical-method",
        default="cpn-generalized-lt",
        choices=[
            "auto",
            "restricted-product-state",
            "sun-gswt-cpn",
            "sun-gswt-single-q",
            "cpn-local-ray-minimize",
            "sunny-cpn-minimize",
            "cpn-generalized-lt",
            "cpn-luttinger-tisza",
        ],
    )
    parser.add_argument("--supercell-shape", type=int, nargs=3, metavar=("NX", "NY", "NZ"), default=(1, 1, 1))
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-linear-size", type=int, default=0)
    parser.add_argument("--convergence-repeats", type=int, default=2)
    parser.add_argument("--max-sweeps", type=int, default=200)
    parser.add_argument("--no-gswt", action="store_true")
    parser.add_argument("--gswt-backend", choices=["sunny", "python"], default="sunny")
    parser.add_argument(
        "--z-harmonic-reference-mode",
        choices=["input", "refined-retained-local"],
        default="input",
    )
    parser.add_argument(
        "--glt-certification-mode",
        choices=["off", "auto", "required"],
        default="off",
    )
    parser.add_argument(
        "--glt-solver-mode",
        choices=["fast", "certified"],
        default="fast",
    )
    parser.add_argument(
        "--classical-output-compatibility",
        choices=["canonical", "legacy"],
        default="canonical",
    )
    args = parser.parse_args()

    parsed_payload = json.loads(Path(args.parsed_payload).read_text(encoding="utf-8"))
    manifest = solve_from_parsed_payload(
        parsed_payload,
        output_dir=Path(args.output_dir),
        docs_dir=Path(args.docs_dir),
        compile_pdf=not args.no_pdf,
        classical_bond_label=None if args.classical_bond_label is None else str(args.classical_bond_label),
        classical_method=str(args.classical_method),
        supercell_shape=tuple(int(value) for value in args.supercell_shape),
        starts=int(args.starts),
        seed=int(args.seed),
        max_linear_size=int(args.max_linear_size),
        convergence_repeats=int(args.convergence_repeats),
        max_sweeps=int(args.max_sweeps),
        run_gswt=not args.no_gswt,
        gswt_backend=str(args.gswt_backend),
        z_harmonic_reference_mode=str(args.z_harmonic_reference_mode),
        glt_certification_mode=str(args.glt_certification_mode),
        glt_solver_mode=str(args.glt_solver_mode),
        compatibility_export_mode=str(args.classical_output_compatibility),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
