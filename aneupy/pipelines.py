"""Reusable building blocks and ready-made model pipelines.

A pipeline is a sequence of plain function calls on a :class:`aneupy.geometry.Domain`:
describe each boundary as a list of :class:`Station`, loft it into a solid with
:func:`add_lofted_solid`, and combine solids with Boolean cuts. The ready-made builders
below follow that pattern and can be copied or replaced. See
``examples/custom_pipeline.py``.

The functions accept any object with the ``Domain`` interface and do not import SALOME.
"""

import collections
import os

import numpy as np

from .centerline import Centerline
from .idealized import IdealizedParameters
from .validation import (
    GeometryError,
    as_finite_array,
    check_nested_radii,
    check_sections_do_not_intersect,
    check_strictly_increasing,
    check_tube_curvature,
)

#: One circular cross-section: centre, radius and local axes (the normal is X x Y).
Station = collections.namedtuple("Station", "center radius x_axis y_axis")

#: Formats written by default by :func:`export_solids`.
DEFAULT_FORMATS = ("step", "stl", "iges")

ImageDerivedStations = collections.namedtuple(
    "ImageDerivedStations", "arc_length centers normals x_axes y_axes wall_radius lumen_radius curvature "
                            "diagnostics")


def stations_from_arrays(centers, radii, x_axes=None, y_axes=None):
    """Return a list of :class:`Station` from arrays.

    Parameters
    ----------
    centers : array_like, shape (n, 3)
        Section centres in mm.
    radii : array_like, shape (n,)
        Section radii in mm.
    x_axes, y_axes : array_like, shape (n, 3), optional
        Local axes in global coordinates. By default they are the global X and Y axes.
    """
    centers = as_finite_array(centers, "centers", shape=(None, 3))
    radii = as_finite_array(radii, "radii", shape=(centers.shape[0],))
    if np.any(radii <= 0.0):
        raise GeometryError("Section radii must be positive")
    count = centers.shape[0]
    x_axes = np.tile([1.0, 0.0, 0.0], (count, 1)) if x_axes is None else np.asarray(x_axes, dtype=float)
    y_axes = np.tile([0.0, 1.0, 0.0], (count, 1)) if y_axes is None else np.asarray(y_axes, dtype=float)
    return [Station(centers[i].tolist(), float(radii[i]), x_axes[i].tolist(), y_axes[i].tolist())
            for i in range(count)]


def add_lofted_solid(domain, name, stations, **shell_options):
    """Add sections, a closed shell and a solid through the given stations.

    Parameters
    ----------
    domain : aneupy.geometry.Domain
        Target domain.
    name : str
        Solid name. Shell and sections use it as a prefix.
    stations : sequence of Station
        Cross-sections in axial order.
    **shell_options
        Options of :class:`aneupy.geometry.Shell`.

    Returns
    -------
    str
        The solid name.
    """
    section_names = []
    for index, station in enumerate(stations):
        section_name = "{}_section_{}".format(name, index)
        domain.add_section(name=section_name, origin=station.center, x_axis=station.x_axis, y_axis=station.y_axis)
        domain.sections[section_name].add_circle(radius=station.radius)
        section_names.append(section_name)
    shell_name = "{}_shell".format(name)
    domain.add_shell(name=shell_name, sections=section_names, **shell_options)
    domain.add_solid_from_shell(name=name, shell=shell_name)
    return name


def add_layered_solids(domain, inner_name, inner_stations, layers, **shell_options):
    """Build an inner solid and the concentric layers around it.

    Parameters
    ----------
    domain : aneupy.geometry.Domain
        Target domain.
    inner_name : str
        Name of the solid inside the first layer, for example the fluid domain.
    inner_stations : sequence of Station
        Cross-sections of the inner solid.
    layers : sequence of tuple
        ``(layer_name, outer_stations)`` from the inside outwards. Each layer is the solid
        between its outer stations and the previous boundary.
    **shell_options
        Options of :class:`aneupy.geometry.Shell`.

    Returns
    -------
    list of str
        Names of the inner solid and of every layer, from the inside outwards.
    """
    add_lofted_solid(domain, inner_name, inner_stations, **shell_options)
    names = [inner_name]
    previous = inner_name
    for layer_name, outer_stations in layers:
        boundary = "{}_outer".format(layer_name)
        add_lofted_solid(domain, boundary, outer_stations, **shell_options)
        domain.add_solid_from_cut(name=layer_name, solids=[boundary, previous])
        names.append(layer_name)
        previous = boundary
    return names


def build_idealized_model(domain, parameters, **shell_options):
    """Build the fluid domain and the wall layers of an idealized aneurysm.

    Parameters
    ----------
    domain : aneupy.geometry.Domain
        Target domain.
    parameters : IdealizedParameters
        Model parameters.
    **shell_options
        Options of :class:`aneupy.geometry.Shell`.

    Returns
    -------
    list of str
        ``aneurysm_fluid``, ``aneurysm_intima_ILT``, ``media_solid`` and ``adventitia_solid``.
        The intima and any thrombus form one solid.
    """
    if not isinstance(parameters, IdealizedParameters):
        raise GeometryError("parameters must be an IdealizedParameters instance")
    centers = parameters.centers()
    check_strictly_increasing(centers[:, 2], "axial positions")
    wall = parameters.wall_inner_radii()
    outer_intima = wall + parameters.wall_thickness_intima
    outer_media = outer_intima + parameters.wall_thickness_media
    outer_adventitia = outer_media + parameters.wall_thickness_adventitia
    lumen = parameters.lumen_radii()
    check_nested_radii(lumen, outer_intima, "lumen", "intima")
    layers = [("aneurysm_intima_ILT", stations_from_arrays(centers, outer_intima)),
              ("media_solid", stations_from_arrays(centers, outer_media)),
              ("adventitia_solid", stations_from_arrays(centers, outer_adventitia))]
    return add_layered_solids(domain, "aneurysm_fluid", stations_from_arrays(centers, lumen), layers,
                              **shell_options)


def prepare_image_derived_stations(centerline_points, wall_profile, lumen_profile, n_sections=None,
                                   centerline_cutoff=30.0, profile_cutoff=30.0, normal_mode="tangent",
                                   flip_profiles=False):
    """Compute and check the cross-sections of an image-derived parametric model.

    The steps are: smooth the centerline, map both area profiles onto its arc length,
    smooth them, sample all quantities at uniformly spaced stations, and check the limits.

    Parameters
    ----------
    centerline_points : array_like, shape (n, 3)
        Centerline points in mm.
    wall_profile, lumen_profile : aneupy.profiles.AreaProfile
        Area enclosed by the outer wall and by the lumen. Both are mapped with their
        common abscissa range.
    n_sections : int, optional
        Number of stations. By default, one every 5 mm of centerline, and at least 12.
    centerline_cutoff, profile_cutoff : float, optional
        Half-gain wavelengths of the smoothers in mm. Zero disables smoothing.
    normal_mode : {"tangent", "z"}, optional
        Section normals follow the centerline tangent or the global Z axis.
    flip_profiles : bool, optional
        If true, the first abscissa corresponds to the last centerline point.

    Returns
    -------
    ImageDerivedStations
        Arrays at the stations and a dictionary of diagnostics.

    Raises
    ------
    GeometryError
        If the input violates a limit of the method.
    """
    if normal_mode not in ("tangent", "z"):
        raise GeometryError("normal_mode must be 'tangent' or 'z', got '{}'".format(normal_mode))
    centerline = Centerline(centerline_points, cutoff_length=centerline_cutoff)
    if n_sections is None:
        n_sections = max(12, int(round(centerline.length / 5.0)) + 1)
    if int(n_sections) < 4:
        raise GeometryError("At least four sections are needed")
    arc_length = centerline.stations(n_sections)
    first = min(wall_profile.abscissa_range[0], lumen_profile.abscissa_range[0])
    last = max(wall_profile.abscissa_range[1], lumen_profile.abscissa_range[1])
    arguments = dict(length=centerline.length, cutoff_length=profile_cutoff, flip=flip_profiles,
                     abscissa_range=(first, last))
    grid, wall_values = wall_profile.radius_on_arc_length(**arguments)
    _, lumen_values = lumen_profile.radius_on_arc_length(**arguments)
    wall_radius = np.interp(arc_length, grid, wall_values)
    lumen_radius = np.interp(arc_length, grid, lumen_values)
    thickness = check_nested_radii(lumen_radius, wall_radius, "lumen", "outer wall")
    centers = centerline.position(arc_length)
    curvature = centerline.curvature_at(arc_length)
    if normal_mode == "tangent":
        normals = centerline.tangent(arc_length)
        x_axes, y_axes = centerline.frames(arc_length)
        curvature_ratio = check_tube_curvature(centerline.curvature, np.interp(
            centerline.arc_length, grid, wall_values), "outer wall")
        check_sections_do_not_intersect(centers, normals, wall_radius, "Outer wall")
    else:
        steps = np.diff(centers[:, 2])
        if not (np.all(steps > 0.0) or np.all(steps < 0.0)):
            raise GeometryError("With normal_mode='z' the centerline must be monotonic in Z")
        normals = np.tile([0.0, 0.0, 1.0], (centers.shape[0], 1))
        x_axes = np.tile([1.0, 0.0, 0.0], (centers.shape[0], 1))
        y_axes = np.tile([0.0, 1.0, 0.0], (centers.shape[0], 1))
        curvature_ratio = None
    diagnostics = {
        "centerline_length_mm": centerline.length,
        "centerline_deviation_mm": centerline.deviation_from_input,
        "n_sections": int(n_sections),
        "section_spacing_mm": centerline.length / (int(n_sections) - 1),
        "max_wall_diameter_mm": 2.0 * float(wall_values.max()),
        "min_wall_lumen_thickness_mm": thickness,
        "max_curvature_times_radius": curvature_ratio,
    }
    return ImageDerivedStations(arc_length, centers, normals, x_axes, y_axes, wall_radius, lumen_radius,
                                curvature, diagnostics)


def build_image_derived_model(domain, stations, **shell_options):
    """Build the lumen and the combined wall and thrombus solids.

    Parameters
    ----------
    domain : aneupy.geometry.Domain
        Target domain.
    stations : ImageDerivedStations
        Result of :func:`prepare_image_derived_stations`.
    **shell_options
        Options of :class:`aneupy.geometry.Shell`.

    Returns
    -------
    list of str
        ``lumen`` and ``wall_ilt``. Area profiles do not separate wall from thrombus, so
        ``wall_ilt`` holds both.
    """
    lumen = stations_from_arrays(stations.centers, stations.lumen_radius, stations.x_axes, stations.y_axes)
    wall = stations_from_arrays(stations.centers, stations.wall_radius, stations.x_axes, stations.y_axes)
    return add_layered_solids(domain, "lumen", lumen, [("wall_ilt", wall)], **shell_options)


def export_solids(domain, names, directory, formats=DEFAULT_FORMATS):
    """Export solids to a directory, one file per solid and format.

    Parameters
    ----------
    domain : aneupy.geometry.Domain
        Domain that holds the solids.
    names : sequence of str
        Solid names.
    directory : str
        Output directory, created if needed.
    formats : sequence of str, optional
        Any of ``step``, ``iges``, ``brep``, ``stl`` and ``vtk``.

    Returns
    -------
    list of str
        Paths of the written files.
    """
    if not os.path.isdir(directory):
        os.makedirs(directory)
    written = []
    for file_format in formats:
        exporter = getattr(domain, "export_{}".format(str(file_format).lower()), None)
        if exporter is None:
            raise GeometryError("Unsupported export format '{}'".format(file_format))
        for name in names:
            path = os.path.join(directory, "{}.{}".format(name, str(file_format).lower()))
            exporter(solid=name, file=path)
            written.append(path)
    return written
