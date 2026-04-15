#!/usr/bin/env python3

from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import eigvalsh


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self):
        if float(self.lower) > float(self.upper):
            raise ValueError("interval lower bound must not exceed upper bound")
        object.__setattr__(self, "lower", float(self.lower))
        object.__setattr__(self, "upper", float(self.upper))

    @property
    def midpoint(self):
        return 0.5 * (self.lower + self.upper)

    @property
    def radius(self):
        return 0.5 * (self.upper - self.lower)


def symmetric_interval(center, radius):
    center = float(center)
    radius = abs(float(radius))
    return Interval(center - radius, center + radius)


def spectral_lower_from_center_radius(center_matrix, radius_matrix):
    center = np.array(center_matrix, dtype=float)
    radius = np.array(radius_matrix, dtype=float)
    if center.size == 0:
        return 0.0
    symmetric = 0.5 * (center + center.T)
    eigenvalues = np.array(eigvalsh(symmetric), dtype=float)
    row_sum_upper = float(np.max(np.sum(np.abs(radius), axis=1))) if radius.size else 0.0
    return float(eigenvalues[0] - row_sum_upper)


def matrix_abs_upper(matrix):
    array = np.array(matrix)
    return float(np.max(np.abs(array))) if array.size else 0.0


def interval_norm_upper(vectors):
    array = np.array(vectors, dtype=float)
    return float(np.linalg.norm(array))


def quadratic_lower_over_radius_interval(quadratic_coefficient, linear_norm_upper, constant_lower, radius_interval):
    quadratic_coefficient = float(quadratic_coefficient)
    linear_norm_upper = abs(float(linear_norm_upper))
    constant_lower = float(constant_lower)
    radius_interval = Interval(*radius_interval)
    candidates = [radius_interval.lower, radius_interval.upper]
    if abs(quadratic_coefficient) > 1.0e-14:
        stationary = linear_norm_upper / quadratic_coefficient if quadratic_coefficient > 0.0 else None
        if stationary is not None and radius_interval.lower <= stationary <= radius_interval.upper:
            candidates.append(stationary)
    values = [
        constant_lower - 2.0 * linear_norm_upper * radius + quadratic_coefficient * radius * radius
        for radius in candidates
    ]
    return float(min(values))


def radius_interval_from_values(values):
    positive = [max(0.0, float(value)) for value in values]
    return math.sqrt(min(positive)), math.sqrt(max(positive))
