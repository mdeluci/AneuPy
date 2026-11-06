import json
import os
import runpy
import sys
import warnings

import numpy as np
import pytest

from aneupy import GeometryError, IdealizedParameters, add_lofted_solid, build_idealized_model, export_solids
from aneupy.pipelines import stations_from_arrays


def builder(geometry):
    return geometry.geomBuilder.New()


def volume(geometry, domain, name):
    return domain.solid_volume(name)


def surface_points(shape, count=40):
    from OCP.BRep import BRep_Tool
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    best, best_area = None, -1.0
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        properties = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, properties)
        if properties.Mass() > best_area:
            best, best_area = BRep_Tool.Surface_s(face), properties.Mass()
        explorer.Next()
    return best


def test_healthy_cylinder_has_the_analytic_volumes(geometry):
    domain = geometry.Domain()
    parameters = IdealizedParameters(length=100.0, radius_nondilated=10.0, radius_dilated=10.0)
    names = build_idealized_model(domain, parameters)
    assert names == ["aneurysm_fluid", "aneurysm_intima_ILT", "media_solid", "adventitia_solid"]
    assert volume(geometry, domain, "aneurysm_fluid") == pytest.approx(np.pi * 100.0 * 100.0, rel=1e-5)
    assert volume(geometry, domain, "aneurysm_intima_ILT") == pytest.approx(np.pi * 100.0 * (10.5 ** 2 - 100.0), rel=1e-4)
    assert volume(geometry, domain, "media_solid") == pytest.approx(np.pi * 100.0 * (10.8 ** 2 - 10.5 ** 2), rel=1e-4)
    assert volume(geometry, domain, "adventitia_solid") == pytest.approx(np.pi * 100.0 * (11.5 ** 2 - 10.8 ** 2), rel=1e-4)


@pytest.mark.parametrize("beta", [1.0, 0.2])
def test_fusiform_and_saccular_match_the_prescribed_law(geometry, beta):
    parameters = IdealizedParameters.from_descriptors(beta=beta, gamma=0.625, chi=2.5, neck_diameter=20.0)
    domain = geometry.Domain()
    build_idealized_model(domain, parameters)
    fine = np.linspace(0.0, parameters.length, 4001)
    weight = parameters.sac_weight(fine)
    radius = parameters.radius_nondilated + weight * (parameters.radius_dilated - parameters.radius_nondilated)
    expected = float(np.sum(0.5 * (radius[1:] ** 2 + radius[:-1] ** 2) * np.diff(fine)) * np.pi)
    assert domain.solid_volume("aneurysm_fluid") == pytest.approx(expected, rel=2e-3)


def test_circle_seam_lies_on_local_x_and_plane_on_local_xy(geometry):
    from OCP.BRep import BRep_Tool
    from OCP.TopoDS import TopoDS

    domain = geometry.Domain()
    x_axis = np.array([0.0, 1.0, 0.0])
    y_axis = np.array([0.0, 0.0, 1.0])
    domain.add_section("s", origin=[1.0, 2.0, 3.0], x_axis=x_axis, y_axis=y_axis)
    domain.sections["s"].add_circle(2.0)
    edge = TopoDS.Edge_s(domain.sections["s"].bases["edge"].shape)
    curve = BRep_Tool.Curve_s(edge, 0.0, 0.0)
    first, _ = BRep_Tool.Range_s(edge)
    point = curve.Value(first)
    assert [point.X(), point.Y(), point.Z()] == pytest.approx([1.0, 4.0, 3.0], abs=1e-7)
    quarter = curve.Value(first + np.pi / 2.0)
    assert [quarter.X(), quarter.Y(), quarter.Z()] == pytest.approx([1.0, 2.0, 5.0], abs=1e-7)


def test_section_rotation_keeps_geometry_consistent(geometry):
    domain = geometry.Domain()
    domain.add_section("s", origin=[0.0, 0.0, 5.0])
    section = domain.sections["s"]
    section.add_circle(1.0)
    section.rotate_x(90.0)
    assert section.z_axis == pytest.approx([0.0, -1.0, 0.0], abs=1e-9)
    assert section.origin == [0.0, 0.0, 5.0]
    section.rotate_x(-90.0)
    assert section.z_axis == pytest.approx([0.0, 0.0, 1.0], abs=1e-9)


def test_invalid_entities_give_clear_errors(geometry):
    domain = geometry.Domain()
    domain.add_section("a", origin=[0.0, 0.0, 0.0])
    with pytest.raises(GeometryError, match="already exists"):
        domain.add_section("a", origin=[0.0, 0.0, 1.0])
    with pytest.raises(GeometryError, match="origin"):
        domain.add_section("b", origin=[0.0, 0.0])
    with pytest.raises(GeometryError, match="parallel"):
        domain.add_section("c", origin=[0.0, 0.0, 0.0], x_axis=[1.0, 0.0, 0.0], y_axis=[2.0, 0.0, 0.0])
    with pytest.raises(GeometryError, match="radius"):
        domain.sections["a"].add_circle(-1.0)
    with pytest.raises(GeometryError, match="Unknown section 'z'"):
        domain.add_shell("s", sections=["a", "z"])
    with pytest.raises(GeometryError, match="no circle"):
        domain.add_shell("s", sections=["a", "a"])
    with pytest.raises(GeometryError, match="Unknown solid"):
        domain.export_stl("missing", "x.stl")
    with pytest.raises(GeometryError, match="exactly two"):
        domain.add_solid_from_cut("x", ["a"])


def test_exports_carry_physical_size(geometry, tmp_path):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.STEPControl import STEPControl_Reader

    domain = geometry.Domain()
    parameters = IdealizedParameters(length=100.0, radius_nondilated=10.0, radius_dilated=10.0)
    names = build_idealized_model(domain, parameters)
    written = export_solids(domain, names[:1], str(tmp_path), formats=("step", "iges", "brep", "stl"))
    assert sorted(os.path.basename(path) for path in written) == [
        "aneurysm_fluid.brep", "aneurysm_fluid.iges", "aneurysm_fluid.step", "aneurysm_fluid.stl"]
    step = tmp_path / "aneurysm_fluid.step"
    assert "SI_UNIT(.MILLI.,.METRE.)" in step.read_text()
    reader = STEPControl_Reader()
    reader.ReadFile(str(step))
    reader.TransferRoots()
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(reader.OneShape(), properties)
    assert abs(properties.Mass()) == pytest.approx(np.pi * 100.0 * 100.0, rel=1e-4)


def test_unknown_export_format(geometry, tmp_path):
    domain = geometry.Domain()
    with pytest.raises(GeometryError, match="Unsupported"):
        export_solids(domain, ["x"], str(tmp_path), formats=("obj",))


def test_save_writes_study_summary(geometry, tmp_path):
    domain = geometry.Domain()
    build_idealized_model(domain, IdealizedParameters(length=60.0, radius_nondilated=5.0, radius_dilated=9.0))
    domain.save(str(tmp_path / "study.hdf"))
    summary = json.loads((tmp_path / "study.cad").read_text())
    assert summary["solids"]["aneurysm_fluid"]["Volume"] > 0.0
    assert not (tmp_path / "study.hdf.cad").exists()


def test_failed_surface_is_detected(geometry, monkeypatch):
    domain = geometry.Domain()
    monkeypatch.setattr(domain, "solid_volume", lambda name: 1.0e9)
    centers = np.column_stack([np.zeros(5), np.zeros(5), np.linspace(0.0, 40.0, 5)])
    with pytest.raises(GeometryError, match="surface fit"):
        add_lofted_solid(domain, "x", stations_from_arrays(centers, np.full(5, 5.0)))


def test_manual_sections_out_of_order_are_rejected(geometry):
    domain = geometry.Domain()
    for name, axial in (("a", 0.0), ("b", 50.0), ("c", 20.0), ("d", 70.0)):
        domain.add_section(name, origin=[0.0, 0.0, axial])
        domain.sections[name].add_circle(5.0)
    with pytest.raises(GeometryError, match="monotonically"):
        domain.add_shell("s", sections=["a", "b", "c", "d"])


def test_manual_crossing_sections_are_rejected(geometry):
    domain = geometry.Domain()
    domain.add_section("a", origin=[0.0, 0.0, 0.0])
    domain.add_section("b", origin=[0.0, 0.0, 5.0], x_axis=[1.0, 0.0, 1.0], y_axis=[0.0, 1.0, 0.0])
    domain.sections["a"].add_circle(20.0)
    domain.sections["b"].add_circle(20.0)
    with pytest.raises(GeometryError, match="intersect"):
        domain.add_shell("s", sections=["a", "b"])


def test_cut_of_enclosing_solid_is_rejected(geometry):
    domain = geometry.Domain()
    centers = np.column_stack([np.zeros(6), np.zeros(6), np.linspace(0.0, 50.0, 6)])
    add_lofted_solid(domain, "inner", stations_from_arrays(centers, np.full(6, 5.0)))
    add_lofted_solid(domain, "outer", stations_from_arrays(centers, np.full(6, 8.0)))
    with pytest.raises(GeometryError, match="no material"):
        domain.add_solid_from_cut("wrong", ["inner", "outer"])


def test_z_mode_builds_on_descending_centerline(geometry, data_dir):
    from aneupy import build_image_derived_model, load_area_profile, prepare_image_derived_stations
    from aneupy.profiles import read_table

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stations = prepare_image_derived_stations(
            read_table(data_dir + "/centerline1.txt", 3), load_area_profile(data_dir + "/Wall_Area.txt"),
            load_area_profile(data_dir + "/Lumen_Area.txt"), normal_mode="z", flip_profiles=True)
        domain = geometry.Domain()
        assert build_image_derived_model(domain, stations) == ["lumen", "wall_ilt"]
    assert domain.solid_volume("wall_ilt") > 0.0


def test_filling_method_remains_available(geometry):
    domain = geometry.Domain()
    centers = np.column_stack([np.zeros(40), np.zeros(40), np.linspace(0.0, 195.0, 40)])
    add_lofted_solid(domain, "x", stations_from_arrays(centers, np.full(40, 10.0)), method="filling")
    assert domain.solid_volume("x") == pytest.approx(np.pi * 100.0 * 195.0, rel=1e-3)
    with pytest.raises(GeometryError, match="Unknown surface method"):
        add_lofted_solid(geometry.Domain(), "y", stations_from_arrays(centers, np.full(40, 10.0)), method="other")


def test_midsection_diameter_is_exact_on_the_built_surface(geometry):
    parameters = IdealizedParameters(length=103.0, radius_nondilated=5.0, radius_dilated=12.0, x_shift=4.0)
    domain = geometry.Domain()
    build_idealized_model(domain, parameters)
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(domain.solids["aneurysm_fluid"].geom.shape, box, False, False)
    xmin, ymin, _, xmax, ymax, _ = box.Get()
    assert ymax - ymin == pytest.approx(24.0, abs=1e-3)
    assert xmax == pytest.approx(16.0, abs=1e-3)


def test_nonplanar_centerline_has_no_twist(geometry):
    from aneupy import Centerline

    t = np.linspace(0.0, 2.0 * np.pi, 120)
    points = np.column_stack([60.0 * np.cos(t), 60.0 * np.sin(t), 40.0 * t])
    line = Centerline(points)
    stations = line.stations(60)
    x_axes, y_axes = line.frames(stations)
    domain = geometry.Domain()
    add_lofted_solid(domain, "tube", stations_from_arrays(line.position(stations), np.full(60, 8.0), x_axes, y_axes))
    assert domain.solid_volume("tube") == pytest.approx(np.pi * 64.0 * line.length, rel=5e-3)


@pytest.mark.parametrize("script, arguments", [
    ("idealized_manual.py", []), ("idealized_automatic.py", []), ("image_derived.py", []),
    ("image_derived.py", ["params_image_derived_2.json"]), ("custom_pipeline.py", []),
])
def test_examples_run(geometry, tmp_path, monkeypatch, script, arguments):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    examples = os.path.join(root, "examples")
    monkeypatch.setenv("ANEUPY_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", [script] + [os.path.join(examples, item) for item in arguments])
    runpy.run_path(os.path.join(examples, script), run_name="__main__")
    assert any(name.endswith(".step") for _, _, files in os.walk(str(tmp_path)) for name in files)


def test_entry_script_and_null_parameter(geometry, tmp_path, monkeypatch, capsys):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = tmp_path / "bad.json"
    config.write_text(json.dumps({"length": None}))
    monkeypatch.setattr(sys, "argv", ["aneupy_cli.py", "idealized", "--config", str(config),
                                      "--output-dir", str(tmp_path / "o")])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(os.path.join(root, "examples", "aneupy_cli.py"), run_name="__main__")
    assert stop.value.code == 2
    assert "error" in capsys.readouterr().err


def test_command_line(geometry, tmp_path, capsys):
    from aneupy.cli import main

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    examples = os.path.join(root, "examples")
    assert main(["idealized", "--config", os.path.join(examples, "params_idealized_automatic.json"), "--x_shift", "0",
                 "--output-dir", str(tmp_path / "a"), "--formats", "step"]) == 0
    assert json.loads((tmp_path / "a" / "diagnostics.json").read_text())["x_shift"] == 0.0
    assert main(["image-derived", "--config", os.path.join(examples, "params_image_derived_1.json"),
                 "--output-dir", str(tmp_path / "b"), "--formats", "stl"]) == 0
    assert (tmp_path / "b" / "wall_ilt.stl").exists()
    assert main(["idealized", "--radius_dilated", "1", "--radius_nondilated", "5", "--output-dir", str(tmp_path / "c")]) == 2
    assert "error" in capsys.readouterr().err
