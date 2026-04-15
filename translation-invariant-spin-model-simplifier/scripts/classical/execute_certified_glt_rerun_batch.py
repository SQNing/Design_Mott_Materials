#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def _load_shortlist(payload_path):
    if payload_path is None:
        return json.load(sys.stdin)
    return json.loads(Path(payload_path).read_text(encoding="utf-8"))


def execute_rerun_batch(shortlist, *, output_root, candidate_rank=1, progress_stream=None):
    progress_stream = progress_stream or sys.stderr
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    executions = []
    bundles = list(shortlist.get("bundles", []))
    total = len(bundles)
    for index, record in enumerate(bundles, start=1):
        bundle_dir = Path(record["bundle_dir"])
        bundle_name = bundle_dir.name
        output_dir = output_root / f"{index:02d}-{bundle_name}"
        command = [
            "bash",
            str(bundle_dir / "reproduce.sh"),
            str(output_dir),
            "--candidate-rank",
            str(int(candidate_rank)),
        ]
        print(
            f"[certified-glt-batch] step={index}/{total} bundle={bundle_name} output={output_dir}",
            file=progress_stream,
        )
        subprocess.run(command, check=True)
        executions.append(
            {
                "bundle_dir": str(bundle_dir),
                "output_dir": str(output_dir),
                "candidate_rank": int(candidate_rank),
                "status": "completed",
            }
        )
    return {
        "format": "certified_glt_rerun_batch",
        "executed_count": len(executions),
        "output_root": str(output_root),
        "executions": executions,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--candidate-rank", type=int, default=1)
    args = parser.parse_args()
    shortlist = _load_shortlist(args.input)
    payload = execute_rerun_batch(
        shortlist,
        output_root=args.output_root,
        candidate_rank=args.candidate_rank,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
