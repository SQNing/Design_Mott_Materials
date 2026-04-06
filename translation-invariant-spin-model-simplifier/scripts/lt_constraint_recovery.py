#!/usr/bin/env python3
import math

import numpy as np


def reconstruct_single_q_real_space_state(positions, q, amplitudes):
    q_vector = np.array([float(value) for value in q], dtype=float)
    while len(q_vector) < 3:
        q_vector = np.append(q_vector, 0.0)

    spins = []
    for position, amplitude in zip(positions, amplitudes):
        position_vector = np.array([float(value) for value in position], dtype=float)
        while len(position_vector) < 3:
            position_vector = np.append(position_vector, 0.0)
        phase = 2.0 * math.pi * float(np.dot(q_vector, position_vector))
        complex_spin = amplitude * np.exp(1j * phase)
        spins.append(np.array([float(np.real(complex_spin)), float(np.imag(complex_spin)), 0.0]))
    return spins


def strong_constraint_residual(spins):
    residual = 0.0
    for spin in spins:
        norm_sq = float(np.dot(spin, spin))
        residual += (norm_sq - 1.0) ** 2
    return float(residual)
