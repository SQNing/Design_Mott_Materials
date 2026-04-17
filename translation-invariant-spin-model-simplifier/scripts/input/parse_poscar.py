#!/usr/bin/env python3
from pathlib import Path
import warnings


def _annotate_structure_payload(payload, *, source_format, source_path):
    annotated = dict(payload)
    annotated.setdefault("source_format", str(source_format))
    annotated.setdefault("source_path", str(source_path))
    return annotated


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
    payload = parse_poscar_text(path.read_text(encoding="utf-8"))
    return _annotate_structure_payload(payload, source_format="poscar", source_path=path)


def _species_and_counts_from_sequence(species_sequence):
    species = []
    counts_by_species = {}
    for item in species_sequence:
        label = str(item)
        if label not in counts_by_species:
            species.append(label)
            counts_by_species[label] = 0
        counts_by_species[label] += 1
    return species, [counts_by_species[label] for label in species]


def _serialize_pymatgen_structure(structure, *, source_format, source_path):
    species, counts = _species_and_counts_from_sequence(site.specie for site in structure.sites)
    return {
        "comment": Path(source_path).name,
        "scale_factor": 1.0,
        "lattice_vectors": [[float(value) for value in row] for row in structure.lattice.matrix.tolist()],
        "species": species,
        "counts": counts,
        "coordinate_mode": "fractional",
        "selective_dynamics": False,
        "positions": [[float(value) for value in row] for row in structure.frac_coords.tolist()],
        "source_format": str(source_format),
        "source_path": str(source_path),
    }


def _parse_with_pymatgen(path):
    from pymatgen.core import Structure

    structure = Structure.from_file(str(path))
    source_format = path.suffix.lower().lstrip(".") or "structure"
    return _serialize_pymatgen_structure(
        structure,
        source_format=source_format,
        source_path=path,
    )


def _parse_with_ase(path):
    from ase.io import read

    suffix = path.suffix.lower()
    if suffix == ".cell":
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Generating CASTEP keywords JSON file.*",
                category=UserWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message=r"Could not determine the version of your CASTEP binary.*",
                category=UserWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message=r"read_cell: Warning - Was not able to validate CASTEP input.*",
                category=UserWarning,
            )
            atoms = read(str(path))
    else:
        atoms = read(str(path))
    species, counts = _species_and_counts_from_sequence(atoms.get_chemical_symbols())
    cell = atoms.cell.array.tolist()
    if atoms.pbc.any():
        coordinate_mode = "fractional"
        positions = atoms.get_scaled_positions(wrap=False).tolist()
    else:
        coordinate_mode = "cartesian"
        positions = atoms.get_positions().tolist()
    source_format = path.suffix.lower().lstrip(".") or "structure"
    return {
        "comment": Path(path).name,
        "scale_factor": 1.0,
        "lattice_vectors": [[float(value) for value in row] for row in cell],
        "species": species,
        "counts": counts,
        "coordinate_mode": coordinate_mode,
        "selective_dynamics": False,
        "positions": [[float(value) for value in row] for row in positions],
        "source_format": str(source_format),
        "source_path": str(path),
    }


def parse_structure_file(path):
    path = Path(path)
    lowered_name = path.name.lower()
    if lowered_name in {"poscar", "contcar"} or path.suffix.lower() == ".vasp":
        return parse_poscar_file(path)

    parse_errors = []
    for parser in (_parse_with_pymatgen, _parse_with_ase):
        try:
            return parser(path)
        except Exception as exc:  # pragma: no cover - exercised via fallback behavior
            parse_errors.append(f"{parser.__name__}: {exc}")
    raise ValueError(
        f"unsupported or unreadable structure format for {path}: " + "; ".join(parse_errors)
    )
