# AneuPy

AneuPy generates parametric, simulation-ready geometries of abdominal aortic aneurysms (AAA) with the
Python interface of the [SALOME platform](https://www.salome-platform.org/). The solids are intended for
finite element analysis, computational fluid dynamics and fluid-structure interaction studies.

![Logo](./Logo.png)

## What AneuPy is for

AneuPy builds families of geometries in which each morphological variable can be changed on its own, for
example in sensitivity analyses or in the verification of solvers. It offers:

- **Idealized models**: a straight reference axis, circular sections, equal necks and uniform wall layers, all
  prescribed by parameters and not derived from any patient. See [Idealized models](#idealized-models).
- **Image-derived parametric models**: a centerline and area profiles measured from images, reconstructed with
  circular sections concentric to the centerline. See [Image-derived models](#image-derived-parametric-models).

**AneuPy is not a patient-specific modelling tool.** Circular sections keep the measured area but not the
shape of a section, and the thrombus has no circumferential variation. To predict the stress of an individual
patient from a segmentation, use a tool that keeps the segmented surface, such as
[BioPARR](http://bioparr.mech.uwa.edu.au/).

## Requirements

- SALOME 9.11, which provides Python 3.6, NumPy, SciPy and the GEOM module. No installation is needed inside
  SALOME, because the examples add the repository to the Python path. The geometry module also supports the import
  layout of recent SALOME versions.
- The layers of `aneupy` other than `aneupy.geometry` need only NumPy and SciPy. `pip install` requires Python 3.7.

```bash
git clone https://github.com/mdeluci/AneuPy.git
cd AneuPy/examples
export SALOME_ROOT_DIR=/path/to/SALOME-9.11.0
./run_in_salome.sh idealized_automatic.py
```

## Conventions

| Item | Convention |
| --- | --- |
| Length, area | Millimetres, square millimetres |
| Coordinates | Right-handed Cartesian. The axis of an idealized model is global Z |
| Section | Defined in the XY plane of its local system, whose Z axis is the section normal |
| Circle seam | On the local X axis |
| Arc length | Measured along the processed centerline, from its first point |
| Exported files | STEP and IGES carry the physical size. STL, VTK and BREP store millimetres without units |

## Idealized models

The radius, thrombus thickness and centre shift follow one shape function, with `zc` the model mid-length:

```text
w(z) = cos^2(pi (z - zc) / LAAA)   inside the sac, and 0 in the necks
```

| Parameter | Meaning |
| --- | --- |
| `length` | Total model length, including both necks |
| `radius_nondilated` | Lumen radius of the necks |
| `radius_dilated` | Radius of the vessel lumen at the midsection, before any thrombus |
| `wall_thickness_intima`, `wall_thickness_media`, `wall_thickness_adventitia` | Layer thicknesses |
| `ilt_thickness` | Thrombus thickness at the midsection |
| `x_shift`, `y_shift` | Offset of the midsection centre from the Z axis |
| `sac_fraction` | `LAAA / length` |
| `section_spacing` | Axial distance between sections (5 mm by default) |

The dimensionless descriptors can be used directly:

```python
from aneupy import IdealizedParameters, build_idealized_model, export_solids
from aneupy.geometry import Domain

parameters = IdealizedParameters.from_descriptors(beta=0.2, gamma=0.625, chi=2.5, neck_diameter=20.0)
domain = Domain()
names = build_idealized_model(domain, parameters)
export_solids(domain, names, "output")
```

Models defined by their dimensions are also available from the command line:

```bash
./run_in_salome.sh aneupy_cli.py idealized --config params_idealized_automatic.json --x_shift 0 --output-dir output
```

The intima and any thrombus form one solid, `aneurysm_intima_ILT`.

## Image-derived parametric models

### Input data

| File | Columns | Separator |
| --- | --- | --- |
| Centerline | X, Y, Z in mm, ordered along the vessel | Commas and/or whitespace |
| Wall area | Axial position, area in mm2 enclosed by the outer wall | Commas and/or whitespace |
| Lumen area | Axial position, lumen area in mm2 | Commas and/or whitespace |

AneuPy does not process images. A segmentation of lumen and outer wall is needed first. With
[3D Slicer](https://www.slicer.org/) and its
[SlicerVMTK extension](https://github.com/vmtk/SlicerExtension-VMTK), the *Extract Centerline* module provides
the centerline and the *Cross-Section Analysis* module measures the area along it. VMTK offers the same
operations from its own tools. The sample files in `examples/data` have this format; please see the article for
their source.

### Processing

1. The centerline is smoothed and reparameterized by arc length (`centerline_cutoff`).
2. Both area profiles become equivalent radii, `R = sqrt(A / pi)`, and map linearly onto arc length over their
   common abscissa range. `flip_profiles` selects which end corresponds to the first abscissa.
3. Both radii are smoothed (`profile_cutoff`). Oscillations of this wavelength in mm keep half of their amplitude.
4. All quantities are sampled at uniformly spaced sections (`n_sections`).
5. The limits below are checked and, when they hold, lumen and `wall_ilt` solids are built.

Area profiles cannot separate wall from thrombus, so `wall_ilt` contains both.

## Checks and limits

AneuPy stops with a `GeometryError`, or warns with a `GeometryWarning`, when the input approaches these limits:

| Limit | Check | Result |
| --- | --- | --- |
| Tight bends (image-derived models) | `curvature x radius < 1` along the centerline | Error, with a warning above 0.8 |
| Folded sections (all shells) | Discs of different sections must not intersect | Error |
| Section order (all shells) | Sections must advance monotonically along their normals | Error |
| Crossing boundaries (image-derived and idealized models) | Lumen inside the outer wall at every section | Error, with a warning below 0.1 mm |
| Failed surface fit (all solids from shells) | Solid volume against the volume implied by the sections | Warning above 1%, error above 5% |
| Boolean cuts (all cuts) | Material must remain, and the removed solid should lie inside the other | Error, or a warning |
| Malformed tables | Columns and numbers (file and line); positive areas (file and row); sorted positions | Error or warning |
| Non-circular sections | Not supported: inputs provide only an area for each position | Not expressible |

Solids are exported separately, so the interfaces between layers coincide geometrically but do not share a mesh.
For a conformal mesh, partition or fragment the solids in the mesher.

## Building your own pipeline

The ready-made builders are short functions over reusable blocks. `add_lofted_solid` turns a list of `Station`
into a solid, and `add_layered_solids` adds concentric layers. `examples/custom_pipeline.py` runs an asymmetry
sweep with a user-defined two-layer wall. See [the API reference](docs/api.md).

## Tests

```bash
pip install -e .[test] "cadquery-ocp<8"
pytest
```

Tests run without SALOME: `tools/salome_shim` implements the GEOM operations used by AneuPy with OpenCASCADE.
The shim is a verification instrument. Please confirm final geometries in SALOME.

## License

AneuPy is released under the GNU General Public License, version 3 or later. See [LICENSE](LICENSE).
