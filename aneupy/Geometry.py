# =============================================================================
#
# Geometry.py
#
# Python module to generate solid models in SALOME
#
# Jacobo Diaz - jdiaz@udc.es
# Mario de Lucio - mdeluci@purdue.edu
# 2024
#
# =============================================================================
#!/usr/bin/env python3

import os
import sys
import math
import json

import salome
import GEOM
from salome.geom import geomBuilder
import SALOMEDS


class Domain(object):

    def __init__(self, **kwargs):
        self.sections = {}
        self.shells = {}
        self.solids = {}

	# Initialize SALOME study
        salome.salome_init()
        self.study = salome.myStudy

        # Initialize GEOM module without the 'study' argument
        self.geompy = geomBuilder.New()

        self.geompy.addToStudyAuto(0)

        O = self.geompy.MakeVertex(0, 0, 0)
        OX = self.geompy.MakeVectorDXDYDZ(1, 0, 0)
        OY = self.geompy.MakeVectorDXDYDZ(0, 1, 0)
        OZ = self.geompy.MakeVectorDXDYDZ(0, 0, 1)

    def add_section(self, name, **kwargs):

        self.sections[name] = Section(name, **kwargs)

    def add_shell(self, name, sections, **kwargs):

        sections_list = []
        for section in sections:
            sections_list.append(self.sections[section])

        self.shells[name] = Shell(name, sections_list, **kwargs)

    def add_solid_from_shell(self, name, shell, **kwargs):

        solid = self.geompy.MakeSolid([self.shells[shell].geom])
        self.solids[name] = Solid(name, solid, **kwargs)

    def add_solid_from_cut(self, name, solids, **kwargs):

        solid = self.geompy.MakeCut(self.solids[solids[0]].geom, self.solids[solids[1]].geom, checkSelfInte=True)
        self.solids[name] = Solid(name, solid, **kwargs)

    def export_iges(self, solid, file):
        self.geompy.ExportIGES(self.solids[solid].geom, file, theVersion='5.3')

    def export_stl(self, solid, file):
        # Export the STL
        #self.geompy.ExportSTL(self.solids[solid].geom, file, False)
        self.geompy.ExportSTL(self.solids[solid].geom, file, False, 0.0001) #Custom linear deflection

    def export_vtk(self, solid, file):
        self.geompy.ExportVTK(self.solids[solid].geom, file, 0.001)

    def export_step(self, solid, file):
        self.geompy.ExportSTEP(self.solids[solid].geom, file)


    def save(self, file):

        file_path = os.path.dirname(file)

	# Save SALOME study
        file_extension = '.hdf'
        file_name = os.path.basename(file.rsplit(file_extension, 1)[0])

	# Ensure the file path and name are correctly set
        study_path = os.path.join(file_path, file_name + file_extension)

	# Save the study
        self.study.SaveAs(study_path, self.study, False)

        # Save Python dictionary with CAD information
        file_extension = '.cad'
        file_name = os.path.basename(file.rsplit(file_extension, 1)[0])

        self._get_cad_info()

        with open(os.path.join(file_path, file_name + file_extension), 'w') as output_file:
            json.dump(self.info, output_file, indent=2, sort_keys=True)

    def _get_cad_info(self):

        self.info = {}
        self.info['sections'] = {}
        self.info['shells'] = {}
        self.info['solids'] = {}

        entities = {}
        for d in (self.sections, self.shells, self.solids):
            entities.update(d)

        for name, entity in entities.items():
            entity_type = type(entity).__name__.lower() + 's'

            BasicProperties = self.geompy.BasicProperties(entity.geom)
            Inertia = self.geompy.Inertia(entity.geom)
            CDG = self.geompy.PointCoordinates(self.geompy.MakeCDG(entity.geom))

            self.info[entity_type][name] = {}
            self.info[entity_type][name]['Length'] = BasicProperties[0]
            self.info[entity_type][name]['Area'] = BasicProperties[1]
            self.info[entity_type][name]['Volume'] = BasicProperties[2]
            self.info[entity_type][name]['I11'] = Inertia[0]
            self.info[entity_type][name]['I12'] = Inertia[1]
            self.info[entity_type][name]['I13'] = Inertia[2]
            self.info[entity_type][name]['I21'] = Inertia[3]
            self.info[entity_type][name]['I22'] = Inertia[4]
            self.info[entity_type][name]['I23'] = Inertia[5]
            self.info[entity_type][name]['I31'] = Inertia[6]
            self.info[entity_type][name]['I32'] = Inertia[7]
            self.info[entity_type][name]['I33'] = Inertia[8]
            self.info[entity_type][name]['Ix'] = Inertia[9]
            self.info[entity_type][name]['Iy'] = Inertia[10]
            self.info[entity_type][name]['Iz'] = Inertia[11]
            self.info[entity_type][name]['CDG'] = CDG


class Section(object):
    """ Defines a cross section.

        Cross sections are defined in the XY plane and then are transformed to
        the local coordinate system (LCS) defined with origin and OX_LCS and OY_LCS

        Origin is mandatory and the default LCS is the global coordinate system (GCS)

        OX_LCS is a sequence with the three components of LCS OX direction in GCS
        OY_LCS is a sequence with the three components of LCS OY direction in GCS

    """

    def __init__(self, name, origin, OX_LCS=None, OY_LCS=None, folder=True):
        self.name = name
        self.origin = list(origin)
        self.bases = {}

        # Get the current study
        self.study = salome.myStudy

        self.geompy = geomBuilder.New()

        if folder:
            self.folder = self.geompy.NewFolder('section_' + name)
        else:
            self.folder = None

        try:
            self.OX_LCS = list(OX_LCS)
        except:
            self.OX_LCS = [1., 0., 0.]

        try:
            self.OY_LCS = list(OY_LCS)
        except:
            self.OY_LCS = [0., 1., 0.]

        # Create a vertex in the origin of the LCS
        self.location = self.geompy.MakeVertex(*tuple(self.origin))
        self.geompy.addToStudy(self.location, self.name + '_origin')
        if self.folder:
            self.geompy.PutToFolder(self.location, self.folder)

        # Create LCS for the section
        self.LCS = self.geompy.MakeMarker(*tuple(self.origin + self.OX_LCS + self.OY_LCS))
        self._obtain_rotation_matrix_LCS()
        self.geompy.addToStudy(self.LCS, self.name + '_LCS')
        if self.folder:
            self.geompy.PutToFolder(self.LCS, self.folder)

        try:
            salome.sg.updateObjBrowser()
        except AttributeError:
            pass


    def _obtain_rotation_matrix_LCS(self):
        """ Obtains the rotation matrix R of the LCS and the
            Euler's angle and axis of the transformation"""

        _temp = self.geompy.GetPosition(self.LCS)
        rx = _temp[6:9]
        rz = _temp[3:6]
        vx = self.geompy.MakeVectorDXDYDZ(*rx)
        vz = self.geompy.MakeVectorDXDYDZ(*rz)
        vy = self.geompy.CrossProduct(vz, vx)
        ry = self.geompy.VectorCoordinates(vy)
        R = [list(rx), list(ry), list(rz)]

        eangle = math.acos(0.5*(R[0][0]+R[1][1]+R[2][2]-1.))
        if abs(eangle) > 1.E-2:
            eaxis = [(R[2][1]-R[1][2])/(2.*math.sin(eangle)),
                     (R[0][2]-R[2][0])/(2.*math.sin(eangle)),
                     (R[1][0]-R[0][1])/(2.*math.sin(eangle)),
                     ]
            eaxisv = self.geompy.MakeVectorDXDYDZ(*eaxis)
        else:
            eaxis = [0, 0, 0]
            eaxisv = None

        self.R = R
        self.EulerAngle = eangle
        self.EulerAngleDeg = eangle*180./math.pi
        self.EulerAxis = eaxis
        self.EulerAxisVector = eaxisv

    def _transform_bases_to_LCS(self):
        """ Transforms all bases to the LCS"""

        for base in self.bases.values():
            if self.EulerAxisVector:
                self.geompy.Rotate(base, self.EulerAxisVector, -self.EulerAngle)

            self.geompy.TranslateDXDYDZ(base, *tuple(self.origin))

    def _transform_bases_to_GCS(self):
        """ Transforms all bases to the GCS"""

        for base in self.bases.values():
            self.geompy.TranslateDXDYDZ(base, *tuple([-i for i in self.origin]))

            if self.EulerAxisVector:
                self.geompy.Rotate(base, self.EulerAxisVector, self.EulerAngle)

    def rotateX(self, angle):
        """Rotate the section around an axis parallel to global X
        through the origin of the LCS"""

        axis = self.geompy.MakeVectorDXDYDZ(1., 0, 0)
        axis = self.geompy.TranslateDXDYDZ(axis, *tuple(self.origin))
        self.geompy.Rotate(self.LCS, axis, angle*math.pi/180.)
        self._transform_bases_to_GCS()
        self._obtain_rotation_matrix_LCS()
        self._transform_bases_to_LCS()

    def rotateY(self, angle):
        """Rotate the section around an axis parallel to global Y
        through the origin of the LCS"""

        axis = self.geompy.MakeVectorDXDYDZ(0., 1., 0)
        axis = self.geompy.TranslateDXDYDZ(axis, *tuple(self.origin))
        self.geompy.Rotate(self.LCS, axis, angle*math.pi/180.)
        self._transform_bases_to_GCS()
        self._obtain_rotation_matrix_LCS()
        self._transform_bases_to_LCS()

    def rotateZ(self, angle):
        """Rotate the section around an axis parallel to global Z
        through the origin of the LCS"""

        axis = self.geompy.MakeVectorDXDYDZ(0., 0., 1.)
        axis = self.geompy.TranslateDXDYDZ(axis, *tuple(self.origin))
        self.geompy.Rotate(self.LCS, axis, angle*math.pi/180.)
        self._transform_bases_to_GCS()
        self._obtain_rotation_matrix_LCS()
        self._transform_bases_to_LCS()

    def add_circle(self, radius):
        self.bases['edge'] = self.geompy.MakeCircleR(radius)
        self.bases['face'] = self.geompy.MakeFaceWires([self.bases['edge']], isPlanarWanted=True)
        self.bases['shell'] = self.geompy.MakeShell([self.bases['face']])
        self.geom = self.bases['face']

        self._transform_bases_to_LCS()

        for key, base in self.bases.items():
            self.geompy.addToStudy(base, self.name + '_base_' + key)
            if self.folder:
                self.geompy.PutToFolder(base, self.folder)

        try:
            salome.sg.updateObjBrowser()
        except AttributeError:
            pass

    def add_circle2(self, circle_center, normal, radius):
        """
        Adds a circle to the section using specified center, normal vector, and radius.

        Args:
            circle_center (list or geomBuilder.GEOM_Vertex): The center point of the circle.
            normal (list): The normal vector defining the circle's orientation.
            circle_radius (float): The radius of the circle.
        Returns:
            None: The circle is added to the SALOME study and potentially a folder.
        """
        # Ensure the circle_center is a geomBuilder Vertex, not just coordinates
        if isinstance(circle_center, list):
            circle_center = self.geompy.MakeVertex(*circle_center)
	# Create the normal vector from components if it's not already a geompy object
        if isinstance(normal, list):
            normal = self.geompy.MakeVectorDXDYDZ(*normal)

        # Create the circle
        self.bases['edge'] = self.geompy.MakeCircle(circle_center, normal, radius)
        self.bases['face'] = self.geompy.MakeFaceWires([self.bases['edge']], isPlanarWanted=True)
        self.bases['shell'] = self.geompy.MakeShell([self.bases['face']])
        self.geom = self.bases['face']

        for key, base in self.bases.items():
            self.geompy.addToStudy(base, self.name + '_base_' + key)
            if self.folder:
                self.geompy.PutToFolder(base, self.folder)

        # Update GUI if needed
        try:
            salome.sg.updateObjBrowser()
        except AttributeError:
            pass


class Shell(object):

    def __init__(self, name, sections, folder=False, closed=True, minBSplineDegree=10, maxBSplineDegree=20, approximation=True):
        self.name, self.sections = name, sections

        self.edges = []
        self.shells = []
        self.locations = []

        # Get the current study
        self.study = salome.myStudy
        self.geompy = geomBuilder.New()

        if folder:
            self.folder = self.geompy.NewFolder('shell_' + name)
        else:
            self.folder = None

        theMinDeg = minBSplineDegree
        theMaxDeg = maxBSplineDegree
        theTol2D = 1.E-5
        theTol3D = 1.E-5
        theNbIter = 100
        theMethod = GEOM.FOM_Default
        isApprox = approximation

        sewing_precision = 1.E-4

        for section in self.sections:
            self.edges.append(section.bases['edge'])
            self.shells.append(section.bases['shell'])
            self.locations.append(section.location)

        self.compound = self.geompy.MakeCompound(self.edges)
        self.face = self.geompy.MakeFilling(self.compound, theMinDeg, theMaxDeg, theTol2D, theTol3D, theNbIter, theMethod, isApprox)

        if closed:
            sewing = self.geompy.MakeSewing([self.face, self.sections[0].bases['shell'], self.sections[-1].bases['shell']], sewing_precision)
            self.geom = self.geompy.MakeShell([sewing])
        else:
            self.geom = self.geompy.MakeShell([self.face])

        self.geompy.addToStudy(self.geom, self.name)
        self.geompy.addToStudy(self.compound, self.name + '_sections')

        if self.folder:
            self.geompy.PutToFolder(self.geom, self.folder)
            self.geompy.PutToFolder(self.compound, self.folder)

        try:
            salome.sg.updateObjBrowser()
        except AttributeError:
            pass

class Solid(object):

    def __init__(self, name, solid, folder=False):
        self.name = name
        self.geom = solid

        self.study = salome.myStudy
        self.geompy = geomBuilder.New()

        if folder:
            self.folder = self.geompy.NewFolder('solid_' + name)
        else:
            self.folder = None

        self.geompy.addToStudy(self.geom, self.name)

        if self.folder:
            self.geompy.PutToFolder(self.geom, self.folder)

        salome.sg.updateObjBrowser()
