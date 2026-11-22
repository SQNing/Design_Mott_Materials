#!/usr/bin/env python3
"""List, sync and query the workspace-level research run registry."""
import argparse
import glob
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.phase_report import render_phase_map_report
from research.registry import (default_registry_path, find_fingerprint,
                               load_registry, query_runs, record_run, sync_runs)


def _registry_arg(parser):
    parser.add_argument("--registry", help="registry.jsonl path; default: <workspace>/registry.jsonl")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("record", help="append/update one run_dir entry")
    p.add_argument("--run-dir", required=True)
    _registry_arg(p)

    p = sub.add_parser("sync", help="record many run directories")
    p.add_argument("--registry", required=True)
    p.add_argument("--run-dir", action="append", default=[])
    p.add_argument("--runs-glob", action="append", default=[])

    p = sub.add_parser("list", help="list latest entries")
    _registry_arg(p)
    p.add_argument("--status")
    p.add_argument("--claim-level")
    p.add_argument("--model-id")
    p.add_argument("--task")
    p.add_argument("--text")

    p = sub.add_parser("show", help="show latest entry for one run_dir")
    p.add_argument("--run-dir", required=True)
    _registry_arg(p)

    p = sub.add_parser("find-fingerprint")
    p.add_argument("--fingerprint", required=True)
    _registry_arg(p)

    p = sub.add_parser("phase-report", help="render single-page phase map from registry")
    _registry_arg(p)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--model-id")

    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            registry = args.registry or default_registry_path(run_dir=args.run_dir)
            result = record_run(args.run_dir, registry)
        elif args.command == "sync":
            run_dirs = list(args.run_dir)
            for pattern in args.runs_glob:
                run_dirs.extend(sorted(glob.glob(pattern)))
            result = sync_runs(run_dirs, args.registry)
        elif args.command == "list":
            registry = args.registry or default_registry_path(workspace=Path.cwd())
            result = query_runs(registry, status=args.status,
                                claim_level=args.claim_level,
                                model_id=args.model_id, task=args.task,
                                text=args.text)
        elif args.command == "show":
            registry = args.registry or default_registry_path(run_dir=args.run_dir)
            run_dir = str(Path(args.run_dir).expanduser().resolve())
            result = next((entry for entry in load_registry(registry)
                           if entry.get("run_dir") == run_dir), None)
            if result is None:
                raise ValueError("run_dir not present in registry: " + run_dir)
        elif args.command == "phase-report":
            registry = args.registry or default_registry_path(workspace=Path.cwd())
            result = render_phase_map_report(registry, args.output_dir,
                                             model_id=args.model_id)
        else:
            registry = args.registry or default_registry_path(workspace=Path.cwd())
            result = find_fingerprint(registry, args.fingerprint)
            if result is None:
                raise ValueError("fingerprint not present in registry")
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "invalid_request", "blocker": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
