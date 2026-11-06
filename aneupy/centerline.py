"""Centerline processing: smoothing, arc-length parameterization and frames."""

import math
import warnings

import numpy as np
from scipy.interpolate import CubicSpline

from .profiles import read_table, smooth_uniform
from .transforms import rotate_vector
from .validation import GeometryError, GeometryWarning, as_finite_array, require_positive


class Centerline:
    """Smooth vessel axis parameterized by arc length.

    The input points are interpolated by a cubic spline in chord length, optionally
    smoothed, and resampled uniformly in arc length.

    Parameters
    ----------
    points : array_like, shape (n, 3)
        Ordered points in millimetres, with at least four distinct points.
    cutoff_length : float, optional
        Half-gain wavelength of the smoother in millimetres. Zero keeps the
        interpolating spline, which passes through every input point.
    spacing : float, optional
        Approximate spacing of the internal grid in millimetres.

    Attributes
    ----------
    points : numpy.ndarray
        Input points without consecutive repetitions.
    arc_length, xyz, tangents, curvature : numpy.ndarray
        Arc length, position, unit tangent and curvature on the internal grid.
    length : float
        Total length in millimetres.
    """

    def __init__(self, points, cutoff_length=0.0, spacing=1.0):
        points = as_finite_array(points, "centerline", shape=(None, 3))
        require_positive(spacing, "spacing")
        keep = np.r_[True, np.linalg.norm(np.diff(points, axis=0), axis=1) > 1.0e-9]
        if not np.all(keep):
            warnings.warn("Removed {} repeated centerline point(s)".format(int((~keep).sum())),
                          GeometryWarning, stacklevel=2)
        self.points = points[keep]
        if self.points.shape[0] < 4:
            raise GeometryError("A centerline needs at least four distinct points")
        chord = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(self.points, axis=0), axis=1))]
        count = max(int(math.ceil(chord[-1] / spacing)) + 1, 8)
        grid = np.linspace(0.0, chord[-1], count)
        dense = CubicSpline(chord, self.points)(grid)
        dense = smooth_uniform(dense, grid[1] - grid[0], cutoff_length)
        lengths = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))]
        self.length = float(lengths[-1])
        self.arc_length = np.linspace(0.0, self.length, count)
        self.xyz = np.column_stack([np.interp(self.arc_length, lengths, dense[:, axis])
                                    for axis in range(3)])
        step = self.arc_length[1] - self.arc_length[0]
        first_derivative = np.gradient(self.xyz, step, axis=0, edge_order=2)
        self.tangents = first_derivative / np.linalg.norm(first_derivative, axis=1, keepdims=True)
        self.curvature = np.linalg.norm(np.gradient(self.tangents, step, axis=0, edge_order=2), axis=1)

    @property
    def deviation_from_input(self):
        """Largest distance in millimetres from an input point to the processed curve."""
        start = self.xyz[:-1]
        direction = self.xyz[1:] - start
        squared_length = np.sum(direction ** 2, axis=1)
        largest = 0.0
        for point in self.points:
            fraction = np.clip(np.sum((point - start) * direction, axis=1) / squared_length, 0.0, 1.0)
            nearest = start + fraction[:, None] * direction
            largest = max(largest, float(np.linalg.norm(point - nearest, axis=1).min()))
        return largest

    def stations(self, count):
        """Return ``count`` arc lengths uniformly spaced from start to end."""
        if int(count) < 2:
            raise GeometryError("At least two stations are needed")
        return np.linspace(0.0, self.length, int(count))

    def position(self, arc_length):
        """Return positions at the given arc lengths."""
        return self._interpolate(arc_length, self.xyz)

    def tangent(self, arc_length):
        """Return unit tangents at the given arc lengths."""
        values = self._interpolate(arc_length, self.tangents)
        return values / np.linalg.norm(values, axis=1, keepdims=True)

    def curvature_at(self, arc_length):
        """Return curvature in 1/mm at the given arc lengths."""
        return np.interp(arc_length, self.arc_length, self.curvature)

    def frames(self, arc_length):
        """Return rotation-minimizing frames at the given arc lengths.

        The frame is carried along the curve by parallel transport, so the seam of each
        circular section stays aligned with its neighbours even for non-planar curves.

        Returns
        -------
        tuple of numpy.ndarray
            Local X axes and local Y axes, each with shape ``(n, 3)``. The local Z axis is
            the tangent.
        """
        x_axes = np.zeros_like(self.tangents)
        first = self.tangents[0]
        reference = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(reference, first)) > 0.9:
            reference = np.array([0.0, 1.0, 0.0])
        x_axis = reference - np.dot(reference, first) * first
        x_axes[0] = x_axis / np.linalg.norm(x_axis)
        for index in range(1, self.tangents.shape[0]):
            previous, current = self.tangents[index - 1], self.tangents[index]
            axis = np.cross(previous, current)
            norm = np.linalg.norm(axis)
            x_axis = x_axes[index - 1]
            if norm > 1.0e-12:
                angle = math.atan2(norm, np.dot(previous, current))
                x_axis = rotate_vector(x_axis, axis / norm, angle)
            x_axis = x_axis - np.dot(x_axis, current) * current
            x_axes[index] = x_axis / np.linalg.norm(x_axis)
        tangents = self.tangent(arc_length)
        local_x = self._interpolate(arc_length, x_axes)
        local_x = local_x - np.sum(local_x * tangents, axis=1, keepdims=True) * tangents
        local_x = local_x / np.linalg.norm(local_x, axis=1, keepdims=True)
        return local_x, np.cross(tangents, local_x)

    def _interpolate(self, arc_length, table):
        """Interpolate a table of vectors linearly in arc length."""
        arc_length = np.atleast_1d(np.asarray(arc_length, dtype=float))
        return np.column_stack([np.interp(arc_length, self.arc_length, table[:, axis])
                                for axis in range(3)])


def load_centerline(path, cutoff_length=0.0, spacing=1.0):
    """Load a three-column table of coordinates into a :class:`Centerline`."""
    return Centerline(read_table(path, 3), cutoff_length=cutoff_length, spacing=spacing)
