"""Idealized aneurysm from the parameters in ``params_idealized_automatic.json``.

Run with ``./run_in_salome.sh idealized_automatic.py``.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))

from aneupy import IdealizedParameters, build_idealized_model, export_solids  # noqa: E402
from aneupy.geometry import Domain  # noqa: E402

OUTPUT = os.environ.get("ANEUPY_OUTPUT_DIR", "output/idealized_automatic")

parameters = IdealizedParameters.from_json(os.path.join(HERE, "params_idealized_automatic.json"))
print("beta = {:.3f}, gamma = {:.3f}, chi = {:.3f}".format(parameters.beta, parameters.gamma, parameters.chi))

domain = Domain()
names = build_idealized_model(domain, parameters)
export_solids(domain, names, OUTPUT)
domain.save(os.path.join(OUTPUT, "idealized_automatic_study.hdf"))
