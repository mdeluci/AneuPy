"""Reading, mapping and smoothing of one-dimensional axial profiles."""

import math
import warnings

import numpy as np

from .validation import GeometryError, GeometryWarning, as_finite_array, require_non_negative

#: Order of the difference penalty used by :func:`smooth_uniform`.
SMOOTHING_ORDER = 3


def read_table(path, columns):
    """Read a numeric table separated by commas and/or whitespace.

    Blank lines and lines starting with ``#`` are ignored.

    Parameters
    ----------
    path : str
        File path.
    columns : int
        Required number of columns.

    Returns
    -------
    numpy.ndarray
        Array of shape ``(n, columns)``.

    Raises
    ------
    GeometryError
        If the file is missing, a row has the wrong number of columns, or a value
        is not a finite number. The message names the file and the line.
    """
    try:
        with open(str(path)) as handle:
            lines = handle.readlines()
    except OSError as error:
        raise GeometryError("Cannot read {}: {}".format(path, error))
    rows = []
    for number, line in enumerate(lines, start=1):
        text = line.split("#", 1)[0].replace(",", " ").strip()
        if not text:
            continue
        fields = text.split()
        if len(fields) != columns:
            raise GeometryError("{}, line {}: expected {} columns, found {}".format(
                path, number, columns, len(fields)))
        try:
            row = [float(field) for field in fields]
        except ValueError:
            raise GeometryError("{}, line {}: non-numeric value in '{}'".format(
                path, number, line.strip()))
        if not all(math.isfinite(value) for value in row):
            raise GeometryError("{}, line {}: NaN or infinite value".format(path, number))
        rows.append(row)
    if not rows:
        raise GeometryError("{} contains no data".format(path))
    return as_finite_array(rows, str(path), shape=(None, columns))


def smoothing_weight(spacing, cutoff_length, order=SMOOTHING_ORDER):
    """Return the penalty weight whose half-gain wavelength is ``cutoff_length``.

    The smoother of :func:`smooth_uniform` has the interior transfer function
    ``1 / (1 + weight * (2 sin(pi spacing / wavelength)) ** (2 * order))``.
    """
    return (2.0 * math.sin(math.pi * min(spacing / cutoff_length, 0.5))) ** (-2.0 * order)


def smooth_uniform(values, spacing, cutoff_length, order=SMOOTHING_ORDER):
    """Smooth uniformly sampled data by penalized least squares.

    Minimizes ``||z - y||^2 + weight ||D z||^2``, where ``D`` is the difference matrix of
    the given ``order`` (Whittaker smoother). Oscillations with wavelength
    ``cutoff_length`` keep half of their amplitude, shorter ones are attenuated more,
    and polynomials of degree below ``order`` are preserved exactly.

    Parameters
    ----------
    values : array_like
        Samples, with one or two dimensions (filtered along the first axis).
    spacing : float
        Sample spacing in millimetres.
    cutoff_length : float
        Half-gain wavelength in millimetres. Zero returns a copy of the input.
    order : int, optional
        Order of the difference penalty.

    Returns
    -------
    numpy.ndarray
        Smoothed samples.
    """
    values = as_finite_array(values, "values")
    if require_non_negative(cutoff_length, "cutoff_length") == 0.0:
        return values.copy()
    size = values.shape[0]
    if size <= order:
        raise GeometryError("At least {} samples are needed to smooth".format(order + 1))
    difference = np.diff(np.eye(size), n=order, axis=0)
    system = np.eye(size) + smoothing_weight(spacing, cutoff_length, order) * difference.T.dot(difference)
    return np.linalg.solve(system, values)


class AreaProfile:
    """Cross-sectional area measured along a vessel.

    Parameters
    ----------
    abscissa : array_like
        Axial position of each measurement. Only its range and its relative spacing
        are used, because the profile is mapped linearly onto the centerline length.
    area : array_like
        Enclosed area in square millimetres.
    name : str, optional
        Name used in messages.
    """

    def __init__(self, abscissa, area, name="profile"):
        self.name = name
        abscissa = as_finite_array(abscissa, name + " abscissa", shape=(None,))
        area = as_finite_array(area, name + " area", shape=(abscissa.size,))
        if abscissa.size < 2:
            raise GeometryError("{} needs at least two points".format(name))
        if np.any(area <= 0.0):
            raise GeometryError("{}: area must be positive; row {} has {}".format(
                name, int(np.argmax(area <= 0.0)) + 1, float(area[np.argmax(area <= 0.0)])))
        order = np.argsort(abscissa, kind="mergesort")
        if np.any(np.diff(abscissa) <= 0.0):
            warnings.warn("{} abscissa is not strictly increasing; points were sorted and "
                          "repeated positions averaged".format(name), GeometryWarning, stacklevel=2)
        unique, inverse = np.unique(abscissa[order], return_inverse=True)
        self.abscissa = unique
        self.area = np.bincount(inverse, weights=area[order]) / np.bincount(inverse)

    @property
    def radius(self):
        """Radius of the circle with the same area, in millimetres."""
        return np.sqrt(self.area / np.pi)

    @property
    def abscissa_range(self):
        """First and last axial positions."""
        return float(self.abscissa[0]), float(self.abscissa[-1])

    def radius_on_arc_length(self, length, spacing=1.0, cutoff_length=0.0, flip=False,
                             abscissa_range=None):
        """Map the equivalent radius onto arc length and optionally smooth it.

        The abscissa range is mapped linearly onto ``[0, length]``. Positions beyond
        the measured range take the nearest measured value.

        Parameters
        ----------
        length : float
            Centerline length in millimetres.
        spacing : float, optional
            Spacing of the uniform output grid in millimetres.
        cutoff_length : float, optional
            Half-gain wavelength of the smoother in millimetres. Zero disables it.
        flip : bool, optional
            If true, the first abscissa corresponds to the end of the centerline.
        abscissa_range : tuple of float, optional
            Range mapped onto the centerline. Use a common range for profiles that
            share an axial coordinate.

        Returns
        -------
        tuple of numpy.ndarray
            Arc length grid and radius on that grid.
        """
        first, last = abscissa_range if abscissa_range is not None else self.abscissa_range
        if last <= first:
            raise GeometryError("{} abscissa range must be increasing".format(self.name))
        position = (self.abscissa - first) / (last - first) * length
        radius = self.radius
        if flip:
            position, radius = length - position[::-1], radius[::-1]
        count = max(int(math.ceil(length / spacing)) + 1, SMOOTHING_ORDER + 2)
        grid = np.linspace(0.0, length, count)
        values = np.interp(grid, position, radius)
        values = smooth_uniform(values, grid[1] - grid[0], cutoff_length)
        return grid, values


def load_area_profile(path, name=None):
    """Load a two-column table of axial position and area into an :class:`AreaProfile`."""
    table = read_table(path, 2)
    label = "{} ({})".format(name, path) if name else str(path)
    return AreaProfile(table[:, 0], table[:, 1], name=label)
