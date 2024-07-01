# Aneupy

Aneupy is an open-source software tool designed to generate both idealized and patient-specific geometries of abdominal aortic aneurysms (AAA). It utilizes the Python interface of the [SALOME platform](https://www.salome-platform.org/) to provide versatile geometry creation options suitable for research and educational purposes.

## Features

Aneupy offers three main functionalities:

1. **Idealized Manual Geometry Generation (`Idealized_manual.py`)**:
   - Allows users to manually input the cross sections (XYZ locations) and radii to generate idealized AAA geometries.

2. **Idealized Automatic Geometry Generation (`Idealized_automatic.py`)**:
   - Automates the generation process using parameters specified in `Params_Idealized_Automatic.json`. This script simplifies the creation of idealized geometries by utilizing predefined parameters:
   - `length`: Total length of the aneurysm
   - `radius_nondilated`: Non-dilated radius of the aneurysm
   - `radius_dilated`: Radius of the aneurysm sac
   - `wall_thickness_intima`: Wall thickness of the intima
   - `wall_thickness_media`: Wall thickness of the media
   - `wall_thickness_adventitia`: Wall thickness of the adventitia
   - `wall_thickness_ILT`: Wall thickness of the intraluminal thrombus (ILT)
   - `x_shift`: Assymetry of the AAA sac in the X-direction
   - `y_shift`: Assymetry of the AAA sac in the Y-direction

3. **Patient-Specific Geometry Generation (`Patient_specific.py`)**:
   - Generates geometries from patient-specific data derived from centerlines, wall area, and length measurements of the AAA, with the option to include thrombus area if available.

## Installation

To use Aneupy, ensure that you have the SALOME platform installed with its Python interface enabled. Clone this repository to your local machine:


[![DOI](https://zenodo.org/badge/22895/jacobo-diaz/aneupy.svg)](https://zenodo.org/badge/latestdoi/22895/jacobo-diaz/aneupy)

<a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-nd/4.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/">Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License</a>.
