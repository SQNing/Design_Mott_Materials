from __future__ import annotations

from hamiltonian_transformation import analyze_low_energy_spin_manifold
from hamiltonian_transformation.example_cases import build_abstract_spin_only_demo_case


def main() -> None:
    demo = build_abstract_spin_only_demo_case()
    result = analyze_low_energy_spin_manifold(**demo)
    diagnostics = result["abstract_diagnostics"]
    hamiltonian = diagnostics["hamiltonian_closure"]
    observable = diagnostics["observable_closure"]

    print(f"decision: {result['decision']}")
    print(f"candidate_spin: {result['candidate_spin']}")
    print(f"hamiltonian target source: {hamiltonian['target_source']}")
    print(f"hamiltonian status: {hamiltonian['status']}")
    print(f"observable available: {observable['available']}")
    if observable["available"]:
        print(f"tested observables: {', '.join(observable['tested_observables'])}")
    else:
        print(f"observable reason: {observable['reason']}")
    print(f"overall_status: {diagnostics['overall_status']}")


if __name__ == "__main__":
    main()
