import warnings

import numpy as np
import pytest

from aneupy import AreaProfile, GeometryError, prepare_image_derived_stations


def straight_line(length=200.0, count=41):
    return np.column_stack([np.zeros(count), np.zeros(count), np.linspace(0.0, length, count)])


def inclined_line(length=200.0, count=41):
    """Straight line at 60 degrees from Z: arc length and Z differ by a factor of 2."""
    s = np.linspace(0.0, length, count)
    return np.column_stack([s * np.sin(np.pi / 3.0), np.zeros(count), s * np.cos(np.pi / 3.0)])


def profile(radius_function, count=101, name="p"):
    x = np.linspace(-50.0, 50.0, count)
    return AreaProfile(x, np.pi * radius_function((x + 50.0) / 100.0) ** 2, name=name)


def bump(u):
    return 10.0 + 8.0 * np.sin(np.pi * u) ** 2


def test_radius_follows_arc_length_and_not_global_z():
    """Regression test: radii used to be looked up with the Z coordinate of each section."""
    wall = profile(lambda u: bump(u) + 2.0)
    lumen = profile(bump)
    result = prepare_image_derived_stations(inclined_line(), wall, lumen, centerline_cutoff=0.0, profile_cutoff=0.0)
    u = result.arc_length / result.arc_length[-1]
    assert result.lumen_radius == pytest.approx(bump(u), abs=0.02)
    assert result.wall_radius == pytest.approx(bump(u) + 2.0, abs=0.02)


def test_whole_profile_is_used():
    wall = profile(lambda u: 12.0 + 4.0 * u)
    lumen = profile(lambda u: 10.0 + 4.0 * u)
    result = prepare_image_derived_stations(inclined_line(), wall, lumen, centerline_cutoff=0.0, profile_cutoff=0.0)
    assert result.wall_radius[0] == pytest.approx(12.0, abs=1e-6)
    assert result.wall_radius[-1] == pytest.approx(16.0, abs=1e-6)


def test_flip_reverses_the_profile():
    wall = profile(lambda u: 12.0 + 4.0 * u)
    lumen = profile(lambda u: 10.0 + 4.0 * u)
    result = prepare_image_derived_stations(straight_line(), wall, lumen, centerline_cutoff=0.0, profile_cutoff=0.0,
                                            flip_profiles=True)
    assert result.wall_radius[0] == pytest.approx(16.0, abs=1e-6)


def test_smoothing_removes_ripple_and_keeps_the_shape():
    rng = np.random.RandomState(1)
    noise = rng.normal(scale=0.4, size=101)
    x = np.linspace(-50.0, 50.0, 101)
    u = (x + 50.0) / 100.0
    wall = AreaProfile(x, np.pi * (bump(u) + 3.0 + noise) ** 2)
    lumen = AreaProfile(x, np.pi * (bump(u) + noise) ** 2)
    raw = prepare_image_derived_stations(straight_line(), wall, lumen, profile_cutoff=0.0)
    smooth = prepare_image_derived_stations(straight_line(), wall, lumen, profile_cutoff=30.0)
    assert np.abs(np.diff(smooth.wall_radius, n=2)).max() < 0.25 * np.abs(np.diff(raw.wall_radius, n=2)).max()
    assert np.abs(smooth.wall_radius.max() - (bump(0.5) + 3.0)) < 1.0


def test_same_filter_is_applied_to_wall_and_lumen():
    wall = profile(lambda u: bump(u) + 5.0)
    lumen = profile(bump)
    result = prepare_image_derived_stations(straight_line(), wall, lumen, profile_cutoff=30.0)
    assert result.wall_radius - result.lumen_radius == pytest.approx(np.full(result.wall_radius.size, 5.0), abs=1e-6)


def test_crossing_boundaries_are_rejected():
    wall = profile(lambda u: 10.0 + 0.0 * u)
    lumen = profile(lambda u: 9.0 + 2.0 * u)
    with pytest.raises(GeometryError, match="outer wall radius must exceed lumen"):
        prepare_image_derived_stations(straight_line(), wall, lumen, centerline_cutoff=0.0, profile_cutoff=0.0)


def test_tight_bend_is_rejected():
    t = np.linspace(0.0, np.pi, 60)
    arch = np.column_stack([30.0 * np.cos(t), np.zeros(60), 30.0 * np.sin(t)])
    wall = profile(lambda u: 33.0 + 0.0 * u)
    lumen = profile(lambda u: 20.0 + 0.0 * u)
    with pytest.raises(GeometryError, match="too curved"):
        prepare_image_derived_stations(arch, wall, lumen, centerline_cutoff=0.0, profile_cutoff=0.0)


def test_moderate_arch_is_accepted():
    t = np.linspace(0.0, np.pi, 60)
    arch = np.column_stack([60.0 * np.cos(t), np.zeros(60), 60.0 * np.sin(t)])
    wall = profile(lambda u: 15.0 + 0.0 * u)
    lumen = profile(lambda u: 12.0 + 0.0 * u)
    result = prepare_image_derived_stations(arch, wall, lumen, centerline_cutoff=0.0, profile_cutoff=0.0)
    assert result.diagnostics["max_curvature_times_radius"] == pytest.approx(0.25, abs=0.01)


def test_z_mode_requires_monotonic_centerline():
    t = np.linspace(0.0, np.pi, 40)
    arch = np.column_stack([60.0 * np.cos(t), np.zeros(40), 60.0 * np.sin(t)])
    wall = profile(lambda u: 15.0 + 0.0 * u)
    lumen = profile(lambda u: 12.0 + 0.0 * u)
    with pytest.raises(GeometryError, match="monotonic"):
        prepare_image_derived_stations(arch, wall, lumen, normal_mode="z", centerline_cutoff=0.0, profile_cutoff=0.0)
    with pytest.raises(GeometryError, match="normal_mode"):
        prepare_image_derived_stations(arch, wall, lumen, normal_mode="other")


def test_z_mode_uses_horizontal_sections():
    wall = profile(lambda u: 15.0 + 0.0 * u)
    lumen = profile(lambda u: 12.0 + 0.0 * u)
    result = prepare_image_derived_stations(straight_line()[::-1], wall, lumen, normal_mode="z",
                                            centerline_cutoff=0.0, profile_cutoff=0.0)
    assert np.all(result.normals == [0.0, 0.0, 1.0])
    assert result.diagnostics["max_curvature_times_radius"] is None


@pytest.mark.parametrize("names, flip", [
    (("centerline1.txt", "Wall_Area.txt", "Lumen_Area.txt"), True),
    (("centerline2.txt", "Wall_Area2.txt", "Lumen_Area2.txt"), False),
])
def test_example_data_are_admissible(data_dir, names, flip):
    from aneupy import load_area_profile
    from aneupy.profiles import read_table

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wall = load_area_profile(data_dir + "/" + names[1])
        lumen = load_area_profile(data_dir + "/" + names[2])
    result = prepare_image_derived_stations(read_table(data_dir + "/" + names[0], 3), wall, lumen, flip_profiles=flip)
    assert result.diagnostics["max_curvature_times_radius"] < 0.8
    assert result.diagnostics["min_wall_lumen_thickness_mm"] > 1.0
    assert result.diagnostics["centerline_deviation_mm"] < 1.0
