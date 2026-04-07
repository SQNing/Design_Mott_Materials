#!/usr/bin/env python3
from pathlib import Path

import numpy as np


def _nonempty_lines(text):
    return [line.rstrip("\n") for line in (text or "").splitlines() if line.strip()]


def parse_many_body_hr_text(text):
    lines = _nonempty_lines(text)
    if len(lines) < 4:
        raise ValueError("hr.dat text is too short")

    comment = lines[0].strip()
    num_wann = int(lines[1].strip())
    nrpts = int(lines[2].strip())

    degeneracies = []
    cursor = 3
    while len(degeneracies) < nrpts:
        values = [int(field) for field in lines[cursor].split()]
        degeneracies.extend(values)
        cursor += 1
    degeneracies = degeneracies[:nrpts]

    expected_rows = num_wann * num_wann * nrpts
    data_lines = lines[cursor:]
    if len(data_lines) != expected_rows:
        raise ValueError(
            f"expected {expected_rows} data rows for num_wann={num_wann}, nrpts={nrpts}, got {len(data_lines)}"
        )

    blocks_by_R = {}
    R_vectors = []
    for line in data_lines:
        fields = line.split()
        if len(fields) < 7:
            raise ValueError("data row must contain at least 7 fields")
        rx, ry, rz = (int(fields[0]), int(fields[1]), int(fields[2]))
        m = int(fields[3]) - 1
        n = int(fields[4]) - 1
        value = complex(float(fields[5]), float(fields[6]))
        R = (rx, ry, rz)
        if R not in blocks_by_R:
            blocks_by_R[R] = np.zeros((num_wann, num_wann), dtype=complex)
            R_vectors.append(R)
        blocks_by_R[R][m, n] = value

    if len(R_vectors) != nrpts:
        raise ValueError(f"expected {nrpts} unique R vectors, got {len(R_vectors)}")

    return {
        "comment": comment,
        "num_wann": num_wann,
        "nrpts": nrpts,
        "degeneracies": degeneracies,
        "R_vectors": R_vectors,
        "blocks_by_R": blocks_by_R,
    }


def parse_many_body_hr_file(path):
    path = Path(path)
    return parse_many_body_hr_text(path.read_text(encoding="utf-8"))
