#!/usr/bin/env python3
import argparse
import json
import shlex
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classical.certified_glt.certify_cpn_glt import certify_cpn_generalized_lt
from classical.certified_glt.progress import ProgressReporter

DEFAULT_RUN_CONFIG = {
    "box_budget": 32,
    "tolerance": 1.0e-3,
    "shell_tolerance": 5.0e-2,
    "supercell_cutoff": 4,
    "weight_bound": 1.0,
    "seed": 0,
    "starts": 1,
}


def _load_json_payload(payload):
    if isinstance(payload, dict):
        return payload
    if payload is None:
        return json.load(sys.stdin)
    return json.loads(Path(payload).read_text(encoding="utf-8"))


def _select_rerun_action(suggestions, candidate_rank):
    candidate_rank = int(candidate_rank)
    if candidate_rank < 1:
        raise ValueError("candidate_rank must be >= 1")
    primary_action = suggestions.get("primary_action")
    candidate_actions = list(suggestions.get("candidate_actions", []))
    if candidate_rank == 1 and isinstance(primary_action, dict) and primary_action:
        return dict(primary_action)
    for action in candidate_actions:
        if int(action.get("priority_rank", -1)) == candidate_rank:
            return dict(action)
    if candidate_rank <= len(candidate_actions):
        return dict(candidate_actions[candidate_rank - 1])
    raise ValueError(f"candidate_rank={candidate_rank} is unavailable in rerun suggestions")


def _supported_rerun_config(action):
    suggested = dict(action.get("suggested_run_config", {}))
    supported = {}
    for key in ("box_budget", "tolerance", "shell_tolerance", "supercell_cutoff", "weight_bound"):
        if key in suggested:
            supported[key] = suggested[key]
    return supported


def resolve_driver_run_config(
    *,
    box_budget=None,
    tolerance=None,
    shell_tolerance=None,
    supercell_cutoff=None,
    weight_bound=None,
    seed=None,
    starts=None,
    rerun_suggestions=None,
    candidate_rank=1,
):
    config = dict(DEFAULT_RUN_CONFIG)
    if rerun_suggestions:
        suggestions = _load_json_payload(rerun_suggestions)
        config.update(_supported_rerun_config(_select_rerun_action(suggestions, candidate_rank)))
    overrides = {
        "box_budget": box_budget,
        "tolerance": tolerance,
        "shell_tolerance": shell_tolerance,
        "supercell_cutoff": supercell_cutoff,
        "weight_bound": weight_bound,
        "seed": seed,
        "starts": starts,
    }
    for key, value in overrides.items():
        if value is not None:
            config[key] = value
    return config


def _render_reproduce_script(applied_run_config):
    driver_path = Path(__file__).resolve()
    quoted_python = shlex.quote(sys.executable)
    quoted_driver = shlex.quote(str(driver_path))
    script_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'DEFAULT_OUTPUT_DIR="$SCRIPT_DIR/reproduced-run"',
        'OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"',
        'CANDIDATE_RANK=""',
        "",
        "# Usage:",
        "#   bash ./reproduce.sh [output_dir]",
        "#   bash ./reproduce.sh [output_dir] --candidate-rank N",
        "",
        "while [[ $# -gt 0 ]]; do",
        '  case "$1" in',
        "    --candidate-rank)",
        '      if [[ $# -lt 2 ]]; then',
        '        echo "Missing value for --candidate-rank" >&2',
        "        exit 2",
        "      fi",
        '      CANDIDATE_RANK="$2"',
        "      shift 2",
        "      ;;",
        "    *)",
        '      if [[ "$OUTPUT_DIR" != "$DEFAULT_OUTPUT_DIR" ]]; then',
        '        echo "Unexpected extra argument: $1" >&2',
        "        exit 2",
        "      fi",
        '      OUTPUT_DIR="$1"',
        "      shift",
        "      ;;",
        "  esac",
        "done",
        "",
        f'CMD=({quoted_python} {quoted_driver} "$SCRIPT_DIR/input_model.json" --output-dir "$OUTPUT_DIR")',
        'if [[ -n "$CANDIDATE_RANK" ]]; then',
        '  CMD+=(--rerun-suggestions "$SCRIPT_DIR/rerun_suggestions.json" --candidate-rank "$CANDIDATE_RANK")',
        "else",
        f"  CMD+=(--box-budget {int(applied_run_config['box_budget'])})",
        f"  CMD+=(--tolerance {applied_run_config['tolerance']})",
        f"  CMD+=(--shell-tolerance {applied_run_config['shell_tolerance']})",
        f"  CMD+=(--supercell-cutoff {int(applied_run_config['supercell_cutoff'])})",
        f"  CMD+=(--weight-bound {applied_run_config['weight_bound']})",
        f"  CMD+=(--seed {int(applied_run_config['seed'])})",
        f"  CMD+=(--starts {int(applied_run_config['starts'])})",
        "fi",
        "",
        '"${CMD[@]}"',
        "",
    ]
    return "\n".join(script_lines)


def _build_reproduce_command_payload(applied_run_config):
    driver_path = str(Path(__file__).resolve())
    return {
        "format": "certified_glt_reproduce_commands",
        "bundle_path_mode": "bundle_relative",
        "driver_path": driver_path,
        "commands": {
            "reproduce_current_run": {
                "description": "Reproduce the current certified GLT run using the bundled input model and applied run config.",
                "argv": [
                    sys.executable,
                    driver_path,
                    "input_model.json",
                    "--box-budget",
                    str(int(applied_run_config["box_budget"])),
                    "--tolerance",
                    str(applied_run_config["tolerance"]),
                    "--shell-tolerance",
                    str(applied_run_config["shell_tolerance"]),
                    "--supercell-cutoff",
                    str(int(applied_run_config["supercell_cutoff"])),
                    "--weight-bound",
                    str(applied_run_config["weight_bound"]),
                    "--seed",
                    str(int(applied_run_config["seed"])),
                    "--starts",
                    str(int(applied_run_config["starts"])),
                    "--output-dir",
                    "<output_dir>",
                ],
            },
            "rerun_from_suggestions_template": {
                "description": "Launch a rerun using the bundled rerun suggestions and a selected candidate rank.",
                "argv": [
                    sys.executable,
                    driver_path,
                    "input_model.json",
                    "--rerun-suggestions",
                    "rerun_suggestions.json",
                    "--candidate-rank",
                    "<candidate_rank>",
                    "--output-dir",
                    "<output_dir>",
                ],
            },
        },
    }


def _build_next_action_summary(result):
    next_best_action = dict(result.get("next_best_action", {}))
    candidate_actions = list(result.get("next_best_actions", []))
    return {
        "format": "certified_glt_next_action_summary",
        "status": str(result.get("relaxed_global_bound", {}).get("status", "inconclusive")),
        "blocking_reason": next_best_action.get("blocking_reason"),
        "candidate_action_count": len(candidate_actions),
        "primary_action": next_best_action,
        "candidate_actions": candidate_actions,
    }


def run_certified_glt_driver(
    payload,
    *,
    box_budget=None,
    tolerance=None,
    shell_tolerance=None,
    supercell_cutoff=None,
    weight_bound=None,
    seed=None,
    starts=None,
    rerun_suggestions=None,
    candidate_rank=1,
    reporter=None,
):
    model = _load_json_payload(payload)
    reporter = reporter or ProgressReporter(stream=sys.stderr)
    config = resolve_driver_run_config(
        box_budget=box_budget,
        tolerance=tolerance,
        shell_tolerance=shell_tolerance,
        supercell_cutoff=supercell_cutoff,
        weight_bound=weight_bound,
        seed=seed,
        starts=starts,
        rerun_suggestions=rerun_suggestions,
        candidate_rank=candidate_rank,
    )
    return certify_cpn_generalized_lt(
        model,
        reporter=reporter,
        box_budget=config["box_budget"],
        tolerance=config["tolerance"],
        shell_tolerance=config["shell_tolerance"],
        supercell_cutoff=config["supercell_cutoff"],
        weight_bound=config["weight_bound"],
        seed=config["seed"],
        starts=config["starts"],
    )


def write_certified_glt_bundle(payload, result, output_dir, *, applied_run_config=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    serialized_input = _load_json_payload(payload)
    serialized_run_config = dict(applied_run_config or {})
    (output_dir / "input_model.json").write_text(
        json.dumps(serialized_input, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "certified_glt_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "next_best_actions.json").write_text(
        json.dumps(
            {"next_best_actions": result.get("next_best_actions", [])},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    rerun_suggestions = {
        "primary_action": dict(result.get("next_best_action", {})),
        "candidate_actions": list(result.get("next_best_actions", [])),
    }
    (output_dir / "rerun_suggestions.json").write_text(
        json.dumps(rerun_suggestions, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "applied_run_config.json").write_text(
        json.dumps(serialized_run_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "reproduce_command.json").write_text(
        json.dumps(_build_reproduce_command_payload(serialized_run_config), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "next_action_summary.json").write_text(
        json.dumps(_build_next_action_summary(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    reproduce_script_path = output_dir / "reproduce.sh"
    reproduce_script_path.write_text(
        _render_reproduce_script(serialized_run_config),
        encoding="utf-8",
    )
    reproduce_script_path.chmod(0o755)
    summary = {
        "status": str(result.get("relaxed_global_bound", {}).get("status", "inconclusive")),
        "relaxed_global_bound": dict(result.get("relaxed_global_bound", {})),
        "lowest_shell_status": str(result.get("lowest_shell_certificate", {}).get("status", "inconclusive")),
        "lift_status": str(result.get("commensurate_lift_certificate", {}).get("status", "inconclusive")),
        "projector_status": str(result.get("projector_exactness_certificate", {}).get("status", "inconclusive")),
        "search_summary": dict(result.get("search_summary", {})),
        "next_best_action": dict(result.get("next_best_action", {})),
        "applied_run_config": serialized_run_config,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    readme_lines = [
        "Certified GLT Summary",
        "",
        f"Relaxed bound status: {summary['relaxed_global_bound'].get('status')}",
        f"Shell certificate status: {summary['lowest_shell_status']}",
        f"Lift certificate status: {summary['lift_status']}",
        f"Projector certificate status: {summary['projector_status']}",
        "",
        "Applied run config:",
        f"  box_budget: {summary['applied_run_config'].get('box_budget')}",
        f"  tolerance: {summary['applied_run_config'].get('tolerance')}",
        f"  shell_tolerance: {summary['applied_run_config'].get('shell_tolerance')}",
        f"  supercell_cutoff: {summary['applied_run_config'].get('supercell_cutoff')}",
        f"  weight_bound: {summary['applied_run_config'].get('weight_bound')}",
        f"  seed: {summary['applied_run_config'].get('seed')}",
        f"  starts: {summary['applied_run_config'].get('starts')}",
        "",
        "Reproduce this run:",
        "  bash ./reproduce.sh [output_dir]",
        "  bash ./reproduce.sh [output_dir] --candidate-rank N",
        "",
        "Next best action:",
        f"  kind: {summary['next_best_action'].get('kind')}",
        f"  blocking_reason: {summary['next_best_action'].get('blocking_reason')}",
        f"  target_axis: {summary['next_best_action'].get('target_axis')}",
    ]
    (output_dir / "README.txt").write_text(
        "\n".join(readme_lines) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "status": "ok",
        "files": {
            "input_model": "input_model.json",
            "result": "certified_glt_result.json",
            "next_best_actions": "next_best_actions.json",
            "rerun_suggestions": "rerun_suggestions.json",
            "applied_run_config": "applied_run_config.json",
            "reproduce_command": "reproduce_command.json",
            "next_action_summary": "next_action_summary.json",
            "reproduce_script": "reproduce.sh",
            "summary": "summary.json",
            "readme": "README.txt",
        },
    }
    (output_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--box-budget", type=int)
    parser.add_argument("--tolerance", type=float)
    parser.add_argument("--shell-tolerance", type=float)
    parser.add_argument("--supercell-cutoff", type=int)
    parser.add_argument("--weight-bound", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--starts", type=int)
    parser.add_argument("--rerun-suggestions")
    parser.add_argument("--candidate-rank", type=int, default=1)
    parser.add_argument("--output")
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    applied_run_config = resolve_driver_run_config(
        box_budget=args.box_budget,
        tolerance=args.tolerance,
        shell_tolerance=args.shell_tolerance,
        supercell_cutoff=args.supercell_cutoff,
        weight_bound=args.weight_bound,
        seed=args.seed,
        starts=args.starts,
        rerun_suggestions=args.rerun_suggestions,
        candidate_rank=args.candidate_rank,
    )
    result = run_certified_glt_driver(
        args.input,
        box_budget=applied_run_config["box_budget"],
        tolerance=applied_run_config["tolerance"],
        shell_tolerance=applied_run_config["shell_tolerance"],
        supercell_cutoff=applied_run_config["supercell_cutoff"],
        weight_bound=applied_run_config["weight_bound"],
        seed=applied_run_config["seed"],
        starts=applied_run_config["starts"],
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if args.output_dir:
        write_certified_glt_bundle(
            args.input,
            result,
            args.output_dir,
            applied_run_config=applied_run_config,
        )
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
