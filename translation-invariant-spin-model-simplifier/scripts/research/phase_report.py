"""Render a single-page phase-map report from registry entries (read-only)."""
import json
from pathlib import Path

from research.contracts import json_safe
from research.registry import load_registry
from research.state import write_json

SCHEMA = "phase-map/v1"


def _phase_label(result):
    static_like = result or {}
    m2 = static_like.get("m2_ordering")
    ordering_q = static_like.get("ordering_q")
    if isinstance(m2, dict) and m2:
        strength = max(abs(float(v)) for v in m2.values()
                       if isinstance(v, (int, float)))
        if strength > 0.2:
            return "ordered" + ("@" + str(ordering_q) if ordering_q else "")
    if isinstance(m2, (int, float)) and abs(float(m2)) > 0.2:
        return "ordered" + ("@" + str(ordering_q) if ordering_q else "")
    return "paramagnetic/disordered"


def render_phase_map_report(registry_path, output_dir, *, model_id=None):
    entries = load_registry(registry_path)
    if model_id:
        entries = [entry for entry in entries if entry.get("model_id") == model_id]
    rows = []
    for entry in entries:
        best = None
        for result in entry.get("results", []):
            if result.get("execution_status") in {"succeeded", "reused"}:
                best = result
        parameters = entry.get("phase_parameters") or {}
        label = _phase_label(best) if best else "no-result"
        rows.append({
            "run_dir": entry.get("run_dir"),
            "model_id": entry.get("model_id"),
            "status": entry.get("status"),
            "claim_level": entry.get("claim_level") or (best or {}).get("claim_level"),
            "scientific_status": (best or {}).get("scientific_status"),
            "parameters": parameters,
            "energy_per_site": (best or {}).get("energy_per_site"),
            "ordering_q": (best or {}).get("ordering_q"),
            "m2_ordering": (best or {}).get("m2_ordering"),
            "phase_label": label,
        })
    rows.sort(key=lambda row: json.dumps(row["parameters"], sort_keys=True))

    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase map report",
        "",
        "Evidence is read from the workspace registry only; no result is recomputed.",
        "Finite-cell rows remain finite-cell claims even when a phase label is assigned.",
        "",
        "| parameters | phase | energy/site | claim_level | scientific | run |",
        "|---|---|---:|---|---|---|",
    ]
    for row in rows:
        params = json.dumps(row["parameters"], sort_keys=True, ensure_ascii=False)
        energy = row["energy_per_site"]
        energy_text = ("%.10g" % energy) if isinstance(energy, (int, float)) else ""
        lines.append("| %s | %s | %s | %s | %s | `%s` |" % (
            params, row["phase_label"], energy_text,
            row.get("claim_level") or "", row.get("scientific_status") or "",
            row["run_dir"]))
    report = out / "phase-map.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {"schema_version": SCHEMA, "registry": str(registry_path),
                "report": str(report), "rows": rows}
    write_json(out / "phase-map.json", manifest)
    return manifest


__all__ = ["render_phase_map_report"]
