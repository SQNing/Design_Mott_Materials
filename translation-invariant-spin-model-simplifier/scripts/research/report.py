"""Render recorded evidence only; importing this module runs no physics."""
import csv
import json
from pathlib import Path

from research.state import collect_steps, read_json, write_json


def _summary(calculation):
    fields = ("energy_per_cell", "energy_per_site", "energy_total", "supercell_shape",
              "spin", "spin_length", "local_dimension", "onsite_term_count", "pair_term_count",
              "stationarity_max_norm", "stationarity", "finite_cell_bound_gap",
              "infinite_lattice_certified", "ground_state_evidence", "convergence", "stability",
              "eigenvalues", "residual_norms", "hilbert_dimension", "sampling", "cutoff_comparison")
    result = {key: calculation[key] for key in fields if key in calculation}
    if "initial_search" in calculation:
        initial = calculation["initial_search"]
        result["initial_search"] = {key: initial[key] for key in
            ("energy_per_cell", "stationarity_max_norm", "finite_cell_bound_gap") if key in initial}
    if "recovery" in calculation:
        recovery = calculation["recovery"]
        result["recovery"] = {key: value for key,value in recovery.items() if key != "seed"}
        if "seed" in recovery:
            result["recovery"]["seed"] = {key:value for key,value in recovery["seed"].items() if key != "spins"}
    return result


def render_research_report(run_dir, output_dir):
    root, output = Path(run_dir).resolve(), Path(output_dir).resolve()
    state = read_json(root / "state.json")
    model = state["model"]
    steps = collect_steps(root, state)
    output.mkdir(parents=True, exist_ok=True)
    fence = chr(96) * 3
    lines = ["# Research report", "", state["request"]["question"], "",
             "- Answer status: " + state["answer_status"],
             "- Model status: " + model["status"],
             "- Model identity: " + model["model_id"],
             "- Full source term count: " + str(model["source_term_count"]),
             "- Solver term count: " + str(model.get("term_count", "unavailable")),
             "- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.",
             "- Default claim scope: finite calculations and the explicitly stated approximations.", "",
             "## Model and conventions", "",
             "[Original source](%s)" % (Path(model["directory"]) / "source.json"),
             "[Model interpretation](%s)" % (Path(model["directory"]) / "interpretation.json"), ""]
    readable = Path(model["directory"]) / "readable.json"
    if readable.exists():
        lines.extend(["[Faithful term representation](%s)" % readable, "",
                      "All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.", ""])
        lines.extend(["Local spaces: " + json.dumps(model.get("local_spaces", {})), "",
                      "Units: " + json.dumps(model.get("units", {})), "",
                      "| Full-model term | Readable content | Sites and translations |",
                      "| --- | --- | --- |"])
        faithful = read_json(readable)
        for category in ("main", "low_weight", "residual"):
            for term in faithful.get(category, []):
                block = term.get("readable_block", {})
                label = block.get("physical_label", block.get("type", term["operator_family"]))
                lines.append("| %s | %s (%s) | %s |" % (
                    term["term_ref"], label, category, json.dumps(term["cluster"])))
        lines.append("")
    if model.get("questions"):
        lines.extend(["## Unresolved physical input", "", fence + "json",
                      json.dumps(model["questions"], indent=2, ensure_ascii=False), fence, ""])
    if state.get("reductions"):
        lines.extend(["## Proposed physical reductions", ""])
        for entry in state["reductions"].values():
            candidate = read_json(entry["record"])
            lines.extend(["### " + candidate["candidate_id"], "",
                "- Transformation: " + candidate["transformation"]["kind"],
                "- Preparation: " + candidate["status"],
                "- Parent is current: " + str(candidate["parent_model_id"] == model["model_id"]),
                "- Complexity: " + json.dumps(candidate["complexity"]),
                "- A prepared candidate is not yet a validated approximation.",
                "[Candidate and operator mapping](%s)" % entry["record"], ""])
            for limitation in candidate["limitations"]:
                lines.append("- Limitation: " + limitation)
            lines.append("")
    if state.get("mechanisms"):
        lines.extend(["## Mechanism studies", ""])
        for entry in state["mechanisms"].values():
            plan = read_json(entry["record"])
            lines.extend(["### " + plan["mechanism_id"], "", plan["question"], "",
                "- Preparation: " + plan["status"],
                "- Parent is current: " + str(plan["parent_model_id"] == model["model_id"]),
                "- Full-model control: " + plan["baseline_point_id"],
                "[Intervention plan and complete models](%s)" % entry["record"], ""])
            for group in plan["groups"]:
                lines.append("- " + group["group_id"] + ": " + group["description"] +
                             " Terms: " + ", ".join(group["term_refs"]))
            lines.extend(["", "| Point | Coupling multipliers | Model status |",
                          "| --- | --- | --- |"])
            for point in plan["points"]:
                lines.append("| %s | %s | %s |" % (point["point_id"], json.dumps(point["factors"]),
                                                  point["model"]["status"]))
            lines.append("")
    artifacts = []
    for step in steps:
        result = step["result"] or {}
        action_id = step["action_id"]
        evidence_path = root / "steps" / action_id / "result.json"
        lines.extend(["## " + action_id, "", "- Decision: " + step["action"]["reason"],
                      "- Execution: " + step["execution"]["status"],
                      "- Scientific usability: " + result.get("scientific_status", "pending"),
                      "- Result model: " + result.get("model_id", "pending"),
                      "- Task: " + str(result.get("task", step["action"].get("task"))), ""])
        accounting = step["execution"]["time_accounting"]
        lines.extend(["- Charged compute seconds: " + str(accounting["seconds"]),
                      "- Time accounting: " + accounting["kind"] +
                      (" (uncertain duration)" if accounting["uncertain"] else ""), ""])
        if result:
            lines.extend(["[Recorded evidence](%s)" % evidence_path, ""])
            if result.get("reference_result"):
                lines.extend(["Reference reused from: " + result["reference_result"] + ".", ""])
            if result.get("reused_from"):
                lines.extend(["Entire calculation reused from: " + result["reused_from"] + ".", ""])
            if result.get("blocker"):
                lines.extend(["Blocker: " + result["blocker"], ""])
            calculation = result.get("calculation", {})
            if result.get("mechanism_id"):
                lines.extend(["- Mechanism study: " + result["mechanism_id"],
                    "- New solver calls: " + str(result["solver_runs"]), "",
                    "| Hypothesis | Verdict | Reason |", "| --- | --- | --- |"])
                for hypothesis in result["hypotheses"]:
                    lines.append("| %s | %s | %s |" % (hypothesis["hypothesis_id"],
                        hypothesis["status"], hypothesis["reason"].replace("|", "/")))
                for hypothesis in result["hypotheses"]:
                    lines.extend(["", "### " + hypothesis["hypothesis_id"], "",
                        "Claim: " + hypothesis["statement"], "",
                        hypothesis.get("explanation", hypothesis["reason"]), "",
                        "Excluded confounded points: " + ", ".join(hypothesis["excluded_confounded_points"]), ""])
                    for source in hypothesis["evidence"]:
                        recorded = source.get("evidence", {})
                        if recorded.get("path"):
                            lines.append("- [%s, factor %s](%s): value %s; selector %s" % (
                                source["point_id"], source["factor"], recorded["path"],
                                source.get("value"), json.dumps(recorded.get("selector", {}))))
                lines.extend(["", "| Observable | Point | Value | Scientific usability |",
                              "| --- | --- | --- | --- |"])
                for value in result["observations"]:
                    lines.append("| %s | %s | %s | %s |" % (value["observable_id"], value["point_id"],
                        value["value"], value["scientific_status"]))
                lines.extend(["", "Energy response (per primitive cell):", "",
                    "| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |",
                    "| --- | --- | --- | --- | --- |"])
                for response in result["energy_responses"]:
                    lines.append("| %s / %s | %s | %s | %s | %s |" % (
                        response["case_id"], response["point_id"], response.get("direct_energy_change"),
                        response.get("relaxation_energy_change"), response.get("total_energy_change"),
                        response["scientific_status"]))
                lines.extend(["", "Tested scope:", "", fence + "json",
                    json.dumps(result["validated_scope"], indent=2, ensure_ascii=False), fence, ""])
            if result.get("validation_status"):
                lines.extend(["- Simplification verdict: " + result["validation_status"],
                    "- Candidate: " + result["candidate_id"],
                    "- New solver calls: " + str(result["solver_runs"]), "",
                    "| Experiment | Observable | Error | Tolerance | Verdict | Reason |",
                    "| --- | --- | --- | --- | --- | --- |"])
                for metric in result["metrics"]:
                    lines.append("| %s | %s | %s | %s | %s | %s |" % (
                        metric["case_id"], metric["name"], metric["value"], metric["tolerance"],
                        metric["outcome"], metric.get("reason", "").replace("|", "/")))
                lines.extend(["", "Tested scope:", "", fence + "json",
                    json.dumps(result["validated_scope"], indent=2, ensure_ascii=False), fence, ""])
                for item in result["evidence"]:
                    lines.append("- [%s / %s](%s), reused: %s" % (
                        item["case_id"], item["role"], item["path"], item["reused"]))
                lines.append("")
            lines.extend([fence + "json", json.dumps(_summary(calculation), indent=2, ensure_ascii=False), fence, ""])
            for diagnostic in result.get("diagnostics", []):
                lines.append("- Diagnostic: " + json.dumps(diagnostic, ensure_ascii=False))
            lines.append("")
            for scope in result.get("scientific_scope", []):
                lines.append("- Scope/limitation: " + scope)
            lines.append("")
            if calculation.get("dispersion"):
                csv_path = output / (action_id + "-spectrum.csv")
                rows = calculation["dispersion"]
                with csv_path.open("w", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["q0", "q1", "q2"] + ["mode_%s" % n for n in range(max(len(r["bands"]) for r in rows))])
                    for row in rows:
                        writer.writerow(row["q"] + row["bands"])
                artifacts.append(str(csv_path))
                lines.extend(["[Spectrum samples, primitive reciprocal coordinates](%s)" % csv_path, ""])
            if calculation.get("grid"):
                grid_path = output / (action_id + "-thermodynamics.json")
                write_json(grid_path, calculation["grid"])
                artifacts.append(str(grid_path))
                lines.extend(["[Finite-temperature samples and errors](%s)" % grid_path, ""])
    lines.extend(["## Agent assessment", ""])
    if not state["assessments"]:
        lines.append("No explicit evidence-based assessment recorded. Successful execution does not complete the research question.")
    for assessment in state["assessments"]:
        lines.extend([assessment["answer_status"] + ": " + assessment["conclusion"], "",
                      "Claim level: " + assessment.get("claim_level", "within_recorded_scope"), "",
                      "Scope: " + str(assessment.get("scope", "unresolved")), "",
                      "Limitations: " + str(assessment["limitations"]), "",
                      "Evidence: " + json.dumps(assessment.get("evidence", [])), ""])
    lines.extend(["", "## Next decisions", "",
                  "Suggested actions are advisory; the host agent must choose settings and justify further computation.", ""])
    for step in steps:
        for suggestion in (step["result"] or {}).get("suggested_actions", []):
            lines.append("- " + suggestion["reason"])
    report = output / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {"schema_version": "research-report/v1", "report": str(report),
                "run_dir": str(root), "model_id": model["model_id"],
                "answer_status": state["answer_status"], "artifacts": artifacts,
                "results": [s["action_id"] for s in steps], "calculations_started": 0}
    write_json(output / "manifest.json", manifest)
    return manifest
