#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions
else:
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions


SCRIPT_DIR = Path(__file__).resolve().parent
SUNNY_GSWT_SCRIPT = SCRIPT_DIR / "run_sunny_sun_gswt.jl"


def _resolve_julia_cmd(julia_cmd=None):
    if julia_cmd not in {None, ""}:
        return str(julia_cmd)
    override = os.environ.get("DESIGN_MOTT_JULIA_CMD")
    if override:
        return override
    return "julia"


def _error(code, message, *, payload_kind=None, backend=None):
    return {
        "status": "error",
        "backend": {"name": backend or "Sunny.jl", "mode": "SUN"},
        "payload_kind": payload_kind,
        "error": {"code": code, "message": message},
    }


def _preflight_payload_error(gswt_payload):
    try:
        resolve_pseudospin_orbital_conventions(gswt_payload)
    except ValueError as exc:
        return _error(
            "invalid-gswt-convention",
            str(exc),
            payload_kind=gswt_payload.get("payload_kind"),
            backend=gswt_payload.get("backend", "Sunny.jl"),
        )

    classical_reference = gswt_payload.get("classical_reference")
    if isinstance(classical_reference, dict):
        manifold = classical_reference.get("manifold")
        if manifold != "CP^(N-1)":
            return _error(
                "invalid-gswt-payload",
                f"Sunny pseudospin-orbital SUN-GSWT payload expects a CP^(N-1) classical reference, got {manifold!r}",
                payload_kind=gswt_payload.get("payload_kind"),
                backend=gswt_payload.get("backend", "Sunny.jl"),
            )
        frame_construction = classical_reference.get("frame_construction")
        if frame_construction is not None and frame_construction != "first-column-is-reference-ray":
            return _error(
                "invalid-gswt-convention",
                f"classical_reference.frame_construction must be 'first-column-is-reference-ray', got {frame_construction!r}",
                payload_kind=gswt_payload.get("payload_kind"),
                backend=gswt_payload.get("backend", "Sunny.jl"),
            )
    else:
        return _error(
            "invalid-gswt-payload",
            "Sunny pseudospin-orbital SUN-GSWT payload must include classical_reference.manifold = 'CP^(N-1)'",
            payload_kind=gswt_payload.get("payload_kind"),
            backend=gswt_payload.get("backend", "Sunny.jl"),
        )

    ordering = gswt_payload.get("ordering")
    if not isinstance(ordering, dict):
        return None
    compatibility = ordering.get("compatibility_with_supercell")
    if not isinstance(compatibility, dict):
        return None
    if ordering.get("ansatz") != "single-q-unitary-ray":
        return None
    if compatibility.get("kind") != "incommensurate":
        return None

    q_vector = ordering.get("q_vector")
    supercell_shape = ordering.get("supercell_shape")
    axis_products = compatibility.get("axis_products", [])
    mismatch_summary = ", ".join(
        f"axis {item.get('axis')}: q*L={item.get('phase_winding')} (nearest integer {item.get('nearest_integer')}, mismatch {item.get('mismatch')})"
        for item in axis_products
    )
    if not mismatch_summary:
        mismatch_summary = "phase winding is not integer on at least one supercell axis"
    message = (
        "Sunny.jl SUN SpinWaveTheory currently requires a periodic magnetic supercell, "
        "but the supplied single-q classical state is incommensurate with that supercell. "
        f"q_vector={q_vector}, supercell_shape={supercell_shape}. {mismatch_summary}. "
        "The current backend cannot evaluate incommensurate single-q SUN-GSWT states through a finite periodic supercell."
    )
    result = _error(
        "unsupported-incommensurate-single-q-sun-gswt",
        message,
        payload_kind=gswt_payload.get("payload_kind"),
        backend=gswt_payload.get("backend", "Sunny.jl"),
    )
    result["ordering"] = ordering
    return result


def _extract_payload(payload):
    if isinstance(payload, dict) and "payload_kind" in payload:
        return payload
    if isinstance(payload, dict):
        embedded = payload.get("gswt_payload")
        if isinstance(embedded, dict):
            return embedded
    return None


def _parse_q_vector_from_message(message):
    if not message:
        return None
    match = re.search(r"q\s*=\s*\[([^\]]+)\]", str(message))
    if match is None:
        return None
    try:
        return [float(value.strip()) for value in match.group(1).split(",")]
    except ValueError:
        return None


def _nearest_q_path_match(target_q, q_path):
    if not isinstance(q_path, list) or not q_path:
        return None
    best = None
    for index, candidate in enumerate(q_path):
        if not isinstance(candidate, list):
            continue
        padded_target = list(target_q) + [0.0] * max(0, len(candidate) - len(target_q))
        padded_candidate = list(candidate) + [0.0] * max(0, len(target_q) - len(candidate))
        distance = math.sqrt(
            sum((float(padded_target[axis]) - float(padded_candidate[axis])) ** 2 for axis in range(len(padded_candidate)))
        )
        if best is None or distance < best["distance"]:
            best = {
                "index": int(index),
                "q_vector": [float(value) for value in candidate],
                "distance": float(distance),
            }
    return best


def _high_symmetry_label_for_index(path_metadata, q_index):
    if not isinstance(path_metadata, dict):
        return None
    labels = path_metadata.get("labels", [])
    node_indices = path_metadata.get("node_indices", [])
    for label, node_index in zip(labels, node_indices):
        if int(node_index) == int(q_index):
            return str(label)
    return None


def _path_region_for_index(path_metadata, q_index):
    if not isinstance(path_metadata, dict):
        return None
    labels = [str(label) for label in path_metadata.get("labels", [])]
    node_indices = [int(index) for index in path_metadata.get("node_indices", [])]
    if not labels or not node_indices:
        return None

    for label, node_index in zip(labels, node_indices):
        if int(node_index) == int(q_index):
            return {
                "kind": "high-symmetry-node",
                "label": str(label),
                "node_index": int(node_index),
            }

    for segment_index in range(max(0, len(node_indices) - 1)):
        start_index = int(node_indices[segment_index])
        end_index = int(node_indices[segment_index + 1])
        if start_index <= int(q_index) <= end_index:
            start_label = str(labels[segment_index])
            end_label = str(labels[segment_index + 1])
            fraction = 0.0
            if end_index > start_index:
                fraction = float(int(q_index) - start_index) / float(end_index - start_index)
            return {
                "kind": "path-segment-sample",
                "segment_index": int(segment_index),
                "start_label": start_label,
                "end_label": end_label,
                "segment_label": f"{start_label}-{end_label}",
                "start_index": start_index,
                "end_index": end_index,
                "segment_fraction": float(fraction),
            }
    return None


def _dispersion_diagnostics(dispersion, soft_mode_tolerance=-1e-9):
    omega_entries = []
    for index, point in enumerate(dispersion):
        if not isinstance(point, dict):
            continue
        if point.get("omega") is not None:
            omega = float(point.get("omega"))
        else:
            bands = point.get("bands", [])
            if not bands:
                continue
            omega = float(min(float(value) for value in bands))
        omega_entries.append(
            {
                "index": int(index),
                "q_vector": [float(value) for value in point.get("q", [])],
                "omega": omega,
            }
        )

    if not omega_entries:
        return None

    omega_min_entry = min(omega_entries, key=lambda item: item["omega"])
    soft_modes = [item for item in omega_entries if item["omega"] < float(soft_mode_tolerance)]
    return {
        "omega_min": float(omega_min_entry["omega"]),
        "omega_max": float(max(item["omega"] for item in omega_entries)),
        "omega_min_q_vector": list(omega_min_entry["q_vector"]),
        "omega_min_index": int(omega_min_entry["index"]),
        "soft_mode_threshold": float(soft_mode_tolerance),
        "soft_mode_count": int(len(soft_modes)),
        "soft_mode_q_points": [list(item["q_vector"]) for item in soft_modes],
    }


def _enrich_gswt_result(result, gswt_payload):
    if not isinstance(result, dict):
        return result

    diagnostics = {}
    dispersion = result.get("dispersion", [])
    dispersion_summary = _dispersion_diagnostics(dispersion)
    if dispersion_summary is not None:
        diagnostics["dispersion"] = dispersion_summary

    error = result.get("error", {})
    if isinstance(error, dict):
        q_vector = _parse_q_vector_from_message(error.get("message", ""))
        if q_vector is not None:
            instability = {
                "kind": "wavevector-instability",
                "q_vector": [float(value) for value in q_vector],
            }
            nearest = _nearest_q_path_match(q_vector, gswt_payload.get("q_path", []))
            if nearest is not None:
                instability["nearest_q_path_index"] = int(nearest["index"])
                instability["nearest_q_path_vector"] = list(nearest["q_vector"])
                instability["nearest_q_path_distance"] = float(nearest["distance"])
                path_region = _path_region_for_index(gswt_payload.get("path", {}), nearest["index"])
                if path_region is not None:
                    instability["nearest_q_path_kind"] = path_region["kind"]
                    if path_region["kind"] == "high-symmetry-node":
                        instability["nearest_high_symmetry_label"] = path_region["label"]
                    elif path_region["kind"] == "path-segment-sample":
                        instability["nearest_path_segment_label"] = path_region["segment_label"]
                        instability["nearest_path_segment_index"] = int(path_region["segment_index"])
                        instability["nearest_path_segment_start_label"] = path_region["start_label"]
                        instability["nearest_path_segment_end_label"] = path_region["end_label"]
                        instability["nearest_path_segment_start_index"] = int(path_region["start_index"])
                        instability["nearest_path_segment_end_index"] = int(path_region["end_index"])
                        instability["nearest_path_segment_fraction"] = float(path_region["segment_fraction"])
                else:
                    label = _high_symmetry_label_for_index(gswt_payload.get("path", {}), nearest["index"])
                    if label is not None:
                        instability["nearest_high_symmetry_label"] = label
            diagnostics["instability"] = instability

    if diagnostics:
        result["diagnostics"] = diagnostics
    return result


def run_sun_gswt(payload, julia_cmd=None):
    gswt_payload = _extract_payload(payload)
    if gswt_payload is None:
        return _error("missing-gswt-payload", "GSWT stage requires a `gswt_payload` dictionary")

    preflight_error = _preflight_payload_error(gswt_payload)
    if preflight_error is not None:
        return preflight_error

    payload_kind = gswt_payload.get("payload_kind")
    backend = gswt_payload.get("backend", "Sunny.jl")
    if payload_kind != "sun_gswt_prototype":
        return _error(
            "unsupported-gswt-payload",
            f"Unsupported GSWT payload kind: {payload_kind}",
            payload_kind=payload_kind,
            backend=backend,
        )

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(gswt_payload, handle, indent=2, sort_keys=True)

    try:
        resolved_julia_cmd = _resolve_julia_cmd(julia_cmd)
        completed = subprocess.run(
            [resolved_julia_cmd, str(SUNNY_GSWT_SCRIPT), str(payload_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return _error(
            "missing-julia-command",
            str(exc),
            payload_kind=payload_kind,
            backend=backend,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return _error(
            "backend-process-failed",
            stderr or str(exc),
            payload_kind=payload_kind,
            backend=backend,
        )
    finally:
        payload_path.unlink(missing_ok=True)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return _error(
            "invalid-backend-json",
            str(exc),
            payload_kind=payload_kind,
            backend=backend,
        )

    if isinstance(result, dict):
        if "path" not in result:
            result["path"] = gswt_payload.get("path", {})
        if "classical_reference" not in result:
            result["classical_reference"] = gswt_payload.get("classical_reference", {})
        if "ordering" not in result and isinstance(gswt_payload.get("ordering"), dict):
            result["ordering"] = gswt_payload.get("ordering", {})
        if "supercell_shape" not in result and gswt_payload.get("supercell_shape") is not None:
            result["supercell_shape"] = gswt_payload.get("supercell_shape")
    return _enrich_gswt_result(result, gswt_payload)


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--julia-cmd")
    args = parser.parse_args()
    payload = _load_payload(args.input)
    print(json.dumps(run_sun_gswt(payload, julia_cmd=args.julia_cmd), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
