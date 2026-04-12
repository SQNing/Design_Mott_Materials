#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lswt.build_python_glswt_payload import build_python_glswt_payload
from lswt.python_glswt_solver import solve_python_glswt


def _load_json_payload(payload):
    if isinstance(payload, dict):
        return payload
    if payload is None:
        return json.load(sys.stdin)
    return json.loads(Path(payload).read_text(encoding="utf-8"))


def run_python_glswt_driver(payload):
    payload = _load_json_payload(payload)
    if payload.get("payload_kind") == "python_glswt_local_rays":
        normalized = dict(payload)
    else:
        normalized = build_python_glswt_payload(payload)
    result = solve_python_glswt(normalized)
    if "path" not in result:
        result["path"] = dict(normalized.get("path", {}))
    if "classical_reference" not in result:
        result["classical_reference"] = dict(normalized.get("classical_reference", {}))
    if "ordering" not in result:
        result["ordering"] = dict(normalized.get("ordering", {}))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    args = parser.parse_args()
    result = run_python_glswt_driver(args.input)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
