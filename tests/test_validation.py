import warnings

import numpy as np
import pytest

from aneupy import GeometryError, GeometryWarning
from aneupy import validation as v


def test_tube_curvature_limit():
    assert v.check_tube_curvature([0.01, 0.02], [10.0, 20.0]) == pytest.approx(0.4)
    with pytest.raises(GeometryError, match="too curved"):
        v.check_tube_curvature([0.1], [10.0])
    with pytest.warns(GeometryWarning):
        v.check_tube_curvature([0.09], [10.0])


def test_nested_radii():
    assert v.check_nested_radii([1.0, 2.0], [2.0, 2.5]) == pytest.approx(0.5)
    with pytest.raises(GeometryError, match="station 1"):
        v.check_nested_radii([1.0, 2.0], [2.0, 1.5])
    with pytest.raises(GeometryError, match="positive"):
        v.check_nested_radii([0.0, 2.0], [2.0, 2.5])
    with pytest.warns(GeometryWarning):
        v.check_nested_radii([1.0], [1.05])


def test_invalid_numbers_are_rejected():
    with pytest.raises(GeometryError):
        v.as_finite_array([1.0, np.nan], "x")
    with pytest.raises(GeometryError):
        v.as_finite_array(["a"], "x")
    with pytest.raises(GeometryError):
        v.as_vector3([1.0, 2.0], "x")
    with pytest.raises(GeometryError):
        v.as_direction([0.0, 0.0, 0.0], "x")
    with pytest.raises(GeometryError):
        v.require_positive(0.0, "x")
    with pytest.raises(GeometryError):
        v.require_non_negative(-1.0, "x")
    with pytest.raises(GeometryError):
        v.check_strictly_increasing([1.0, 1.0], "x")


def test_disc_intersection():
    centers = [[0.0, 0.0, 0.0], [0.0, 0.0, 10.0]]
    parallel = [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]]
    assert v.find_intersecting_sections(centers, parallel, [5.0, 5.0]) == []
    tilted = [[0.0, 0.0, 1.0], [np.sin(1.2), 0.0, np.cos(1.2)]]
    assert v.find_intersecting_sections(centers, tilted, [20.0, 20.0]) == [(0, 1)]
    assert v.find_intersecting_sections(centers, tilted, [1.0, 1.0]) == []
    with pytest.raises(GeometryError, match="intersect"):
        v.check_sections_do_not_intersect(centers, tilted, [20.0, 20.0])


def test_expected_volume_of_cylinder_and_cone():
    normals = np.tile([0.0, 0.0, 1.0], (11, 1))
    centers = np.column_stack([np.zeros(11), np.zeros(11), np.linspace(0.0, 10.0, 11)])
    assert v.expected_loft_volume(centers, normals, np.full(11, 2.0)) == pytest.approx(np.pi * 4.0 * 10.0)
    radii = np.linspace(1.0, 3.0, 11)
    assert v.expected_loft_volume(centers, normals, radii) == pytest.approx(np.pi * 10.0 / 3.0 * (1 + 3 + 9), rel=1e-4)


def test_expected_volume_requires_one_sense_of_advance():
    normals = np.tile([0.0, 0.0, 1.0], (5, 1))
    ascending = np.column_stack([np.zeros(5), np.zeros(5), np.arange(5.0)])
    forward = v.expected_loft_volume(ascending, normals, np.ones(5))
    assert v.expected_loft_volume(ascending[::-1], normals, np.ones(5)) == pytest.approx(forward)
    mixed = ascending[[0, 2, 1, 3, 4]]
    with pytest.raises(GeometryError, match="monotonically"):
        v.expected_loft_volume(mixed, normals, np.ones(5))


def test_cut_volume_check():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        v.check_cut_volume(50.0, 100.0, 50.0, "c")
    with pytest.warns(GeometryWarning):
        v.check_cut_volume(80.0, 100.0, 50.0, "c")
    with pytest.raises(GeometryError, match="no material"):
        v.check_cut_volume(0.0, 100.0, 150.0, "c")


def test_none_is_rejected():
    with pytest.raises(GeometryError):
        v.require_positive(None, "x")
    with pytest.raises(GeometryError):
        v.require_non_negative(None, "x")


def test_loft_volume_check():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert v.check_loft_volume(100.5, 100.0, "s") == pytest.approx(0.005)
    with pytest.warns(GeometryWarning):
        v.check_loft_volume(103.0, 100.0, "s")
    with pytest.raises(GeometryError, match="surface fit"):
        v.check_loft_volume(150.0, 100.0, "s")
