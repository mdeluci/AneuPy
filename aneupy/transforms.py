"""Rotation helpers shared by the geometric layers."""

import math

import numpy as np

from .validation import GeometryError, as_finite_array


def orthonormal_axes(x_axis, y_axis):
    """Return orthonormal local axes from two user directions.

    Parameters
    ----------
    x_axis, y_axis : array_like
        Local X and Y directions in global coordinates. ``y_axis`` is made
        orthogonal to ``x_axis``.

    Returns
    -------
    tuple of list of float
        Unit local X, Y and Z axes in global coordinates.

    Raises
    ------
    GeometryError
        If an axis is null or the two axes are parallel.
    """
    x_vector = as_finite_array(x_axis, "x_axis", shape=(3,))
    y_vector = as_finite_array(y_axis, "y_axis", shape=(3,))
    if np.linalg.norm(x_vector) < 1.0e-12 or np.linalg.norm(y_vector) < 1.0e-12:
        raise GeometryError("Section axes must be non-zero vectors")
    x_vector = x_vector / np.linalg.norm(x_vector)
    y_vector = y_vector - np.dot(y_vector, x_vector) * x_vector
    if np.linalg.norm(y_vector) < 1.0e-9:
        raise GeometryError("Section axes must not be parallel")
    y_vector = y_vector / np.linalg.norm(y_vector)
    z_vector = np.cross(x_vector, y_vector)
    return x_vector.tolist(), y_vector.tolist(), z_vector.tolist()


def axis_angle_from_axes(x_axis, y_axis, z_axis):
    """Return the rotation that takes the global axes onto the given local axes.

    Parameters
    ----------
    x_axis, y_axis, z_axis : sequence of float
        Orthonormal local axes in global coordinates.

    Returns
    -------
    tuple
        ``(axis, angle)``, with ``axis`` a unit vector and ``angle`` in radians.
        ``axis`` is ``None`` when the rotation is the identity.
    """
    rotation = np.column_stack([x_axis, y_axis, z_axis])
    cosine = max(-1.0, min(1.0, 0.5 * (float(np.trace(rotation)) - 1.0)))
    angle = math.acos(cosine)
    if angle < 1.0e-12:
        return None, 0.0
    sine = math.sin(angle)
    if sine > 1.0e-9:
        axis = np.array([rotation[2, 1] - rotation[1, 2],
                         rotation[0, 2] - rotation[2, 0],
                         rotation[1, 0] - rotation[0, 1]]) / (2.0 * sine)
    else:
        # The rotation is close to a half turn, where the formula above is singular.
        symmetric = 0.5 * (rotation + np.eye(3))
        index = int(np.argmax(np.diag(symmetric)))
        axis = symmetric[:, index] / math.sqrt(max(symmetric[index, index], 1.0e-30))
    return (axis / np.linalg.norm(axis)).tolist(), angle


def rotate_vector(vector, axis, angle):
    """Rotate ``vector`` about the unit ``axis`` by ``angle`` radians (Rodrigues)."""
    vector = np.asarray(vector, dtype=float)
    axis = np.asarray(axis, dtype=float)
    return (vector * math.cos(angle) + np.cross(axis, vector) * math.sin(angle)
            + axis * np.dot(axis, vector) * (1.0 - math.cos(angle)))
