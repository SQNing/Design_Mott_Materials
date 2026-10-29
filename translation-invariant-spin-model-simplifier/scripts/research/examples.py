"""Small reproducible model inputs. No reference answers are solver inputs."""
import argparse
import copy
import json
from pathlib import Path


def identity_symmetry():
    return {"source": {"international_symbol": "P1", "number": 1},
            "operations": [{"operation_ref": "identity",
                            "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                            "translation": [0., 0., 0.]}], "unresolved": []}


def _base(space, basis, positions):
    return {"schema_version": "lattice-term-contract/v1",
            "local_hilbert": {"operator_bases": {"basis": basis},
                              "classical_spaces": {"space": space}},
            "lattice_structure": {
                "lattice_vectors": [[1.1, 0., 0.], [.17, 1.23, 0.], [.09, .21, 1.37]],
                "basis_sites": [{"site_ref": "site:%s" % i, "position": p} for i, p in enumerate(positions)],
                "bond_orbits": []},
            "symmetry": identity_symmetry(), "parameters": {},
            "term_attachments": {"site_terms": [], "bond_terms": [], "higher_body_terms": [], "term_sets": []},
            "units": {"energy": "dimensionless model units", "hbar": 1}}


def _term(name, sites, translations, kind, matrix):
    return {"term_ref": name, "cluster": [{"site": s, "translation": t} for s, t in zip(sites, translations)],
            "operator_basis_ref": "basis",
            "payload": {"kind": kind, "matrix": {"shape": [len(matrix), len(matrix)], "data": matrix}},
            "coordinate_convention": "global_crystallographic",
            "attach_to": {"kind": "explicit_cluster", "orientation": "explicit"}}


def multisublattice_spin():
    """Four inequivalent sites of a triclinic periodic exchange network."""
    model = _base({"kind": "unit_vector_sphere", "dimension": 3},
                  {"kind": "spin_vector", "labels": ["Sx", "Sy", "Sz"]},
                  [[0., 0., 0.], [.19, .23, .31], [.43, .11, .67], [.71, .59, .37]])
    pairs = [(i, j, [0, 0, 0]) for i in range(4) for j in range(i + 1, 4)]
    pairs += [(i, (i + 1) % 4, t) for i in range(4) for t in ([1, 0, 0], [0, 1, 0], [0, 0, 1])]
    for index, (i, j, shift) in enumerate(pairs):
        strength = .73 + .013 * index
        matrix = [[-strength, 0., 0.], [0., -.91 * strength, 0.], [0., 0., -1.17 * strength]]
        model["term_attachments"]["bond_terms"].append(
            _term("exchange:%s" % index, [i, j], [[0, 0, 0], shift], "bilinear_exchange_matrix", matrix))
    return model


def retained_three_level():
    model = _base({"kind": "complex_projective_space", "dimension": 3},
                  {"kind": "dense_local_matrix_units", "dimension": 3,
                   "symmetry_actions": {"identity": {"matrix": [[int(i == j) for j in range(9)] for i in range(9)]}}},
                  [[0., 0., 0.]])
    model["local_basis_labels"] = ["g", "e1", "e2"]
    onsite = [[-.2, 0., 0.], [0., .6, 0.], [0., 0., 1.4]]
    pair = [[0. for _ in range(9)] for _ in range(9)]
    pair[0][0] = -.31
    pair[1][3] = {"kind": "complex", "re": .05, "im": .03}
    pair[3][1] = {"kind": "complex", "re": .05, "im": -.03}
    pair[2][6] = pair[6][2] = .041
    model["term_attachments"]["site_terms"] = [
        _term("onsite:levels", [0], [[0, 0, 0]], "local_operator_matrix", onsite)]
    model["term_attachments"]["bond_terms"] = [
        _term("pair:general", [0, 0], [[0, 0, 0], [1, 0, 0]], "pair_matrix", pair)]
    return model


def request_for(model, question, tasks):
    return {"model": copy.deepcopy(model), "question": question, "requested_tasks": list(tasks),
            "budget": {"max_solver_runs": 8, "max_wall_time_seconds": 180, "max_memory_mb": 2048}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    for name, model in (("multisublattice-spin", multisublattice_spin()),
                        ("retained-three-level", retained_three_level())):
        request = request_for(model, "Find a finite periodic classical reference and test its harmonic stability.",
                              ["classical_ground_state", "harmonic_spectrum"])
        with (root / (name + ".json")).open("x") as stream:
            json.dump(request, stream, indent=2)


if __name__ == "__main__":
    main()
