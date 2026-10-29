#!/usr/bin/env python3
"""Emit model/request examples to stdout. Contains input models, no answers."""

import argparse
import itertools
import json
import numpy as np


def cubic_input(exchange, request):
    operations = []
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            rotation = np.eye(3, dtype=int)[list(permutation)] * np.array(signs)[:, None]
            operations.append({"operation_ref": "symop:%d" % len(operations),
                               "rotation": rotation.tolist(), "translation": [0, 0, 0]})
    model = {
        "schema_version": "lattice-term-contract/v1",
        "lattice_structure": {"lattice_vectors": np.eye(3).tolist(),
                              "basis_sites": [{"site_ref": "site:0", "position": [0, 0, 0]}]},
        "local_hilbert": {
            "operator_bases": {"operator-basis:spin": {"kind": "spin_vector", "labels": ["Sx", "Sy", "Sz"]}},
            "classical_spaces": {"classical-space:spin": {"kind": "unit_vector_sphere", "dimension": 3}},
        },
        "symmetry": {"source": {"international_symbol": "Pm-3m", "number": 221},
                     "operations": operations, "unresolved": []},
        "parameters": {},
        "term_attachments": {"site_terms": [], "higher_body_terms": [], "bond_terms": [
            {"term_ref": "term:J%d" % axis,
             "cluster": [{"site": 0, "translation": [0, 0, 0]},
                         {"site": 0, "translation": delta.tolist()}],
             "operator_basis_ref": "operator-basis:spin",
             "coordinate_convention": "global_crystallographic",
             "payload": {"kind": "bilinear_exchange_matrix", "matrix": (exchange * np.eye(3)).tolist()}}
            for axis, delta in enumerate(np.eye(3, dtype=int))]},
    }
    return {"model": model, "request": request}


def example_input(name, task=None):
    if name == "dipoles":
        return {"model": {"lattice_vectors": (3 * np.eye(3)).tolist(),
                          "fractional_positions": [[0.1, 0.2, 0.3], [0.6, 0.4, 0.8]],
                          "moments": [[0, 0, 1], [0, 0, -1]]},
                "request": {"task": "dipolar_ewald", "alpha": 0.9,
                            "real_cutoff": 9.0, "reciprocal_cutoff": 12.0, "boundary": "tin_foil"}}
    exchange = -1.0 if name == "cubic-fm" else 1.0
    request = {"task": task or "classical_ground_state", "supercell_shape": [2, 2, 2],
               "spin_length": 0.5, "spin": 0.5, "starts": 4, "seed": 42,
               "stationarity_tolerance": 1e-9}
    if request["task"] in {"fourier_exchange_spectrum", "spin_wave_spectrum"}:
        request["reduced_momenta"] = [[0, 0, 0], [.25, 0, 0], [.5, .5, .5]]
    if request["task"] == "spin_wave_spectrum":
        request["zero_point_mesh"] = [6, 6, 6]
    if request["task"] in {"classical_monte_carlo", "classical_finite_size"}:
        request.update({"spin_length": 1.0, "temperatures": [0.7, 1.2, 1.6, 2.0, 3.0],
                        "burn_in": 1000, "sweeps": 3000,
                        "order_momentum": [0, 0, 0] if exchange < 0 else [.5, .5, .5]})
    if request["task"] == "classical_finite_size":
        request["supercell_shapes"] = [[2, 2, 2], [4, 4, 4]]
    if request["task"] == "quantum_low_energy":
        request.update({"supercell_shape": [2, 2, 4], "eigenvalues": 2, "seed": 18})
    return cubic_input(exchange, request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=["cubic-fm", "cubic-af", "dipoles"])
    parser.add_argument("--task", choices=["fourier_exchange_spectrum", "classical_ground_state",
                                          "spin_wave_spectrum", "classical_monte_carlo",
                                          "classical_finite_size", "quantum_low_energy"])
    args = parser.parse_args()
    print(json.dumps(example_input(args.model, args.task), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
