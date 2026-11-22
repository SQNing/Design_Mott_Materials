"""Land existing input routes without changing the physical Hamiltonian."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json

from research.contracts import digest, json_safe, restore_complex
from research.state import write_json


def merge_patch(original, patch):
    result = deepcopy(original)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_patch(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_source(request):
    if "model" in request:
        return deepcopy(request["model"]), {"kind": "inline"}
    source = request.get("source", {})
    if source.get("path"):
        p = Path(source["path"]).expanduser().resolve()
        raw = p.read_text(encoding="utf-8")
        if source.get("kind") in {"text", "document", "latex"}:
            return {"text": raw, "source_path": str(p)}, {"kind": source["kind"], "path": str(p)}
        return json.loads(raw), {"kind": source.get("kind", "model_file"), "path": str(p)}
    if source.get("text"):
        return {"text": source["text"]}, {"kind": source.get("kind", "text")}
    raise ValueError("supply model or source.path/source.text")


def source_term_count(source):
    if isinstance(source.get("terms"), list):
        return len(source["terms"])
    attachments = source.get("term_attachments", {})
    return sum(len(attachments.get(key, [])) for key in ("site_terms", "bond_terms", "higher_body_terms"))


def prepare_model(source, request, root, version):
    directory = Path(root) / "models" / ("model-%04d" % version)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "source.json", source, exclusive=True)
    record = {"version": version, "directory": str(directory), "status": "ready",
              "source_term_count": source_term_count(source), "questions": [],
              "fidelity": {"assessment": "not_assessed", "reconstruction_error": None}}
    model = deepcopy(source)
    if source.get("kind") == "dipolar_geometry":
        record.update(model_id=digest(source), term_count=0, term_families={},
                      site_count=len(source.get("moments", [])),
                      scope="independent periodic dipole geometry; no short-range model merge")
        for field in ("lattice_vectors", "fractional_positions", "moments"):
            if field not in source:
                record["questions"].append({"field": field, "question": "Supply explicit " + field})
        if record["questions"]:
            record["status"] = "needs_input"
        write_json(directory / "solver_model.json", source, exclusive=True)
        write_json(directory / "interpretation.json", record, exclusive=True)
        return record
    try:
        if "text" in model:
            from input.normalize_input import normalize_freeform_text
            selection = request.get("normalization", {})
            allowed = ("selected_classical_bond_label", "selected_model_candidate",
                       "selected_local_bond_bond_label", "selected_coordinate_convention")
            model = normalize_freeform_text(model["text"], source_path=model.get("source_path"),
                                             **{k: selection[k] for k in allowed if k in selection})
            if request.get("agent_normalized_document") is not None:
                from cli.normalize_document_with_agent import run_document_normalization_with_agent
                import inspect
                kwargs = {k: v for k, v in request.items()
                          if k in inspect.signature(run_document_normalization_with_agent).parameters}
                kwargs.update({k: selection[k] for k in allowed if k in selection})
                kwargs["agent_normalized_document"] = request["agent_normalized_document"]
                landed = run_document_normalization_with_agent(source["text"], **kwargs)
                model = landed.get("normalized_model", landed)
        elif model.get("schema_version") == "effective-model/v1":
            # Inter-chain contract (stage F1): canonical-hamiltonian/v1 superset
            # plus upstream provenance and uncertainty. Until the upstream DFT
            # fields are explicitly aligned, missing provenance is a question,
            # never something to infer.
            missing = [field for field in ("model", "provenance", "uncertainty")
                       if not model.get(field)]
            provenance = model.get("provenance") or {}
            for field in ("dft_code", "functional", "u_j", "projection_window",
                          "wannier_basis", "date"):
                if not provenance.get(field):
                    missing.append("provenance." + field)
            if missing:
                record.update(status="needs_input", questions=[{
                    "field": field,
                    "question": "Supply effective-model/v1 %s; the upstream contract is not aligned." % field,
                } for field in missing])
                write_json(directory / "normalized.json", model, exclusive=True)
                record.setdefault("model_id", digest(source))
                write_json(directory / "interpretation.json", record, exclusive=True)
                return json_safe(record)
            effective_provenance = deepcopy(model["provenance"])
            effective_uncertainty = deepcopy(model["uncertainty"])
            model = deepcopy(model["model"])
            model["effective_model_provenance"] = effective_provenance
            model["effective_model_uncertainty"] = effective_uncertainty
        elif model.get("schema_version") not in {"lattice-term-contract/v1", "canonical-hamiltonian/v1"}:
            from input.normalize_input import normalize_input
            model = normalize_input(model)
        interaction = model.get("interaction", {})
        if interaction.get("status") == "needs_input":
            record.update(status="needs_input", questions=[interaction])
            if model.get("agent_normalization_request"):
                record["agent_normalization_request"] = model["agent_normalization_request"]
        if record["status"] == "ready":
            for field in ("lattice_structure", "local_hilbert", "symmetry"):
                if not model.get(field):
                    record["questions"].append({"field": field,
                        "question": "Supply the model's %s; it cannot be inferred safely." % field})
            if not model.get("symmetry", {}).get("operations"):
                record["questions"].append({"field": "symmetry.operations",
                    "question": "Supply the structural symmetry operations, including identity."})
            if record["questions"]:
                record["status"] = "needs_input"
        if record["status"] == "ready":
            from common.canonical_hamiltonian import compile_canonical_hamiltonian
            from common.hamiltonian_symmetry_gate import run_hamiltonian_symmetry_gate, SymmetryGateRequest
            canonical = (restore_complex(model) if model.get("schema_version") == "canonical-hamiltonian/v1"
                         else compile_canonical_hamiltonian(restore_complex(model)))
            # Preserve basis names and units as interpretation metadata; no basis
            # rotation, rescaling or inferred spin representation is performed.
            for field in ("local_basis_labels", "units", "effective_model_provenance",
                          "effective_model_uncertainty"):
                if field in model:
                    canonical[field] = deepcopy(model[field])
            gate = run_hamiltonian_symmetry_gate(canonical, SymmetryGateRequest(
                repair=bool(request.get("physics_policy", {}).get("symmetry_repair", False))))
            write_json(directory / "canonical.json", canonical, exclusive=True)
            write_json(directory / "gate.json", gate, exclusive=True)
            if gate["status"] != "ok":
                reason = gate.get("completion", {}).get("reason", "")
                record.update(status="unsupported" if "unsupported" in reason else "needs_input", questions=[{
                    "field": "hamiltonian_symmetry", "question": "Resolve the reported Hamiltonian/symmetry mismatch.",
                    "diagnostics": gate}])
            else:
                solver = gate["solver_model"]
                write_json(directory / "solver_model.json", solver, exclusive=True)
                hamiltonian_hash = gate["symmetry_validation_stamp"]["hamiltonian_hash"]
                record.update(model_id=digest({"hamiltonian_hash": hamiltonian_hash,
                                              "units": solver.get("units"),
                                              "local_basis_labels": solver.get("local_basis_labels")}),
                              hamiltonian_hash=hamiltonian_hash,
                              term_count=len(solver.get("terms", [])),
                              term_families=dict(Counter(t["operator_family"] for t in solver.get("terms", []))),
                              site_count=len(solver["lattice_structure"].get("basis_sites", [])),
                              local_spaces=solver.get("local_hilbert", {}).get("classical_spaces", {}),
                              local_basis_labels=solver.get("local_basis_labels", []),
                              units=solver.get("units", {"energy": "input coefficient units; absolute unit unspecified"}),
                              lattice_vectors=solver["lattice_structure"].get("lattice_vectors"),
                              basis_sites=solver["lattice_structure"].get("basis_sites"),
                              symmetry_validation=gate["symmetry_validation"],
                              warnings=gate.get("warnings", []))
                for field in ("effective_model_provenance", "effective_model_uncertainty"):
                    if field in model:
                        record[field] = deepcopy(model[field])
                # A faithful matrix/tensor representation is meaningful even when
                # no specialized human-readable block exists for a local operator.
                from research.readable import faithful_view
                readable = faithful_view(solver)
                if model.get("input_mode") or model.get("mode"):
                    from cli.simplify_text_input import run_simplification_from_normalized_model
                    try:
                        simplified = run_simplification_from_normalized_model(model)
                        readable["existing_simplification"] = simplified
                    except (ValueError, KeyError, TypeError) as exc:
                        readable["readable_block_limitation"] = str(exc)
                write_json(directory / "readable.json", readable, exclusive=True)
    except (ValueError, KeyError, TypeError, NotImplementedError) as exc:
        record.update(status="unsupported", blocker=str(exc))
    write_json(directory / "normalized.json", model, exclusive=True)
    record.setdefault("model_id", digest(source))
    write_json(directory / "interpretation.json", record, exclusive=True)
    return json_safe(record)

