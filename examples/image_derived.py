"""Parametric model from a centerline and lumen and wall area profiles.

The result has circular cross-sections with the measured areas. It is not an anatomical
replica of the patient. Run with ``./run_in_salome.sh image_derived.py [config.json]``.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "src"))

from aneupy import (  # noqa: E402
    build_image_derived_model,
    export_solids,
    load_area_profile,
    prepare_image_derived_stations,
)
from aneupy.geometry import Domain  # noqa: E402
from aneupy.profiles import read_table  # noqa: E402

CONFIG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "params_image_derived_1.json")
OUTPUT = os.environ.get("ANEUPY_OUTPUT_DIR", "output/image_derived")

with open(CONFIG) as handle:
    config = json.load(handle)
base = os.path.dirname(os.path.abspath(CONFIG))

stations = prepare_image_derived_stations(
    read_table(os.path.join(base, config.pop("centerline_file")), 3),
    load_area_profile(os.path.join(base, config.pop("wall_area_file")), "wall area"),
    load_area_profile(os.path.join(base, config.pop("lumen_area_file")), "lumen area"),
    **config)
print(json.dumps(stations.diagnostics, indent=2, sort_keys=True))

domain = Domain()
names = build_image_derived_model(domain, stations)
export_solids(domain, names, OUTPUT)
domain.save(os.path.join(OUTPUT, "image_derived_study.hdf"))
