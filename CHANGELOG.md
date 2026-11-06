# Changelog

## 1.1.0

Revision made during the peer review of the AneuPy article.

### Fixed

- **Axial mapping of area profiles.** Radii were looked up with the global Z coordinate of each
  section instead of the arc length along the centerline, after a scaling that used only the maximum
  abscissa. On the example data this shifted the radii by up to 6.1 mm and left up to 40% of the measured
  profile unused. Profiles now map linearly onto arc length.
- **Centerline smoothing.** The documented smoothing was not applied: the spline was evaluated
  only at the input points, which returned them unchanged. The centerline is now smoothed.
- **Zero parameters.** `x_shift=0` silently became 4 mm, and zero wall thicknesses became 1 mm,
  because of truthiness tests. A straight, healthy aorta could not be requested.
- **Spurious lumen dilation.** When `radius_dilated == radius_nondilated`, the lumen neck was
  reduced by the intima thickness, which created a false dilation.
- **Length units.** STEP and IGES files were labelled in metres with millimetre values, so
  unit-aware software read a 100 mm model as 100 m. Both now carry the correct physical size.
- **Run scripts.** They contained personal absolute paths, `--use_tangent_normal` was always passed
  whatever the value of the setting, and `Idealized_automatic.py` could not import the geometry module.
- **Study file.** `SaveAs` received the study object as its multi-file flag, and the summary was
  named `*.hdf.cad`.
- **Input format.** Tables must be two or three columns separated by commas or whitespace. Malformed
  rows now give an error with the file and line.
- **Near-identity rotations.** Section rotations below 0.57 degrees were ignored.
- **Export formats.** `export_brep` was documented but missing.
- **Packaging.** `setup.py` found no package, and declared the MIT licence.
- **Licence.** The repository now states GPL-3.0-or-later everywhere.

### Added

- Library API separated from the example workflows, with `build_idealized_model`,
  `build_image_derived_model`, `add_lofted_solid` and `add_layered_solids`.
- Smoothing of centerlines and profiles with a physical cut-off wavelength.
- Runtime checks: positive radii, nested boundaries, `curvature x radius < 1`, intersecting section
  discs, section order, the volume of each solid against its sections, and material left by each cut.
- `IdealizedParameters.from_descriptors(beta, gamma, chi, ...)`.
- Rotation-minimizing section frames, which keep section seams aligned on non-planar centerlines.
- `python -m aneupy` command line, `diagnostics.json`, tests, continuous integration, and API documentation.

### Changed

- Idealized sections follow an analytic law, `R(z) = R0 + (Rsac - R0) cos^2(pi (z - zc) / LAAA)`. It passes
  through the former control sections and removes the oscillation of the previous global fit in the necks.
  Sections always include the sac ends and the midsection.
- The default surface method is `MakeThruSections`, because the `MakeFilling` fit failed for some section layouts.
- Output paths are made absolute before they reach SALOME.
- `Patient_specific.py` became the image-derived workflow, because circular sections from area profiles
  do not reproduce an individual anatomy.
- Names follow PEP 8: `add_circle2` was removed, `rotateX` became `rotate_x`, `OX_LCS` became `x_axis`,
  and `minBSplineDegree` became `min_degree`.
- The module `Geometry.py` became `aneupy/geometry.py`, and examples moved to `examples/`.
- `Domain.add_section` rejects duplicate names.
