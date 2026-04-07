#!/usr/bin/env python3
import itertools


def generate_q_mesh(mesh_shape):
    if len(mesh_shape) != 3:
        raise ValueError("mesh_shape must have length 3")

    axes = []
    for points in mesh_shape:
        points = int(points)
        if points <= 0:
            raise ValueError("mesh dimensions must be positive")
        if points == 1:
            axes.append([0.0])
        else:
            step = 1.0 / float(points - 1)
            axes.append([index * step for index in range(points)])

    return [list(point) for point in itertools.product(*axes)]
