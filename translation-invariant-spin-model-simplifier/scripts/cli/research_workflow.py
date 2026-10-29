#!/usr/bin/env python3
"""Prepare, inspect, advance and report a host-agent research task."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.workflow import prepare_research_task, inspect_research_task, execute_research_action
from research.report import render_research_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "status", "step", "report"):
        p = sub.add_parser(name)
        p.add_argument("--run-dir", required=True)
        if name == "prepare":
            p.add_argument("--request", required=True)
        if name == "step":
            p.add_argument("--action", required=True)
            p.add_argument("--wait", action="store_true", help="wait for this worker; default returns its handle")
        if name == "report":
            p.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_research_task(json.loads(Path(args.request).read_text()), args.run_dir)
        elif args.command == "status":
            result = inspect_research_task(args.run_dir)
        elif args.command == "step":
            result = execute_research_action(args.run_dir, json.loads(Path(args.action).read_text()), wait=args.wait)
        else:
            result = render_research_report(args.run_dir, args.output_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "invalid_request", "blocker": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
