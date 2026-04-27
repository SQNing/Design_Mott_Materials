#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from input.parse_poscar import parse_structure_file


def _parse_levels_per_site(text):
    values = [field.strip() for field in str(text).split(",")]
    levels_per_site = [int(value) for value in values if value]
    if not levels_per_site or any(value <= 0 for value in levels_per_site):
        raise ValueError("levels-per-site must contain positive integers only")
    return levels_per_site


def _resolve_site_count(structure_path):
    structure = parse_structure_file(Path(structure_path))
    positions = list(structure.get("positions") or [])
    if not positions:
        raise ValueError("structure does not contain any sites")
    return len(positions)


def _resolve_levels_per_site(levels_per_site, site_count):
    if len(levels_per_site) == 1 and site_count is not None:
        return [int(levels_per_site[0])] * int(site_count)
    if site_count is not None and len(levels_per_site) != int(site_count):
        raise ValueError("levels-per-site count must match site count")
    return [int(value) for value in levels_per_site]


def _parse_site_labels(text):
    labels = [field.strip() for field in str(text).split(",") if field.strip()]
    return labels


def generate_local_level_to_site_mapping(levels_per_site, site_labels=None):
    level_cursor = 0
    site_level_mapping = []
    for site_index, level_count in enumerate(levels_per_site):
        item = {
            "site": int(site_index),
            "level_indexes": list(range(level_cursor, level_cursor + int(level_count))),
        }
        if site_labels is not None:
            item["label"] = str(site_labels[site_index])
        site_level_mapping.append(item)
        level_cursor += int(level_count)
    return {
        "schema_version": 1,
        "site_level_mapping": site_level_mapping,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels-per-site", required=True)
    parser.add_argument("--structure")
    parser.add_argument("--site-labels")
    args = parser.parse_args()
    site_count = _resolve_site_count(args.structure) if args.structure else None
    levels_per_site = _resolve_levels_per_site(_parse_levels_per_site(args.levels_per_site), site_count)
    site_labels = _parse_site_labels(args.site_labels) if args.site_labels else None
    if site_labels is not None and len(site_labels) != len(levels_per_site):
        raise ValueError("site-labels count must match site count")
    payload = generate_local_level_to_site_mapping(levels_per_site, site_labels=site_labels)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
