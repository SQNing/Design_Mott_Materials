#!/usr/bin/env python3
"""Boundary adapter for inputs that must land on the lattice term contract."""

from __future__ import annotations

from copy import deepcopy

from common.lattice_term_contract import validate_lattice_term_payload
from input.normalize_input import normalize_input


def convert_legacy_payload_to_lattice_term_payload(payload):
    """Normalize an older public payload shape into the canonical contract."""
    normalized = normalize_input(deepcopy(payload))
    return validate_lattice_term_payload(normalized)
