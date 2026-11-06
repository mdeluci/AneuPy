"""Input validation and runtime checks of geometric limits.

All functions are pure and independent of SALOME. Violations that make a geometry
impossible raise :class:`GeometryError`. Conditions close to a known limit emit
:class:`GeometryWarning`.
"""

import math
import warnings

import numpy as np
from scipy.interpolate import CubicSpline

#: Curvature-radius product above which a warning is emitted.
CURVATURE_WARNING_RATIO = 0.8


class GeometryError(ValueError):
    """The requested geometry is invalid or cannot be built."""


class GeometryWarning(UserWarning):
    """The requested geometry is valid but close to a known limit."""


def as_finite_array(values, name, shape=None):
    """Return ``values`` as a float array after checking that it is finite.

    Parameters
    ----------
    values : array_like
        Input values.
    name : str
        Name used in error messages.
    shape : tuple of (int or None), optional
        Required shape. ``None`` entries match any length.

    Returns
    -------
    numpy.ndarray
        Array of floats.

    Raises
    ------
    GeometryError
        If the values are not numeric, not finite, or have the wrong shape.
    """
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as error:
        raise GeometryError("{} must contain only numbers: {}".format(name, error))
    if shape is not None:
        matches = array.ndim == len(shape) and all(
            expected is None or size == expected for size, expected in zip(array.shape, shape))
        if not matches:
            raise GeometryError("{} must have shape {}, got {}".format(name, shape, array.shape))
    if not np.all(np.isfinite(array)):
        raise GeometryError("{} contains NaN or infinite values".format(name))
    return array


def as_vector3(values, name):
    """Return a finite three-component vector as a list of floats."""
    return [float(value) for value in as_finite_array(values, name, shape=(3,))]


def as_direction(values, name):
    """Return a unit vector, raising :class:`GeometryError` for a null vector."""
    vector = np.array(as_vector3(values, name))
    norm = float(np.linalg.norm(vector))
    if norm < 1.0e-12:
        raise GeometryError("{} must be a non-zero vector".format(name))
    return (vector / norm).tolist()


def require_positive(value, name):
    """Return ``value`` as a float after checking that it is finite and positive."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise GeometryError("{} must be a positive number, got {}".format(name, value))
    if not math.isfinite(number) or number <= 0.0:
        raise GeometryError("{} must be a positive number, got {}".format(name, value))
    return number


def require_non_negative(value, name):
    """Return ``value`` as a float after checking that it is finite and not negative."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise GeometryError("{} must be zero or positive, got {}".format(name, value))
    if not math.isfinite(number) or number < 0.0:
        raise GeometryError("{} must be zero or positive, got {}".format(name, value))
    return number


def check_nested_radii(inner, outer, inner_name="lumen", outer_name="wall", warn_thickness=0.1):
    """Check that the outer boundary encloses the inner one at every station.

    Parameters
    ----------
    inner, outer : array_like
        Radii in millimetres at the same stations.
    inner_name, outer_name : str
        Names used in messages.
    warn_thickness : float, optional
        Thickness in millimetres below which a warning is emitted.

    Returns
    -------
    float
        The minimum thickness ``outer - inner``.

    Raises
    ------
    GeometryError
        If a radius is not positive or the boundaries touch or cross.
    """
    inner = as_finite_array(inner, inner_name, shape=(None,))
    outer = as_finite_array(outer, outer_name, shape=(inner.size,))
    if np.any(inner <= 0.0):
        raise GeometryError("{} radius must be positive at every station".format(inner_name))
    thickness = outer - inner
    minimum = float(thickness.min())
    if minimum <= 0.0:
        station = int(thickness.argmin())
        raise GeometryError(
            "{} radius must exceed {} radius; station {} has thickness {:.3f} mm".format(
                outer_name, inner_name, station, minimum))
    if minimum < warn_thickness:
        warnings.warn(
            "Minimum thickness between {} and {} is {:.3f} mm; Boolean operations and meshing "
            "may fail".format(inner_name, outer_name, minimum), GeometryWarning, stacklevel=2)
    return minimum


def check_tube_curvature(curvature, radii, name="section"):
    """Check that sections normal to the centerline do not fold onto each other.

    A tube of radius ``r`` around a curve of curvature ``kappa`` is free of local
    self-intersection only if ``kappa * r < 1``. Tight bends, as in the aortic arch,
    violate this bound for large radii.

    Parameters
    ----------
    curvature, radii : array_like
        Curvature in 1/mm and radius in mm at the same stations.
    name : str, optional
        Name used in messages.

    Returns
    -------
    float
        The maximum of ``kappa * r``.

    Raises
    ------
    GeometryError
        If ``kappa * r >= 1`` at any station.
    """
    curvature = as_finite_array(curvature, "curvature", shape=(None,))
    radii = as_finite_array(radii, "radii", shape=(curvature.size,))
    ratio = curvature * radii
    maximum = float(ratio.max())
    if maximum >= 1.0:
        station = int(ratio.argmax())
        raise GeometryError(
            "Centerline too curved for {} radius at station {}: curvature x radius = {:.2f} "
            "(must stay below 1). Increase the centerline smoothing or use fewer, more widely "
            "spaced stations only after checking the geometry.".format(name, station, maximum))
    if maximum > CURVATURE_WARNING_RATIO:
        warnings.warn(
            "Curvature x radius reaches {:.2f} for {}; the limit is 1 and the surface may "
            "degrade near it".format(maximum, name), GeometryWarning, stacklevel=2)
    return maximum


def find_intersecting_sections(centers, normals, radii):
    """Return index pairs of circular sections whose discs intersect.

    Parameters
    ----------
    centers, normals : array_like, shape (n, 3)
        Disc centres and unit normals.
    radii : array_like, shape (n,)
        Disc radii.

    Returns
    -------
    list of tuple of int
        Pairs ``(i, j)`` with ``i < j``.
    """
    centers = as_finite_array(centers, "centers", shape=(None, 3))
    normals = as_finite_array(normals, "normals", shape=(centers.shape[0], 3))
    radii = as_finite_array(radii, "radii", shape=(centers.shape[0],))
    pairs = []
    for i in range(centers.shape[0] - 1):
        for j in range(i + 1, centers.shape[0]):
            if _discs_intersect(centers[i], normals[i], radii[i], centers[j], normals[j], radii[j]):
                pairs.append((i, j))
    return pairs


def _discs_intersect(center_a, normal_a, radius_a, center_b, normal_b, radius_b):
    """Return whether two discs in space intersect."""
    direction = np.cross(normal_a, normal_b)
    norm = np.linalg.norm(direction)
    if norm < 1.0e-12:
        coplanar = abs(np.dot(center_b - center_a, normal_a)) < 1.0e-9
        return bool(coplanar and np.linalg.norm(center_b - center_a) < radius_a + radius_b)
    direction = direction / norm
    # Point on the line where both planes meet.
    offsets = np.array([np.dot(normal_a, center_a), np.dot(normal_b, center_b), 0.0])
    point = np.linalg.solve(np.vstack([normal_a, normal_b, direction]), offsets)
    chords = []
    for center, radius in ((center_a, radius_a), (center_b, radius_b)):
        along = np.dot(center - point, direction)
        distance = np.linalg.norm(center - point - along * direction)
        if distance >= radius:
            return False
        chords.append((along, math.sqrt(radius ** 2 - distance ** 2)))
    return bool(abs(chords[0][0] - chords[1][0]) < chords[0][1] + chords[1][1])


def check_cut_volume(result, first, second, name):
    """Check a Boolean difference, in which a layer normally encloses the removed solid.

    Parameters
    ----------
    result, first, second : float
        Volumes of ``first - second``, of ``first`` and of ``second``, in cubic millimetres.
    name : str
        Name of the resulting solid.

    Raises
    ------
    GeometryError
        If the cut leaves no material, which means that the removed solid encloses the other.
    """
    if result <= 1.0e-6 * first:
        raise GeometryError("The cut '{}' leaves no material: the removed solid encloses the other one".format(name))
    if abs(result - (first - second)) > 0.01 * first:
        warnings.warn("The cut '{}' removed {:.0f} mm3 of a solid of {:.0f} mm3: the removed solid is not fully "
                      "inside the other one".format(name, first - result, second), GeometryWarning, stacklevel=2)


def check_sections_do_not_intersect(centers, normals, radii, name="section"):
    """Raise :class:`GeometryError` if any two section discs intersect."""
    pairs = find_intersecting_sections(centers, normals, radii)
    if pairs:
        raise GeometryError(
            "{} discs intersect at {} station pair(s), first at {}. The lofted surface would "
            "self-intersect; reduce the curvature or the radius.".format(name, len(pairs), pairs[0]))


def check_strictly_increasing(values, name):
    """Raise :class:`GeometryError` unless ``values`` strictly increase."""
    values = as_finite_array(values, name, shape=(None,))
    if np.any(np.diff(values) <= 0.0):
        raise GeometryError("{} must be strictly increasing".format(name))


def expected_loft_volume(centers, normals, radii):
    """Return the volume enclosed by a smooth loft through circular sections.

    The axial coordinate advances by the projection of each step between centres on the
    mean normal of the two sections, and the radius is interpolated with a cubic spline.
    For sections normal to a curve this is the theorem of Pappus and Guldinus. Sections may
    run with or against their normals, but all in the same sense.

    Parameters
    ----------
    centers, normals : array_like, shape (n, 3)
        Section centres and unit normals.
    radii : array_like, shape (n,)
        Section radii.

    Returns
    -------
    float
        Volume in cubic millimetres.
    """
    centers = as_finite_array(centers, "centers", shape=(None, 3))
    normals = as_finite_array(normals, "normals", shape=(centers.shape[0], 3))
    radii = as_finite_array(radii, "radii", shape=(centers.shape[0],))
    mean_normals = normals[1:] + normals[:-1]
    mean_normals = mean_normals / np.linalg.norm(mean_normals, axis=1, keepdims=True)
    steps = np.sum((centers[1:] - centers[:-1]) * mean_normals, axis=1)
    if np.all(steps < 0.0):
        steps = -steps
    if np.any(steps <= 0.0):
        raise GeometryError("Sections must advance monotonically along their normals; check their order")
    axial = np.r_[0.0, np.cumsum(steps)]
    fine = np.linspace(0.0, axial[-1], 40 * axial.size)
    areas = np.pi * CubicSpline(axial, radii)(fine) ** 2
    return float(np.sum(0.5 * (areas[1:] + areas[:-1]) * np.diff(fine)))


def check_loft_volume(actual, expected, name, warn_ratio=0.01, error_ratio=0.05):
    """Compare the volume of a built solid with the volume implied by its sections.

    The surface fit can fail silently for some section layouts, which produces a surface
    far from the requested sections. Such a failure changes the enclosed volume.

    Parameters
    ----------
    actual, expected : float
        Volumes in cubic millimetres.
    name : str
        Solid name.
    warn_ratio, error_ratio : float, optional
        Relative differences that trigger a warning and an error.

    Returns
    -------
    float
        Relative difference.

    Raises
    ------
    GeometryError
        If the difference exceeds ``error_ratio``.
    """
    difference = abs(actual - expected) / expected
    if difference > error_ratio:
        raise GeometryError(
            "The surface fit of '{}' failed: its volume is {:.0f} mm3 and its sections imply {:.0f} mm3. "
            "Change the number of sections.".format(name, actual, expected))
    if difference > warn_ratio:
        warnings.warn("The volume of '{}' differs by {:.1%} from the value implied by its sections; "
                      "inspect the surface".format(name, difference), GeometryWarning, stacklevel=2)
    return difference
