"""AneuPy: parametric, simulation-ready geometries of abdominal aortic aneurysms.

The package has two layers:

* a pure Python layer (:mod:`aneupy.centerline`, :mod:`aneupy.profiles`,
  :mod:`aneupy.idealized`, :mod:`aneupy.pipelines`, :mod:`aneupy.validation`) that
  needs only NumPy and SciPy and computes and checks the geometric description;
* a SALOME layer (:mod:`aneupy.geometry`) that turns that description into CAD.

Importing :mod:`aneupy` does not require SALOME. Only :mod:`aneupy.geometry` does.

Conventions used throughout the package
---------------------------------------
Lengths are in millimetres, and areas in square millimetres. Coordinates are
right-handed and Cartesian. In idealized models the vessel axis is the global Z axis.
"""

from .centerline import Centerline, load_centerline
from .idealized import IdealizedParameters
from .pipelines import (
                        Station,
                        add_layered_solids,
                        add_lofted_solid,
                        build_idealized_model,
                        build_image_derived_model,
                        export_solids,
                        prepare_image_derived_stations,
)
from .profiles import AreaProfile, load_area_profile
from .validation import GeometryError, GeometryWarning

__version__ = "1.1.0"

__all__ = [
    "AreaProfile",
    "Centerline",
    "GeometryError",
    "GeometryWarning",
    "IdealizedParameters",
    "Station",
    "add_layered_solids",
    "add_lofted_solid",
    "build_idealized_model",
    "build_image_derived_model",
    "export_solids",
    "load_area_profile",
    "load_centerline",
    "prepare_image_derived_stations",
]
