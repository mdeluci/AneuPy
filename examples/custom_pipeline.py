"""Custom pipeline: an asymmetry sweep with a user-defined two-layer wall.

The ready-made builders are ordinary functions, so a study can combine the same building
blocks in its own way. Run with ``./run_in_salome.sh custom_pipeline.py``.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from aneupy import IdealizedParameters, add_layered_solids, export_solids  # noqa: E402
from aneupy.geometry import Domain  # noqa: E402
from aneupy.pipelines import stations_from_arrays  # noqa: E402

OUTPUT = os.environ.get("ANEUPY_OUTPUT_DIR", "output/custom_pipeline")
WALL_THICKNESS = {"inner_wall": 0.9, "outer_wall": 0.6}  # mm

for beta in (1.0, 0.6, 0.2):
    parameters = IdealizedParameters.from_descriptors(beta=beta, gamma=0.625, chi=2.5, neck_diameter=20.0)
    centers = parameters.centers()
    radii = parameters.lumen_radii()
    layers = []
    for name, thickness in WALL_THICKNESS.items():
        radii = radii + thickness
        layers.append((name, stations_from_arrays(centers, radii)))
    domain = Domain()
    names = add_layered_solids(domain, "fluid", stations_from_arrays(centers, parameters.lumen_radii()), layers)
    export_solids(domain, names, os.path.join(OUTPUT, "beta_{:.1f}".format(beta)), formats=("step",))
