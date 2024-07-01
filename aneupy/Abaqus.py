# =============================================================================
#
# Abaqus.py
#
# Python module to generate fluid-structure interaction (FSI) models in Abaqus
#
# Jacobo Diaz - jdiaz@udc.es
# 2015
#
# =============================================================================

import os

# Abaqus Python modules
from abaqus import *
from abaqusConstants import *
from caeModules import *
from part import *
from material import *
from section import *
from assembly import *
from step import *
from interaction import *
from load import *
from mesh import *
from job import *
from sketch import *
from visualization import *
from connectorBehavior import *
from regionToolset import *
from odbAccess import *
from odbSection import *


class Database(object):

    def __init__(self, **kwargs):
        Mdb()

        for odb in session.odbs.values():
            odb.close()

    def save(self, file):

        file_path = os.path.dirname(file)

        file_extension = '.cae'
        file_name = os.path.basename(file.rsplit(file_extension, 1)[0])

        mdb.saveAs(pathName=os.path.join(file_path, file_name + file_extension))


class Model(object):

    def __init__(self, name, cfd=False, **kwargs):

        self.name = name
        self.cfd = cfd

        self.parts = {}
        self.materials = {}
        self.instances = {}

        if self.cfd:
            self.model = mdb.Model(name=name, modelType=CFD)
        else:
            self.model = mdb.Model(name=name, modelType=STANDARD_EXPLICIT)

        if 'Model-1' in mdb.models and name != 'Model-1':
            del mdb.models['Model-1']

    def part_from_iges(self, iges_file, name=None):

        if not name:
            name = os.path.splitext(os.path.basename(iges_file))[0]

        iges = mdb.openIges(iges_file, msbo=True, trimCurve=DEFAULT, scaleFromFile=OFF)

        self.parts[name] = self.model.PartFromGeometryFile(name=name,
            geometryFile=iges, combine=False, stitchTolerance=1.0,
            dimensionality=THREE_D, type=DEFORMABLE_BODY, convertToAnalytical=1, stitchEdges=1)

    def add_material(self, name, **kwargs):
        self.materials[name] = self.model.Material(name=name)

        self.density = kwargs.get('density', self.density)

        self.materials[name].Density(table=((1000.0, ), ))
        self.materials[name].Viscosity(table=((0.001,), ))

        self.materials[name].Elastic(table=((materiales[i]['E'], materiales[i]['Nu']), ))

        self.materials[name].Hyperelastic(
            materialType=ISOTROPIC, testData=OFF, type=ARRUDA_BOYCE,
            volumetricResponse=VOLUMETRIC_DATA, table=((1.0, 2.0, 3.0), ))

        self.materials[name].Conductivity(table=((11.0, ), ))
        self.materials[name].Plastic(table=((2.0, 0.0), (3.0, 3.0)))
        self.materials[name].Expansion(table=((333.0, ), ))


        mdb.models['aneurysm_fluid'].HomogeneousFluidSection(name='Section-1', material='Material-1')
        mdb.models['aneurysm_solid'].HomogeneousSolidSection(name='Section-1', material='Material-1', thickness=None)



    def create_assembly(self):
        for name, part in self.parts.items():
            self.instances[name] = self.model.rootAssembly.Instance(name=name, part=part, dependent=ON)
