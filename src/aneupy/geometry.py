"""SALOME layer: sections, shells and solids built with the GEOM module.

This is the only module that imports SALOME. Run it inside a SALOME environment, for
example with ``salome shell -- python3 script.py``.

Conventions
-----------
Lengths are in millimetres. A section is defined in the XY plane of its local coordinate
system (LCS), given by an origin and by local X and Y axes in global coordinates; its
normal is the local Z axis. The seam of a circle lies on the local X axis. Geometric
tolerances are in model units.
"""

import json
import math
import os

try:
    # Layout of recent SALOME versions.
    from salome.kernel import GEOM, salome
except ImportError:
    # Layout of SALOME 9.11.
    import GEOM
    import salome
from salome.geom import geomBuilder

from .transforms import axis_angle_from_axes, orthonormal_axes
from .validation import (
    GeometryError,
    as_vector3,
    check_cut_volume,
    check_loft_volume,
    check_sections_do_not_intersect,
    expected_loft_volume,
    require_positive,
)

#: Size of one model unit in metres. Exports use it because SALOME treats model units as metres.
MODEL_UNIT_IN_METRES = 1.0e-3


def _refresh_object_browser():
    """Refresh the SALOME object browser when a GUI session is available."""
    gui = getattr(salome, "sg", None)
    refresh = getattr(gui, "updateObjBrowser", None)
    if refresh is not None:
        refresh()


class Domain:
    """Container and factory of the sections, shells and solids of one model.

    Creating a domain initializes the SALOME study and the GEOM module.

    Attributes
    ----------
    sections, shells, solids : dict
        Created entities by name.
    """

    def __init__(self):
        self.sections = {}
        self.shells = {}
        self.solids = {}
        self.info = {}
        salome.salome_init()
        self.study = salome.myStudy
        self.geompy = geomBuilder.New()
        self.geompy.addToStudyAuto(0)

    def add_section(self, name, origin, x_axis=None, y_axis=None, folder=True):
        """Add a :class:`Section`. See that class for the arguments."""
        self._require_new(name, self.sections, "section")
        self.sections[name] = Section(name, origin, x_axis=x_axis, y_axis=y_axis, folder=folder)

    def add_shell(self, name, sections, **options):
        """Add a :class:`Shell` through the named sections, in the given order.

        Parameters
        ----------
        name : str
            Shell name.
        sections : sequence of str
            Names of existing sections.
        **options
            Options of :class:`Shell`.
        """
        self._require_new(name, self.shells, "shell")
        self.shells[name] = Shell(name, [self._get(self.sections, section, "section") for section in sections],
                                  **options)

    def add_solid_from_shell(self, name, shell, folder=False):
        """Add a solid bounded by the named closed shell, and check its volume against its sections."""
        self._require_new(name, self.solids, "solid")
        source = self._get(self.shells, shell, "shell")
        self.solids[name] = Solid(name, self.geompy.MakeSolid([source.geom]), folder=folder)
        check_loft_volume(self.solid_volume(name), source.expected_volume, name)

    def add_solid_from_cut(self, name, solids, folder=False):
        """Add the Boolean difference ``solids[0] - solids[1]``, and check that material remains."""
        self._require_new(name, self.solids, "solid")
        if len(solids) != 2:
            raise GeometryError("A cut needs exactly two solids, got {}".format(len(solids)))
        first = self._get(self.solids, solids[0], "solid").geom
        second = self._get(self.solids, solids[1], "solid").geom
        self.solids[name] = Solid(name, self.geompy.MakeCut(first, second, checkSelfInte=True), folder=folder)
        check_cut_volume(self.solid_volume(name), self.solid_volume(solids[0]), self.solid_volume(solids[1]), name)

    def solid_volume(self, name):
        """Return the volume of a solid in cubic millimetres."""
        return abs(self.geompy.BasicProperties(self._get(self.solids, name, "solid").geom)[2])

    def export_iges(self, solid, file):
        """Export a solid to IGES 5.3 with its physical size (SALOME writes metres)."""
        self.geompy.ExportIGES(self._in_metres(solid), os.path.abspath(file), theVersion="5.3")

    def export_step(self, solid, file):
        """Export a solid to STEP in millimetres with its physical size."""
        self.geompy.ExportSTEP(self._in_metres(solid), os.path.abspath(file), GEOM.LU_MILLIMETER)

    def export_brep(self, solid, file):
        """Export a solid to BREP. BREP stores plain model units (millimetres)."""
        self.geompy.ExportBREP(self._get(self.solids, solid, "solid").geom, os.path.abspath(file))

    def export_stl(self, solid, file, deflection=1.0e-4, relative=True, ascii_format=False):
        """Export a solid to STL. STL stores plain model units (millimetres).

        Parameters
        ----------
        solid : str
            Solid name.
        file : str
            Output path.
        deflection : float, optional
            Maximum chordal deviation of the facets.
        relative : bool, optional
            If true, ``deflection`` is relative to the size of the shape.
        ascii_format : bool, optional
            If true, write ASCII instead of binary.
        """
        self.geompy.ExportSTL(self._get(self.solids, solid, "solid").geom, os.path.abspath(file), ascii_format,
                              deflection, relative)

    def export_vtk(self, solid, file, deflection=1.0e-3):
        """Export a triangulated solid to VTK. VTK stores plain model units (millimetres)."""
        self.geompy.ExportVTK(self._get(self.solids, solid, "solid").geom, os.path.abspath(file), deflection)

    def save(self, file):
        """Save the SALOME study and a JSON summary of the entities.

        Parameters
        ----------
        file : str
            Path of the ``.hdf`` study file. The summary uses the same path with the
            extension ``.cad``.
        """
        file = os.path.abspath(file)
        stem = file[:-4] if file.endswith(".hdf") else file
        # Arguments of SaveAs: path, multi-file flag, ASCII flag.
        self.study.SaveAs(stem + ".hdf", False, False)
        self._get_cad_info()
        with open(stem + ".cad", "w") as output_file:
            json.dump(self.info, output_file, indent=2, sort_keys=True)

    def _in_metres(self, solid):
        """Return a copy of the solid scaled from millimetres to metres."""
        geometry = self._get(self.solids, solid, "solid").geom
        return self.geompy.MakeScaleTransform(geometry, None, MODEL_UNIT_IN_METRES)

    def _get_cad_info(self):
        """Collect length, area, volume, inertia and centre of gravity of each entity."""
        self.info = {"sections": {}, "shells": {}, "solids": {}}
        for kind, entities in (("sections", self.sections), ("shells", self.shells), ("solids", self.solids)):
            for name, entity in entities.items():
                if entity.geom is None:
                    continue
                length, area, volume = self.geompy.BasicProperties(entity.geom)[:3]
                inertia = self.geompy.Inertia(entity.geom)
                labels = ("I11", "I12", "I13", "I21", "I22", "I23", "I31", "I32", "I33", "Ix", "Iy", "Iz")
                record = dict(zip(labels, inertia))
                record.update(Length=length, Area=area, Volume=volume,
                              CDG=self.geompy.PointCoordinates(self.geompy.MakeCDG(entity.geom)))
                self.info[kind][name] = record

    @staticmethod
    def _require_new(name, entities, kind):
        """Raise :class:`GeometryError` if ``name`` is already used."""
        if name in entities:
            raise GeometryError("A {} named '{}' already exists".format(kind, name))

    @staticmethod
    def _get(entities, name, kind):
        """Return an entity by name, or raise :class:`GeometryError` listing valid names."""
        try:
            return entities[name]
        except KeyError:
            raise GeometryError("Unknown {} '{}'. Available: {}".format(kind, name, sorted(entities)))


class Section:
    """A planar cross-section in its local coordinate system.

    Parameters
    ----------
    name : str
        Section name.
    origin : sequence of float
        LCS origin in global coordinates, in mm.
    x_axis, y_axis : sequence of float, optional
        Local X and Y directions in global coordinates. By default, the global axes.
        ``y_axis`` is orthogonalized against ``x_axis``.
    folder : bool, optional
        If true, group the entities in a folder of the study.
    """

    def __init__(self, name, origin, x_axis=None, y_axis=None, folder=True):
        self.name = name
        self.origin = as_vector3(origin, "origin of section '{}'".format(name))
        self.bases = {}
        self.geom = None
        self.radius = None
        self.study = salome.myStudy
        self.geompy = geomBuilder.New()
        self.folder = self.geompy.NewFolder("section_" + name) if folder else None
        self.x_axis, self.y_axis, self.z_axis = orthonormal_axes(
            [1.0, 0.0, 0.0] if x_axis is None else x_axis,
            [0.0, 1.0, 0.0] if y_axis is None else y_axis)
        self.location = self.geompy.MakeVertex(*self.origin)
        self._publish(self.location, "_origin")
        self.lcs = self.geompy.MakeMarker(*(self.origin + self.x_axis + self.y_axis))
        self._publish(self.lcs, "_LCS")
        self.euler_axis, self.euler_angle = axis_angle_from_axes(self.x_axis, self.y_axis, self.z_axis)
        _refresh_object_browser()

    def add_circle(self, radius):
        """Add a circle centred at the origin, in the local XY plane.

        Parameters
        ----------
        radius : float
            Radius in mm.

        Raises
        ------
        GeometryError
            If the radius is not positive.
        """
        radius = require_positive(radius, "radius of section '{}'".format(self.name))
        self.radius = radius
        self.bases["edge"] = self.geompy.MakeCircleR(radius)
        self.bases["face"] = self.geompy.MakeFaceWires([self.bases["edge"]], isPlanarWanted=True)
        self.bases["shell"] = self.geompy.MakeShell([self.bases["face"]])
        self.geom = self.bases["face"]
        self._transform_bases_to_lcs()
        for key, base in self.bases.items():
            self._publish(base, "_base_" + key)
        _refresh_object_browser()

    def rotate_x(self, angle):
        """Rotate the section about an axis parallel to global X through its origin, in degrees."""
        self._rotate((1.0, 0.0, 0.0), angle)

    def rotate_y(self, angle):
        """Rotate the section about an axis parallel to global Y through its origin, in degrees."""
        self._rotate((0.0, 1.0, 0.0), angle)

    def rotate_z(self, angle):
        """Rotate the section about an axis parallel to global Z through its origin, in degrees."""
        self._rotate((0.0, 0.0, 1.0), angle)

    def _rotate(self, direction, angle):
        """Rotate the LCS and the bases about a global direction through the origin."""
        axis = self.geompy.MakeVectorDXDYDZ(*direction)
        axis = self.geompy.TranslateDXDYDZ(axis, *self.origin)
        self.geompy.Rotate(self.lcs, axis, math.radians(angle))
        self._transform_bases_to_gcs()
        position = self.geompy.GetPosition(self.lcs)
        z_axis, x_axis = list(position[3:6]), list(position[6:9])
        y_axis = [z_axis[1] * x_axis[2] - z_axis[2] * x_axis[1],
                  z_axis[2] * x_axis[0] - z_axis[0] * x_axis[2],
                  z_axis[0] * x_axis[1] - z_axis[1] * x_axis[0]]
        self.x_axis, self.y_axis, self.z_axis = orthonormal_axes(x_axis, y_axis)
        self.euler_axis, self.euler_angle = axis_angle_from_axes(self.x_axis, self.y_axis, self.z_axis)
        self._transform_bases_to_lcs()

    def _transform_bases_to_lcs(self):
        """Move all bases from the global to the local coordinate system."""
        for base in self.bases.values():
            if self.euler_axis is not None:
                axis = self.geompy.MakeVectorDXDYDZ(*self.euler_axis)
                self.geompy.Rotate(base, axis, self.euler_angle)
            self.geompy.TranslateDXDYDZ(base, *self.origin)

    def _transform_bases_to_gcs(self):
        """Move all bases from the local to the global coordinate system."""
        for base in self.bases.values():
            self.geompy.TranslateDXDYDZ(base, *[-value for value in self.origin])
            if self.euler_axis is not None:
                axis = self.geompy.MakeVectorDXDYDZ(*self.euler_axis)
                self.geompy.Rotate(base, axis, -self.euler_angle)

    def _publish(self, geometry, suffix):
        """Add an entity to the study and to the section folder."""
        self.geompy.addToStudy(geometry, self.name + suffix)
        if self.folder:
            self.geompy.PutToFolder(geometry, self.folder)


class Shell:
    """Surface through a sequence of circular sections, closed by end caps.

    Two surface methods are available:

    * ``"thru_sections"`` (default) uses GEOM's ``MakeThruSections``, which builds a smooth
      NURBS surface through the sections. It was the most robust method in our tests.
    * ``"filling"`` uses GEOM's ``MakeFilling``, the method of earlier versions. With
      ``approximation=True``, GEOM samples each section and fits a C2 non-rational B-spline
      surface to the grid of points. This fit is sensitive to the number of sections and
      can fail far from them, which the volume check of
      :meth:`Domain.add_solid_from_shell` detects.

    Parameters
    ----------
    name : str
        Shell name.
    sections : sequence of Section
        At least two sections with circles, in axial order.
    folder : bool, optional
        If true, group the entities in a folder of the study.
    closed : bool, optional
        If true, sew the first and last section faces as end caps.
    method : {"thru_sections", "filling"}, optional
        Surface method.
    precision : float, optional
        3D precision of ``"thru_sections"``.
    min_degree, max_degree : int, optional
        Range of the surface degree of ``"filling"``.
    approximation : bool, optional
        Use GEOM's approximation algorithm in ``"filling"``. When true, GEOM ignores
        ``tol_2d`` and ``max_iterations``.
    tol_2d, tol_3d : float, optional
        Tolerances of ``"filling"``.
    max_iterations : int, optional
        Iterations of ``"filling"`` when ``approximation`` is false.
    sewing_precision : float, optional
        Sewing tolerance of the end caps.
    """

    def __init__(self, name, sections, folder=False, closed=True, method="thru_sections", precision=1.0e-5,
                 min_degree=10, max_degree=20, approximation=True, tol_2d=1.0e-5, tol_3d=1.0e-5,
                 max_iterations=100, sewing_precision=1.0e-4):
        self.name = name
        self.sections = list(sections)
        if len(self.sections) < 2:
            raise GeometryError("Shell '{}' needs at least two sections".format(name))
        if method not in ("thru_sections", "filling"):
            raise GeometryError("Unknown surface method '{}'".format(method))
        if min_degree > max_degree:
            raise GeometryError("min_degree must not exceed max_degree")
        for section in self.sections:
            if "edge" not in section.bases:
                raise GeometryError("Section '{}' of shell '{}' has no circle".format(section.name, name))
        centers = [section.origin for section in self.sections]
        normals = [section.z_axis for section in self.sections]
        radii = [section.radius for section in self.sections]
        check_sections_do_not_intersect(centers, normals, radii, "Shell '{}': section".format(name))
        self.expected_volume = expected_loft_volume(centers, normals, radii)
        self.study = salome.myStudy
        self.geompy = geomBuilder.New()
        self.folder = self.geompy.NewFolder("shell_" + name) if folder else None
        self.edges = [section.bases["edge"] for section in self.sections]
        self.locations = [section.location for section in self.sections]
        self.compound = self.geompy.MakeCompound(self.edges)
        if method == "thru_sections":
            self.face = self.geompy.MakeThruSections(self.edges, False, precision, False)
        else:
            self.face = self.geompy.MakeFilling(self.compound, min_degree, max_degree, tol_2d, tol_3d,
                                                max_iterations, GEOM.FOM_Default, approximation)
        if closed:
            caps = [self.sections[0].bases["shell"], self.sections[-1].bases["shell"]]
            self.geom = self.geompy.MakeShell([self.geompy.MakeSewing([self.face] + caps, sewing_precision)])
        else:
            self.geom = self.geompy.MakeShell([self.face])
        self.geompy.addToStudy(self.geom, self.name)
        self.geompy.addToStudy(self.compound, self.name + "_sections")
        if self.folder:
            self.geompy.PutToFolder(self.geom, self.folder)
            self.geompy.PutToFolder(self.compound, self.folder)
        _refresh_object_browser()


class Solid:
    """A solid published in the SALOME study.

    Parameters
    ----------
    name : str
        Solid name.
    solid : GEOM object
        The solid geometry.
    folder : bool, optional
        If true, group the entity in a folder of the study.
    """

    def __init__(self, name, solid, folder=False):
        self.name = name
        self.geom = solid
        self.study = salome.myStudy
        self.geompy = geomBuilder.New()
        self.folder = self.geompy.NewFolder("solid_" + name) if folder else None
        self.geompy.addToStudy(self.geom, self.name)
        if self.folder:
            self.geompy.PutToFolder(self.geom, self.folder)
        _refresh_object_browser()
