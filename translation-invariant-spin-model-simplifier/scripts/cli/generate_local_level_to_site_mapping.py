#!/usr/bin/env python3
import argparse
import json


def _parse_levels_per_site(text):
    values = [field.strip() for field in str(text).split(",")]
    levels_per_site = [int(value) for value in values if value]
    if not levels_per_site or any(value <= 0 for value in levels_per_site):
        raise ValueError("levels-per-site must contain positive integers only")
    return levels_per_site


def generate_local_level_to_site_mapping(levels_per_site):
    level_cursor = 0
    site_level_mapping = []
    for site_index, level_count in enumerate(levels_per_site):
        site_level_mapping.append(
            {
                "site": int(site_index),
                "level_indexes": list(range(level_cursor, level_cursor + int(level_count))),
            }
        )
        level_cursor += int(level_count)
    return {
        "schema_version": 1,
        "site_level_mapping": site_level_mapping,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels-per-site", required=True)
    args = parser.parse_args()
    levels_per_site = _parse_levels_per_site(args.levels_per_site)
    payload = generate_local_level_to_site_mapping(levels_per_site)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
