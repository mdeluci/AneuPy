import numpy as np
import pytest

from aneupy import AreaProfile, GeometryError, GeometryWarning, load_area_profile
from aneupy.profiles import read_table, smooth_uniform


def write(tmp_path, text):
    path = tmp_path / "table.txt"
    path.write_text(text)
    return str(path)


def test_read_table_accepts_commas_and_spaces(tmp_path):
    table = read_table(write(tmp_path, "# header\n1,2\n3 4\n\n5, 6 # comment\n"), 2)
    assert table.tolist() == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]


@pytest.mark.parametrize("text, message", [("1,2,3\n", "expected 2 columns"), ("1,a\n", "non-numeric"), ("# x\n", "no data"),
                                           ("1,2\n3,nan\n", "line 2: NaN")])
def test_read_table_reports_problems(tmp_path, text, message):
    with pytest.raises(GeometryError, match=message):
        read_table(write(tmp_path, text), 2)


def test_read_table_reports_missing_file(tmp_path):
    with pytest.raises(GeometryError, match="Cannot read"):
        read_table(str(tmp_path / "missing.txt"), 2)


def test_smoother_half_gain_at_cutoff_and_polynomials():
    spacing = 1.0
    x = np.arange(0.0, 2000.0, spacing)
    signal = np.sin(2.0 * np.pi * x / 40.0)
    middle = slice(500, 1500)
    assert smooth_uniform(signal, spacing, 40.0)[middle].max() == pytest.approx(0.5, abs=0.01)
    assert smooth_uniform(np.sin(2.0 * np.pi * x / 10.0), spacing, 40.0)[middle].max() < 0.01
    short = np.arange(0.0, 200.0)
    quadratic = 0.01 * short ** 2 + short - 3.0
    assert smooth_uniform(quadratic, spacing, 40.0) == pytest.approx(quadratic)


def test_zero_cutoff_returns_input():
    values = np.array([1.0, 2.0, 4.0, 3.0, 9.0])
    assert smooth_uniform(values, 1.0, 0.0).tolist() == values.tolist()


def test_area_profile_validates_and_converts():
    profile = AreaProfile([0.0, 1.0], [np.pi, 4.0 * np.pi])
    assert profile.radius == pytest.approx([1.0, 2.0])
    with pytest.raises(GeometryError, match="positive"):
        AreaProfile([0.0, 1.0], [1.0, -1.0])
    with pytest.raises(GeometryError, match="two points"):
        AreaProfile([0.0], [1.0])


def test_unsorted_and_repeated_positions_warn_and_average():
    with pytest.warns(GeometryWarning):
        profile = AreaProfile([0.0, 2.0, 1.0, 1.0], [1.0, 3.0, 2.0, 4.0])
    assert profile.abscissa.tolist() == [0.0, 1.0, 2.0]
    assert profile.area.tolist() == [1.0, 3.0, 3.0]


def test_mapping_uses_range_and_supports_flip():
    profile = AreaProfile([-50.0, 50.0], [np.pi, 9.0 * np.pi])
    grid, radius = profile.radius_on_arc_length(200.0, spacing=1.0)
    assert grid[0] == 0.0 and grid[-1] == 200.0
    assert radius[0] == pytest.approx(1.0) and radius[-1] == pytest.approx(3.0)
    assert np.interp(100.0, grid, radius) == pytest.approx(2.0)
    _, flipped = profile.radius_on_arc_length(200.0, spacing=1.0, flip=True)
    assert flipped[0] == pytest.approx(3.0) and flipped[-1] == pytest.approx(1.0)


def test_common_range_keeps_relative_alignment():
    profile = AreaProfile([0.0, 50.0], [np.pi, np.pi])
    grid, radius = profile.radius_on_arc_length(100.0, abscissa_range=(0.0, 100.0))
    assert radius[-1] == pytest.approx(1.0)
    assert grid.size == 101


def test_negative_area_names_file_and_row(tmp_path):
    path = write(tmp_path, "0,1\n1,-2\n")
    with pytest.raises(GeometryError, match="table.txt.*row 2"):
        load_area_profile(path, "wall area")


def test_load_example_profile(data_dir):
    profile = load_area_profile(data_dir + "/Lumen_Area2.txt")
    assert profile.radius.min() > 0.0
