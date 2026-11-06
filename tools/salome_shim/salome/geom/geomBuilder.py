"""OpenCASCADE-backed subset of SALOME's ``geomBuilder``, for testing only.

This shim lets AneuPy's real code run without a SALOME installation. Each method
mirrors the GEOM operation of the same name; ``MakeFilling`` with ``isApprox=True``
follows ``GEOMImpl_FillingDriver::Execute`` from the SALOME GEOM sources: every
section is sampled at ``nbp = max(21, 2*MaxNbPoles - 1)`` equally spaced parameters
and the grid is passed to ``GeomAPI_PointsToBSplineSurface`` with C2 continuity.
``MakeThruSections`` follows ``GEOMImpl_ThruSectionsDriver::Execute``.

It is a verification instrument, not a replacement for SALOME.
"""
import math

from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakeSolid, BRepBuilderAPI_MakeVertex,
                                BRepBuilderAPI_MakeWire, BRepBuilderAPI_Sewing,
                                BRepBuilderAPI_Transform)
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepTools import BRepTools
from OCP.GeomAPI import GeomAPI_Interpolate, GeomAPI_PointsToBSplineSurface
from OCP.GeomAbs import GeomAbs_C2
from OCP.Geom import Geom_Circle
from OCP.GProp import GProp_GProps
from OCP.IGESControl import IGESControl_Controller, IGESControl_Writer
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.ShapeFix import ShapeFix_Solid
from OCP.StlAPI import StlAPI_Writer
from OCP.TColgp import TColgp_Array2OfPnt, TColgp_HArray1OfPnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shell
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec, gp_XYZ

LOG = []


class Shape:
    """Mutable holder, because GEOM operations modify objects in place."""

    def __init__(self, shape=None, **attributes):
        self.shape = shape
        self.__dict__.update(attributes)


def _edge_of(shape):
    explorer = TopExp_Explorer(shape.shape, TopAbs_EDGE)
    return TopoDS.Edge_s(explorer.Current())


class GeomBuilder:
    """Subset of ``geomBuilder`` used by AneuPy."""

    def addToStudy(self, *args, **kwargs):
        return None

    def addToStudyAuto(self, *args, **kwargs):
        return None

    def NewFolder(self, name):
        return name

    def PutToFolder(self, *args, **kwargs):
        return None

    def MakeVertex(self, x, y, z):
        builder = BRepBuilderAPI_MakeVertex(gp_Pnt(float(x), float(y), float(z)))
        return Shape(builder.Vertex(), xyz=(float(x), float(y), float(z)), keep=builder)

    def MakeVectorDXDYDZ(self, dx, dy, dz):
        return Shape(None, origin=(0.0, 0.0, 0.0), vector=(float(dx), float(dy), float(dz)))

    def VectorCoordinates(self, vector):
        return vector.vector

    def CrossProduct(self, a, b):
        p, q = a.vector, b.vector
        return self.MakeVectorDXDYDZ(p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2],
                                     p[0] * q[1] - p[1] * q[0])

    def PointCoordinates(self, point):
        return point.xyz

    def MakeMarker(self, ox, oy, oz, xdx, xdy, xdz, ydx, ydy, ydz):
        x_axis = gp_Vec(xdx, xdy, xdz)
        y_axis = gp_Vec(ydx, ydy, ydz)
        z_axis = x_axis.Crossed(y_axis)
        x_axis.Normalize()
        z_axis.Normalize()
        return Shape(None, marker=True, origin=(ox, oy, oz),
                     z=(z_axis.X(), z_axis.Y(), z_axis.Z()),
                     x=(x_axis.X(), x_axis.Y(), x_axis.Z()))

    def GetPosition(self, shape):
        return tuple(shape.origin) + tuple(shape.z) + tuple(shape.x)

    def MakeCircleR(self, radius):
        LOG.append(('MakeCircleR', float(radius)))
        circle = Geom_Circle(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1), gp_Dir(1, 0, 0)), float(radius))
        builder = BRepBuilderAPI_MakeEdge(circle)
        return Shape(builder.Edge(), keep=builder)

    def MakeCircle(self, center, normal, radius):
        LOG.append(('MakeCircle', center.xyz, normal.vector, float(radius)))
        axes = gp_Ax2(gp_Pnt(*center.xyz), gp_Dir(*normal.vector))
        circle = Geom_Circle(axes, float(radius))
        builder = BRepBuilderAPI_MakeEdge(circle)
        return Shape(builder.Edge(), keep=builder)

    def MakeFaceWires(self, wires, isPlanarWanted=False):
        wire_builder = BRepBuilderAPI_MakeWire(TopoDS.Edge_s(wires[0].shape))
        face_builder = BRepBuilderAPI_MakeFace(wire_builder.Wire(), bool(isPlanarWanted))
        return Shape(face_builder.Face(), keep=(wire_builder, face_builder))

    def MakeShell(self, faces):
        if len(faces) == 1 and faces[0].shape.ShapeType() == TopAbs_SHELL:
            return Shape(faces[0].shape)
        builder = BRep_Builder()
        shell = TopoDS_Shell()
        builder.MakeShell(shell)
        for item in faces:
            explorer = TopExp_Explorer(item.shape, TopAbs_FACE)
            while explorer.More():
                builder.Add(shell, TopoDS.Face_s(explorer.Current()))
                explorer.Next()
        return Shape(shell)

    def MakeCompound(self, shapes):
        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)
        for item in shapes:
            builder.Add(compound, item.shape)
        return Shape(compound, members=list(shapes))

    def MakeFilling(self, contours, min_degree=2, max_degree=5, tol_2d=1e-4, tol_3d=1e-4,
                    n_iterations=0, method=0, is_approx=0):
        LOG.append(('MakeFilling', min_degree, max_degree, tol_2d, tol_3d, n_iterations, is_approx))
        if not is_approx:
            raise NotImplementedError('The shim implements only the isApprox=True branch')
        curves = []
        explorer = TopExp_Explorer(contours.shape, TopAbs_EDGE)
        while explorer.More():
            first = [0.0]
            last = [0.0]
            edge = TopoDS.Edge_s(explorer.Current())
            curve = BRep_Tool.Curve_s(edge, 0.0, 0.0)
            first, last = BRep_Tool.Range_s(edge)
            curves.append((curve, first, last))
            explorer.Next()
        n_curves = len(curves)
        n_points = 21
        points = TColgp_Array2OfPnt(1, n_curves, 1, n_points)
        for i, (curve, first, last) in enumerate(curves):
            step = (last - first) / (n_points - 1)
            for j in range(n_points):
                points.SetValue(i + 1, j + 1, curve.Value(first + step * j))
        surface = GeomAPI_PointsToBSplineSurface(points, int(min_degree), int(max_degree),
                                                 GeomAbs_C2, float(tol_3d)).Surface()
        builder = BRepBuilderAPI_MakeFace(surface, 1.0e-7)
        return Shape(builder.Face(), surface=surface, keep=builder)

    def MakeThruSections(self, sections, mode_solid, precision, ruled):
        LOG.append(('MakeThruSections', len(sections), mode_solid, precision, ruled))
        builder = BRepOffsetAPI_ThruSections(bool(mode_solid), bool(ruled), max(float(precision), 1.0e-7))
        builder.CheckCompatibility(False)
        wires = []
        for section in sections:
            wire = BRepBuilderAPI_MakeWire(TopoDS.Edge_s(section.shape))
            wires.append(wire)
            builder.AddWire(wire.Wire())
        builder.Build()
        return Shape(builder.Shape(), keep=(builder, wires))

    def MakeSewing(self, shapes, tolerance):
        sewing = BRepBuilderAPI_Sewing(float(tolerance))
        for shape in shapes:
            sewing.Add(shape.shape)
        sewing.Perform()
        return Shape(sewing.SewedShape(), keep=sewing)

    def MakeSolid(self, shells):
        shell = shells[0].shape
        if shell.ShapeType() != TopAbs_SHELL:
            explorer = TopExp_Explorer(shell, TopAbs_SHELL)
            shell = explorer.Current()
        builder = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(shell))
        solid = builder.Solid()
        fixer = ShapeFix_Solid(solid)
        fixer.Perform()
        fixed = fixer.Solid()
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(fixed, properties)
        if properties.Mass() < 0:
            fixed = fixed.Reversed()
        return Shape(fixed)

    def MakeCut(self, first, second, checkSelfInte=False):
        cut = BRepAlgoAPI_Cut(first.shape, second.shape)
        cut.Build()
        if not cut.IsDone():
            raise RuntimeError('MakeCut failed')
        return Shape(cut.Shape(), keep=cut)

    def _transform(self, shape, transform):
        if shape.shape is not None:
            builder = BRepBuilderAPI_Transform(shape.shape, transform, True)
            shape.shape = builder.Shape()
            shape.keep = builder
        return shape

    def TranslateDXDYDZ(self, shape, dx, dy, dz):
        if getattr(shape, 'vector', None) is not None and shape.shape is None:
            ox, oy, oz = shape.origin
            shape.origin = (ox + dx, oy + dy, oz + dz)
            return shape
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(float(dx), float(dy), float(dz)))
        return self._transform(shape, transform)

    def Rotate(self, shape, axis, angle):
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(*axis.origin), gp_Dir(*axis.vector)), float(angle))
        if getattr(shape, 'marker', False):
            origin = gp_Pnt(*shape.origin).Transformed(transform)
            z_axis = gp_Vec(*shape.z).Transformed(transform)
            x_axis = gp_Vec(*shape.x).Transformed(transform)
            shape.origin = (origin.X(), origin.Y(), origin.Z())
            shape.z = (z_axis.X(), z_axis.Y(), z_axis.Z())
            shape.x = (x_axis.X(), x_axis.Y(), x_axis.Z())
            return shape
        return self._transform(shape, transform)

    def MakeInterpol(self, points, *args, **kwargs):
        array = TColgp_HArray1OfPnt(1, len(points))
        for index, point in enumerate(points):
            array.SetValue(index + 1, gp_Pnt(*point.xyz))
        interpolation = GeomAPI_Interpolate(array, False, 1.0e-7)
        interpolation.Perform()
        builder = BRepBuilderAPI_MakeEdge(interpolation.Curve())
        return Shape(builder.Edge(), keep=(interpolation, builder))

    def BasicProperties(self, shape, *args, **kwargs):
        if shape.shape is None:
            return (0.0, 0.0, 0.0)
        linear, surface, volume = GProp_GProps(), GProp_GProps(), GProp_GProps()
        BRepGProp.LinearProperties_s(shape.shape, linear)
        BRepGProp.SurfaceProperties_s(shape.shape, surface)
        BRepGProp.VolumeProperties_s(shape.shape, volume)
        return (linear.Mass(), surface.Mass(), volume.Mass())

    def Inertia(self, shape):
        return tuple([0.0] * 12)

    def MakeCDG(self, shape):
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape.shape, properties)
        centre = properties.CentreOfMass()
        return self.MakeVertex(centre.X(), centre.Y(), centre.Z())

    def ExportSTEP(self, shape, path, unit=0):
        # As STEPPlugin_ExportDriver: the model is in metres and the unit is only that of the file.
        writer = STEPControl_Writer()
        writer.Model().SetLocalLengthUnit(1000.0)
        writer.Model().SetWriteLengthUnit({0: 1000.0, 1: 1.0}[unit])
        Interface_Static.SetCVal_s("write.step.unit", {0: "M", 1: "MM"}[unit])
        writer.Transfer(shape.shape, STEPControl_AsIs)
        writer.Write(path)

    def ExportIGES(self, shape, path, theVersion='5.3'):
        # GEOM writes model units as metres. This OCCT binding has no public switch for the
        # model unit, so the shim only checks that the shape can be written.
        IGESControl_Controller.Init_s()
        writer = IGESControl_Writer('MM', 0)
        writer.AddShape(shape.shape)
        writer.ComputeModel()
        writer.Write(path)

    def MakeScaleTransform(self, shape, point, factor):
        transform = gp_Trsf()
        transform.SetScale(gp_Pnt(0.0, 0.0, 0.0), float(factor))
        builder = BRepBuilderAPI_Transform(shape.shape, transform, True)
        return Shape(builder.Shape(), keep=builder)

    def ExportBREP(self, shape, path):
        BRepTools.Write_s(shape.shape, path)

    def ExportSTL(self, shape, path, is_ascii=True, deflection=0.001, is_relative=True):
        BRepMesh_IncrementalMesh(shape.shape, float(deflection) if not is_relative else 0.05,
                                 bool(is_relative), 0.2, True)
        writer = StlAPI_Writer()
        writer.ASCIIMode = bool(is_ascii)
        writer.Write(shape.shape, path)

    def ExportVTK(self, shape, path, deflection=0.001):
        raise NotImplementedError('ExportVTK is not provided by the test shim')


_BUILDER = GeomBuilder()


def New(*args, **kwargs):
    """Return the shared builder, as ``geomBuilder.New`` does for a SALOME session."""
    return _BUILDER
