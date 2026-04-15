#!/usr/bin/env python3
import argparse
import json
import shlex
from pathlib import Path


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _discover_bundle_dirs(inputs):
    discovered = []
    seen = set()
    for raw_path in inputs:
        path = Path(raw_path)
        if not path.exists():
            continue
        if path.is_dir() and (path / "next_action_summary.json").exists():
            resolved = str(path.resolve())
            if resolved not in seen:
                discovered.append(path)
                seen.add(resolved)
            continue
        if path.is_dir():
            for child in sorted(item for item in path.iterdir() if item.is_dir()):
                if (child / "next_action_summary.json").exists():
                    resolved = str(child.resolve())
                    if resolved not in seen:
                        discovered.append(child)
                        seen.add(resolved)
    return discovered


def _bundle_record(bundle_dir):
    next_action_summary = _load_json(bundle_dir / "next_action_summary.json")
    summary = _load_json(bundle_dir / "summary.json")
    applied_run_config = _load_json(bundle_dir / "applied_run_config.json")
    primary_action = dict(next_action_summary.get("primary_action", {}))
    suggested_run_config = dict(primary_action.get("suggested_run_config", {}))
    return {
        "bundle_dir": str(bundle_dir.resolve()),
        "status": str(next_action_summary.get("status", summary.get("status", "inconclusive"))),
        "blocking_reason": primary_action.get("blocking_reason", next_action_summary.get("blocking_reason")),
        "candidate_action_count": int(next_action_summary.get("candidate_action_count", 0)),
        "primary_action_kind": primary_action.get("kind"),
        "primary_action_target_axis": primary_action.get("target_axis"),
        "suggested_box_budget": suggested_run_config.get("box_budget"),
        "applied_box_budget": applied_run_config.get("box_budget"),
    }


def _sort_key(record):
    status_priority = 0 if record["status"] != "certified" else 1
    blocking_priority = 0 if record["blocking_reason"] else 1
    suggested_budget = record["suggested_box_budget"]
    budget_priority = -(int(suggested_budget) if suggested_budget is not None else -1)
    return (
        status_priority,
        blocking_priority,
        budget_priority,
        record["bundle_dir"],
    )


def aggregate_bundles(input_paths, *, status=None, blocking_reason=None, top=None):
    bundle_dirs = _discover_bundle_dirs(input_paths)
    records = [_bundle_record(path) for path in bundle_dirs]
    records.sort(key=_sort_key)
    if status is not None:
        records = [record for record in records if record["status"] == status]
    if blocking_reason is not None:
        records = [record for record in records if record["blocking_reason"] == blocking_reason]
    if top is not None:
        records = records[: max(int(top), 0)]
    status_counts = {}
    for record in records:
        status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
    return {
        "format": "certified_glt_bundle_aggregate",
        "bundle_count": len(records),
        "status_counts": status_counts,
        "bundles": records,
    }


def _render_json(payload):
    return json.dumps(payload, indent=2, sort_keys=True)


def _render_table(payload):
    columns = [
        "bundle_dir",
        "status",
        "blocking_reason",
        "candidate_action_count",
        "primary_action_kind",
        "primary_action_target_axis",
        "suggested_box_budget",
        "applied_box_budget",
    ]
    rows = []
    for record in payload["bundles"]:
        rows.append([str(record.get(column, "")) for column in columns])
    widths = [len(column) for column in columns]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    header = " | ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
    separator = "-+-".join("-" * widths[index] for index in range(len(columns)))
    body = [" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows]
    lines = [header, separator] + body
    return "\n".join(lines)


def _render_rerun_shell(payload):
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
    ]
    for index, record in enumerate(payload["bundles"], start=1):
        bundle_dir = record["bundle_dir"]
        bundle_name = Path(bundle_dir).name
        output_dir = f"./aggregated-reruns/{index:02d}-{bundle_name}"
        command = " ".join(
            [
                "bash",
                shlex.quote(str(Path(bundle_dir) / "reproduce.sh")),
                shlex.quote(output_dir),
                "--candidate-rank",
                "1",
            ]
        )
        lines.append(command)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--output")
    parser.add_argument("--format", choices=("json", "table"), default="json")
    parser.add_argument("--top", type=int)
    parser.add_argument("--status")
    parser.add_argument("--blocking-reason")
    parser.add_argument("--emit-rerun-shell", action="store_true")
    args = parser.parse_args()
    payload = aggregate_bundles(
        args.paths,
        status=args.status,
        blocking_reason=args.blocking_reason,
        top=args.top,
    )
    if args.emit_rerun_shell:
        rendered = _render_rerun_shell(payload)
    else:
        rendered = _render_json(payload) if args.format == "json" else _render_table(payload)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
