"""Explicit coupling interventions on the complete canonical Hamiltonian."""
from copy import deepcopy
from pathlib import Path
import math
import numpy as np

from research.contracts import digest, restore_complex, validate_id
from research.state import event, read_json, write_json


def _groups(full, groups):
    if not isinstance(groups, list) or not groups:
        raise ValueError("groups must be a nonempty list of explicit term selections")
    known = {term["term_ref"] for term in full["terms"]}
    identifiers, selected = set(), set()
    for group in groups:
        if not isinstance(group, dict) or set(group) - {"group_id", "term_refs", "description"}:
            raise ValueError("invalid intervention group")
        identifier = validate_id(group.get("group_id"))
        terms = group.get("term_refs")
        if identifier in identifiers:
            raise ValueError("duplicate group_id")
        if not isinstance(group.get("description"), str) or not group["description"].strip():
            raise ValueError("each group needs a physical description")
        if (not isinstance(terms, list) or not terms or
                any(not isinstance(t, str) for t in terms) or len(set(terms)) != len(terms)):
            raise ValueError("term_refs must be a nonempty list of unique strings")
        if set(terms) - known:
            raise ValueError("unknown term_refs: " + str(sorted(set(terms) - known)))
        if selected.intersection(terms):
            raise ValueError("intervention groups must not overlap")
        identifiers.add(identifier)
        selected.update(terms)
    return identifiers


def _factors(factors, identifiers):
    if not isinstance(factors, dict) or set(factors) != identifiers:
        raise ValueError("each point must explicitly give a factor for every group")
    for value in factors.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("coupling factors must be finite real numbers")


def scale_terms(full_model, groups, factors):
    model = deepcopy(restore_complex(full_model))
    if model.get("schema_version") != "canonical-hamiltonian/v1":
        raise ValueError("mechanism interventions require a complete canonical Hamiltonian")
    identifiers = _groups(model, groups)
    _factors(factors, identifiers)
    scales = {term: factors[g["group_id"]] for g in groups for term in g["term_refs"]}
    for term in model["terms"]:
        if term["term_ref"] in scales:
            coefficient = np.asarray(term["coefficient"], dtype=complex)
            if not np.all(np.isfinite(coefficient)):
                raise ValueError("interventions require finite numeric canonical coefficients")
            scaled = coefficient * scales[term["term_ref"]]
            if not np.all(np.isfinite(scaled)):
                raise ValueError("scaled coefficient overflow")
            # Preserve real spin coefficients as real scalars/arrays.
            if np.all(scaled.imag == 0):
                scaled = scaled.real
            term["coefficient"] = scaled.tolist()
    return model


def propose_mechanism(root, state, action):
    identifier = action["action_id"]
    previous = state.get("mechanisms", {}).get(identifier)
    if previous:
        record = read_json(previous["record"])
        if record["action_hash"] != digest(action):
            raise ValueError("action_id already used with different content")
        return record
    if state["model"]["status"] != "ready":
        raise ValueError("mechanism study needs a fully prepared complete model")
    if not isinstance(action.get("question"), str) or not action["question"].strip():
        raise ValueError("mechanism study needs an explicit physical question")
    full = read_json(Path(state["model"]["directory"]) / "solver_model.json")
    groups = deepcopy(action.get("groups"))
    identifiers = _groups(full, groups)
    points = deepcopy(action.get("points"))
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("provide a full-model control and at least one intervention point")
    point_ids, settings_seen, baseline = set(), set(), []
    for point in points:
        if not isinstance(point, dict) or set(point) != {"point_id", "factors"}:
            raise ValueError("each point needs only point_id and factors")
        point_id = validate_id(point["point_id"])
        _factors(point["factors"], identifiers)
        settings_key = tuple(float(point["factors"][g]) for g in sorted(identifiers))
        if point_id in point_ids or settings_key in settings_seen:
            raise ValueError("duplicate point_id or coupling point")
        point_ids.add(point_id)
        settings_seen.add(settings_key)
        if all(v == 1 for v in point["factors"].values()):
            baseline.append(point_id)
    if len(baseline) != 1:
        raise ValueError("exactly one point must be the complete-model control (all factors equal one)")
    directory = Path(root) / "mechanisms" / identifier
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "action.json", action, exclusive=True)
    from research.models import prepare_model
    for point in points:
        if point["point_id"] == baseline[0]:
            point["model"] = deepcopy(state["model"])
        else:
            transformed = scale_terms(full, groups, point["factors"])
            point["model"] = prepare_model(transformed, {"physics_policy": {"symmetry_repair": False}},
                                           directory / "points" / point["point_id"], 1)
    record = {
        "schema_version": "mechanism-plan/v1", "mechanism_id": identifier,
        "action_hash": digest(action), "parent_model_id": state["model"]["model_id"],
        "parent_directory": state["model"]["directory"], "question": action["question"],
        "groups": groups, "points": points, "baseline_point_id": baseline[0],
        "status": "ready" if all(p["model"]["status"] == "ready" for p in points) else "rejected",
        "limitations": ["Interventions act on the complete canonical model with the original structural symmetry.",
                        "No assumption of a unique mechanism or validity beyond the sampled couplings and observables.",
                        "A successful plan does not establish any physical hypothesis."]}
    path = directory / "record.json"
    write_json(path, record, exclusive=True)
    state.setdefault("mechanisms", {})[identifier] = {"record": str(path)}
    state["answer_status"] = "pending"
    write_json(Path(root) / "state.json", state)
    event(root, {"type": "propose_mechanism", "action": action, "mechanism_id": identifier})
    return record

