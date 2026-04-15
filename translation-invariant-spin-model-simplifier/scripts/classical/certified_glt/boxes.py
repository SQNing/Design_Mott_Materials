#!/usr/bin/env python3

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParameterBox:
    names: list
    lower: list
    upper: list
    depth: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if len(self.names) != len(self.lower) or len(self.names) != len(self.upper):
            raise ValueError("names, lower, and upper must have identical lengths")
        normalized_lower = [float(value) for value in self.lower]
        normalized_upper = [float(value) for value in self.upper]
        for lower, upper in zip(normalized_lower, normalized_upper):
            if lower > upper:
                raise ValueError("box lower bound must not exceed upper bound")
        object.__setattr__(self, "lower", normalized_lower)
        object.__setattr__(self, "upper", normalized_upper)
        object.__setattr__(self, "names", [str(name) for name in self.names])
        object.__setattr__(self, "depth", int(self.depth))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def dimension(self):
        return len(self.names)

    def widths(self):
        return [float(upper - lower) for lower, upper in zip(self.lower, self.upper)]

    def midpoint(self):
        return [0.5 * (lower + upper) for lower, upper in zip(self.lower, self.upper)]

    def widest_dimension(self):
        widths = self.widths()
        if not widths:
            return 0
        return max(range(len(widths)), key=lambda index: (widths[index], -index))

    def split(self, axis=None):
        if self.dimension == 0:
            raise ValueError("cannot split a zero-dimensional box")
        split_axis = self.widest_dimension() if axis is None else int(axis)
        midpoint = self.midpoint()[split_axis]
        left_upper = list(self.upper)
        left_upper[split_axis] = midpoint
        right_lower = list(self.lower)
        right_lower[split_axis] = midpoint
        left = ParameterBox(
            names=list(self.names),
            lower=list(self.lower),
            upper=left_upper,
            depth=self.depth + 1,
            metadata=dict(self.metadata),
        )
        right = ParameterBox(
            names=list(self.names),
            lower=right_lower,
            upper=list(self.upper),
            depth=self.depth + 1,
            metadata=dict(self.metadata),
        )
        return left, right

    def to_dict(self):
        return {
            "names": list(self.names),
            "lower": list(self.lower),
            "upper": list(self.upper),
            "depth": int(self.depth),
            "metadata": dict(self.metadata),
        }
