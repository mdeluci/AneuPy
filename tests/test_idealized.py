import json

import numpy as np
import pytest

from aneupy import GeometryError, IdealizedParameters


def test_zero_shift_is_respected():
    parameters = IdealizedParameters(x_shift=0.0, y_shift=0.0)
    assert np.all(parameters.centers()[:, :2] == 0.0)
    assert parameters.beta == 1.0


def test_healthy_aorta_has_constant_radii():
    parameters = IdealizedParameters(radius_nondilated=10.0, radius_dilated=10.0)
    assert np.all(parameters.lumen_radii() == 10.0)
    assert np.all(parameters.wall_inner_radii() == 10.0)
    assert parameters.chi == 1.0


def test_zero_layer_thickness_is_an_error_and_not_replaced():
    with pytest.raises(GeometryError, match="wall_thickness_intima"):
        IdealizedParameters(wall_thickness_intima=0.0)


def test_law_passes_through_the_former_control_sections():
    parameters = IdealizedParameters(length=100.0, radius_nondilated=5.0, radius_dilated=12.0, sac_fraction=0.4)
    assert parameters.sac_weight([30.0, 40.0, 50.0, 60.0, 70.0]) == pytest.approx([0.0, 0.5, 1.0, 0.5, 0.0])
    assert parameters.sac_weight([0.0, 29.9, 70.1, 100.0]).max() < 1e-3


@pytest.mark.parametrize("length", [100.0, 103.0, 217.0])
def test_sections_fall_on_sac_ends_and_midsection(length):
    parameters = IdealizedParameters(length=length, radius_dilated=12.0, x_shift=3.0)
    positions = parameters.axial_positions()
    neck = 0.5 * (length - parameters.aneurysm_length)
    for target in (neck, 0.5 * length, length - neck):
        assert np.abs(positions - target).min() < 1e-9
    assert parameters.wall_inner_radii().max() == pytest.approx(12.0)
    assert np.all(np.diff(positions) <= parameters.section_spacing + 1e-9)


def test_none_parameter_is_an_error():
    with pytest.raises(GeometryError):
        IdealizedParameters(length=None)


def test_descriptors_round_trip():
    parameters = IdealizedParameters.from_descriptors(beta=0.2, gamma=0.625, chi=2.5, neck_diameter=20.0)
    assert parameters.beta == pytest.approx(0.2)
    assert parameters.gamma == pytest.approx(0.625)
    assert parameters.chi == pytest.approx(2.5)
    assert parameters.aneurysm_length == pytest.approx(80.0)
    assert parameters.length == pytest.approx(200.0)
    assert parameters.radius_dilated == pytest.approx(25.0)
    r_value = parameters.radius_dilated - parameters.shift
    r_large = parameters.radius_dilated + parameters.shift
    assert r_value / r_large == pytest.approx(0.2)
    assert r_value + r_large == pytest.approx(50.0)


def test_shift_direction():
    parameters = IdealizedParameters.from_descriptors(0.5, 0.5, 2.0, 20.0, shift_angle=90.0)
    assert parameters.x_shift == pytest.approx(0.0, abs=1e-12)
    assert parameters.y_shift > 0.0


def test_ilt_reduces_only_the_lumen():
    parameters = IdealizedParameters(radius_nondilated=10.0, radius_dilated=25.0, ilt_thickness=5.0)
    assert parameters.lumen_radii().min() == pytest.approx(10.0)
    assert parameters.lumen_radii().max() == pytest.approx(20.0)
    assert parameters.wall_inner_radii().max() == pytest.approx(25.0)


@pytest.mark.parametrize("arguments, message", [
    (dict(radius_nondilated=10.0, radius_dilated=5.0), "not be smaller"),
    (dict(radius_dilated=10.0, x_shift=10.0), "shift"),
    (dict(radius_dilated=10.0, ilt_thickness=10.0), "ilt_thickness"),
    (dict(sac_fraction=1.0), "sac_fraction"),
    (dict(length=-1.0), "length"),
])
def test_invalid_parameters(arguments, message):
    with pytest.raises(GeometryError, match=message):
        IdealizedParameters(**arguments)


@pytest.mark.parametrize("descriptors, message", [
    (dict(beta=0.0, gamma=1.0, chi=2.0), "beta"), (dict(beta=1.5, gamma=1.0, chi=2.0), "beta"),
    (dict(beta=1.0, gamma=1.0, chi=0.5), "chi"), (dict(beta=1.0, gamma=0.0, chi=2.0), "gamma"),
])
def test_invalid_descriptors(descriptors, message):
    with pytest.raises(GeometryError, match=message):
        IdealizedParameters.from_descriptors(neck_diameter=20.0, **descriptors)


def test_json_reading(tmp_path):
    path = tmp_path / "parameters.json"
    path.write_text(json.dumps({"length": 80.0, "x_shift": 0.0}))
    parameters = IdealizedParameters.from_json(str(path), radius_dilated=9.0, x_shift=None)
    assert parameters.length == 80.0 and parameters.x_shift == 0.0 and parameters.radius_dilated == 9.0
    path.write_text(json.dumps({"wall_thickness_ILT": 1.0}))
    with pytest.raises(GeometryError, match="Unknown parameters"):
        IdealizedParameters.from_json(str(path))
