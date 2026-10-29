"""Explicit physical approximations, with an immutable full-model control."""
from copy import deepcopy
from pathlib import Path
import numpy as np

from research.contracts import digest, json_safe, restore_complex
from research.state import event, read_json, write_json


def _array(value):
    return np.asarray(restore_complex(value), dtype=complex)


def transform_model(full_model, transformation):
    model = deepcopy(restore_complex(full_model))
    if model.get("schema_version") != "canonical-hamiltonian/v1":
        raise ValueError("reduction requires the complete canonical Hamiltonian")
    original = deepcopy(model)
    kind = transformation.get("kind")
    if kind == "drop_terms":
        selected = transformation.get("term_refs", [])
        if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected):
            raise ValueError("drop_terms needs a nonempty unique list of term_refs")
        known = {t["term_ref"] for t in model["terms"]}
        if set(selected) - known:
            raise ValueError("unknown term_refs: " + str(sorted(set(selected) - known)))
        removed = [t for t in model["terms"] if t["term_ref"] in selected]
        model["terms"] = [t for t in model["terms"] if t["term_ref"] not in selected]
        distances = []
        for term in removed:
            try:
                norm = float(np.linalg.norm(_array(term["coefficient"])))
            except (ValueError, TypeError):
                norm = None
            distances.append({"term_ref": term["term_ref"], "coefficient_frobenius_norm": norm})
        return model, {"kind": kind, "removed_terms": removed,
                       "coefficient_distances": distances,
                       "physical_error": None, "assessment": "requires_physical_validation",
                       "limitations": ["Coefficient norms alone do not bound the requested observables."]}
    if kind != "project_local_space":
        raise ValueError("unsupported reduction kind: " + str(kind))
    spaces = model["local_hilbert"].get("classical_spaces", {})
    if not spaces or any(s.get("kind") != "complex_projective_space" for s in spaces.values()):
        raise ValueError("local-space projection requires an explicitly retained local Hilbert space")
    dimensions = {int(s["dimension"]) for s in spaces.values()}
    if len(dimensions) != 1:
        raise ValueError("projection requires a common local dimension")
    dimension = dimensions.pop()
    embedding = _array(transformation.get("isometry"))
    if (embedding.ndim != 2 or embedding.shape[0] != dimension or
            not 2 <= embedding.shape[1] < dimension or not np.all(np.isfinite(embedding))):
        raise ValueError("isometry must have shape N by n, with 2 <= n < N")
    reduced_dimension = embedding.shape[1]
    orthogonality = float(np.linalg.norm(embedding.conj().T @ embedding - np.eye(reduced_dimension)))
    if orthogonality > 1e-10:
        raise ValueError("isometry columns must be orthonormal")
    labels = transformation.get("basis_labels", ["retained:%s" % i for i in range(reduced_dimension)])
    if len(labels) != reduced_dimension or len(set(labels)) != reduced_dimension:
        raise ValueError("basis_labels must identify each retained local state")
    # Row-major vectorization of P O P^dagger is (P tensor P*) vec(O).
    operator_embedding = np.kron(embedding, embedding.conjugate())
    used_bases = {t.get("operator_basis_ref") for t in model["terms"]}
    bases = model["local_hilbert"].get("operator_bases", {})
    symmetry_residuals = []
    for reference in used_bases:
        basis = bases.get(reference, {})
        if basis.get("kind") != "dense_local_matrix_units" or int(basis.get("dimension", 0)) != dimension:
            raise ValueError("projection needs declared dense local matrix units for every term")
        for operation, record in basis.get("symmetry_actions", {}).items():
            action = _array(record["matrix"] if isinstance(record, dict) else record)
            if action.shape != (dimension ** 2, dimension ** 2):
                raise ValueError("local operator symmetry action has the wrong dimension")
            reduced = operator_embedding.conj().T @ action @ operator_embedding
            residual = float(np.linalg.norm(action @ operator_embedding - operator_embedding @ reduced))
            symmetry_residuals.append({"basis": reference, "operation": operation, "residual": residual})
            if residual > 1e-9:
                raise ValueError("retained subspace is not closed under structural symmetry: " + operation)
            basis["symmetry_actions"][operation] = {"matrix": reduced.tolist()}
        basis["dimension"] = reduced_dimension
        if "labels" in basis:
            basis["labels"] = ["E%s_%s" % (i, j) for i in range(reduced_dimension) for j in range(reduced_dimension)]
    diagnostics = []
    for term in model["terms"]:
        family, arity = term["operator_family"], term["arity"]
        if family == "local_operator_matrix" and arity == 1:
            lift = embedding
        elif family == "pair_matrix" and arity == 2:
            from common.canonical_hamiltonian import pair_coefficient_representation
            if pair_coefficient_representation(term, original) != "full_pair_operator":
                raise ValueError("projection requires full pair operators, not coefficient tensors")
            lift = np.kron(embedding, embedding)
            term["coefficient_representation"] = "full_pair_operator"
        else:
            raise ValueError("projection does not support complete-model term " + term["term_ref"])
        matrix = _array(term["coefficient"])
        if matrix.shape != (lift.shape[0], lift.shape[0]) or not np.all(np.isfinite(matrix)):
            raise ValueError("operator dimension mismatch: " + term["term_ref"])
        if not np.allclose(matrix, matrix.conj().T, atol=1e-10, rtol=0):
            raise ValueError("non-Hermitian operator: " + term["term_ref"])
        reduced = lift.conj().T @ matrix @ lift
        leakage = matrix @ lift - lift @ reduced
        diagnostics.append({"term_ref": term["term_ref"],
                            "discarded_coupling_norm": float(np.linalg.norm(leakage, 2)),
                            "full_shape": list(matrix.shape), "reduced_shape": list(reduced.shape)})
        term["coefficient"] = reduced.tolist()
    for record in spaces.values():
        record["dimension"] = reduced_dimension
    model["local_basis_labels"] = list(labels)
    return model, {"kind": kind, "full_dimension": dimension, "reduced_dimension": reduced_dimension,
                   "isometry": embedding.tolist(), "orthogonality_residual": orthogonality,
                   "symmetry_subspace_residuals": symmetry_residuals, "term_mapping": diagnostics,
                   "physical_error": None, "assessment": "requires_physical_validation",
                   "limitations": ["Direct subspace projection only; virtual-excitation corrections are not included.",
                                   "The projection is not certified by a small coupling norm alone."]}


def propose_reduction(root, state, action):
    identifier = action["action_id"]
    existing = state.get("reductions", {}).get(identifier)
    if existing:
        record = read_json(existing["record"])
        if record["action_hash"] != digest(action):
            raise ValueError("action_id already used with different content")
        return record
    if state["model"]["status"] != "ready":
        raise ValueError("a reduction needs a fully prepared control model")
    full = read_json(Path(state["model"]["directory"]) / "solver_model.json")
    transformed, mapping = transform_model(full, action["transformation"])
    directory = Path(root) / "reductions" / identifier
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "action.json", action, exclusive=True)
    write_json(directory / "mapping.json", mapping, exclusive=True)
    from research.models import prepare_model
    candidate = prepare_model(transformed, {"physics_policy": {"symmetry_repair": False}}, directory, 1)
    record = {"schema_version": "reduction-candidate/v1", "candidate_id": identifier,
              "action_hash": digest(action), "parent_model_id": state["model"]["model_id"],
              "parent_directory": state["model"]["directory"], "candidate": candidate,
              "status": "ready" if candidate["status"] == "ready" else "rejected",
              "transformation": json_safe(mapping),
              "validation_status": "not_assessed",
              "complexity": {"full_terms": len(full["terms"]), "candidate_terms": len(transformed["terms"]),
                             "full_dimension": mapping.get("full_dimension"),
                             "candidate_dimension": mapping.get("reduced_dimension")},
              "limitations": mapping["limitations"]}
    write_json(directory / "record.json", record, exclusive=True)
    state.setdefault("reductions", {})[identifier] = {"record": str(directory / "record.json")}
    state["answer_status"] = "pending"
    write_json(Path(root) / "state.json", state)
    event(root, {"type": "propose_reduction", "action": action, "candidate_id": identifier})
    return record
