#!/usr/bin/env python3
from pathlib import Path


def _strip_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _parse_vector(line):
    fields = line.split()
    if len(fields) < 3:
        raise ValueError("lattice vector line must contain at least three numbers")
    return [float(fields[0]), float(fields[1]), float(fields[2])]


def _parse_counts(line):
    fields = line.split()
    if not fields:
        raise ValueError("species counts line must be non-empty")
    return [int(value) for value in fields]


def _parse_positions(lines, count):
    positions = []
    for line in lines[:count]:
        fields = line.split()
        if len(fields) < 3:
            raise ValueError("position line must contain at least three coordinates")
        positions.append([float(fields[0]), float(fields[1]), float(fields[2])])
    if len(positions) != count:
        raise ValueError("POSCAR does not contain the expected number of positions")
    return positions


def parse_poscar_text(text):
    lines = _strip_lines(text)
    if len(lines) < 8:
        raise ValueError("POSCAR text is too short")

    comment = lines[0]
    scale_factor = float(lines[1])
    lattice_vectors = [_parse_vector(lines[2]), _parse_vector(lines[3]), _parse_vector(lines[4])]
    species = lines[5].split()
    counts = _parse_counts(lines[6])
    if len(species) != len(counts):
        raise ValueError("species and counts lengths do not match")

    coordinate_mode_index = 7
    selective_dynamics = False
    if lines[coordinate_mode_index].lower().startswith("selective"):
        selective_dynamics = True
        coordinate_mode_index += 1

    coordinate_mode = lines[coordinate_mode_index]
    total_sites = sum(counts)
    position_start = coordinate_mode_index + 1
    positions = _parse_positions(lines[position_start:], total_sites)

    return {
        "comment": comment,
        "scale_factor": scale_factor,
        "lattice_vectors": lattice_vectors,
        "species": species,
        "counts": counts,
        "coordinate_mode": coordinate_mode,
        "selective_dynamics": selective_dynamics,
        "positions": positions,
    }


def parse_poscar_file(path):
    path = Path(path)
    return parse_poscar_text(path.read_text(encoding="utf-8"))
