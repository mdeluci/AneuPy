import numpy as np
import pytest

from aneupy import Centerline, GeometryError, GeometryWarning


def arc(radius, angle, count=60):
    t = np.linspace(0.0, angle, count)
    return np.column_stack([radius * np.cos(t), radius * np.sin(t), np.zeros(count)])


def helix(radius=40.0, pitch=30.0, turns=1.0, count=200):
    t = np.linspace(0.0, 2.0 * np.pi * turns, count)
    return np.column_stack([radius * np.cos(t), radius * np.sin(t), pitch * t / (2.0 * np.pi)])


def test_length_and_curvature_of_circular_arc():
    line = Centerline(arc(50.0, np.pi))
    assert line.length == pytest.approx(50.0 * np.pi, rel=1e-3)
    assert np.median(line.curvature) == pytest.approx(1.0 / 50.0, rel=1e-3)


def test_tangents_are_unit_and_tangent_to_curve():
    line = Centerline(arc(50.0, np.pi))
    tangents = line.tangent(line.stations(20))
    assert np.linalg.norm(tangents, axis=1) == pytest.approx(np.ones(20))
    position = line.position(line.length / 2.0)[0]
    assert np.dot(tangents[0], arc(50.0, 0.0, 2)[0] / 50.0) == pytest.approx(0.0, abs=1e-3)
    assert np.linalg.norm(position) == pytest.approx(50.0, rel=1e-4)


def test_input_is_reproduced_without_smoothing():
    points = helix()
    assert Centerline(points, cutoff_length=0.0).deviation_from_input < 0.05


def test_smoothing_removes_noise_but_not_shape():
    points = arc(80.0, np.pi / 2.0, 80)
    rng = np.random.RandomState(0)
    noisy = points + rng.normal(scale=0.3, size=points.shape) * np.array([1.0, 1.0, 0.0])
    raw = Centerline(noisy, cutoff_length=0.0)
    smooth = Centerline(noisy, cutoff_length=30.0)
    assert np.percentile(smooth.curvature, 95) < 0.25 * np.percentile(raw.curvature, 95)
    radii = np.linalg.norm(smooth.xyz[20:-20], axis=1)
    assert np.abs(radii - 80.0).max() < 0.5


def test_frames_are_orthonormal_and_do_not_jump():
    line = Centerline(helix(), cutoff_length=0.0)
    stations = line.stations(120)
    x_axes, y_axes = line.frames(stations)
    tangents = line.tangent(stations)
    assert np.abs(np.sum(x_axes * tangents, axis=1)).max() < 1e-9
    assert np.abs(np.sum(x_axes * y_axes, axis=1)).max() < 1e-9
    assert np.cross(x_axes, y_axes) == pytest.approx(tangents, abs=1e-9)
    assert np.arccos(np.clip(np.sum(x_axes[1:] * x_axes[:-1], axis=1), -1.0, 1.0)).max() < np.radians(10.0)


def test_frames_are_rotation_minimizing():
    line = Centerline(helix(), cutoff_length=0.0)
    stations = line.stations(400)
    x_axes, _ = line.frames(stations)
    tangents = line.tangent(stations)
    twist = np.sum((x_axes[1:] - x_axes[:-1]) * np.cross(tangents[:-1], x_axes[:-1]), axis=1)
    assert np.abs(twist).max() < 1e-3


def test_invalid_centerlines():
    with pytest.raises(GeometryError, match="four distinct"):
        Centerline([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]])
    with pytest.raises(GeometryError):
        Centerline([[0.0, 0.0], [1.0, 1.0]])
    with pytest.raises(GeometryError):
        Centerline(np.array([[0.0, 0.0, np.nan]] * 5))


def test_repeated_points_are_removed():
    points = np.vstack([arc(50.0, 1.0, 10), arc(50.0, 1.0, 10)[-1:]])
    with pytest.warns(GeometryWarning):
        assert Centerline(points).points.shape[0] == 10
