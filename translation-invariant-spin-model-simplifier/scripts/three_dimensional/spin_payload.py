"""Adapt validated canonical spin bonds to a common global Cartesian frame."""

import numpy as np
from classical.build_spin_only_solver_payload import build_spin_only_solver_payload
from common.hamiltonian_symmetry_action import _local_frames


def global_spin_payload(gate):
    payload = build_spin_only_solver_payload(gate)["payload"]
    model = gate["solver_model"]
    frames = _local_frames(model["lattice_structure"])
    for site, frame in frames.items():
        if not np.allclose(frame.T @ frame, np.eye(3), atol=1e-10) or not np.isclose(np.linalg.det(frame), 1):
            raise ValueError("local spin frames must be proper orthogonal rotations: site %d" % site)
    converted = []
    for term, bond in zip(model["terms"], payload["bonds"]):
        if term.get("coordinate_convention") == "local_frames":
            left = frames.get(bond["source"], np.eye(3))
            right = frames.get(bond["target"], np.eye(3))
            bond["matrix"] = (left @ np.array(bond["matrix"]) @ right.T).tolist()
            converted.append(term["term_ref"])
    payload["bridge_metadata"]["global_frame_converted_terms"] = converted
    return payload
