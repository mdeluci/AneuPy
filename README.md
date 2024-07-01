aneupy
=======

# Aneupy

Aneupy is an open-source software tool designed to generate both idealized and patient-specific geometries of abdominal aortic aneurysms (AAA). It utilizes the Python interface of the SALOME platform to provide versatile geometry creation options suitable for research and educational purposes.

## Features

Aneupy offers three main functionalities:

1. **Idealized Manual Geometry Generation (`Idealized_manual.py`)**:
   - Allows users to manually input the sections (XYZ locations) and radii to generate idealized AAA geometries.

2. **Idealized Automatic Geometry Generation (`Idealized_automatic.py`)**:
   - Automates the generation process using parameters specified in `Params_Idealized_Automatic.json`.

3. **Patient-Specific Geometry Generation (`Patient_specific.py`)**:
   - Generates geometries based on patient-specific data, including centerline details of the AAA, wall area, and optionally, the thrombus area.

## Installation

To use Aneupy, ensure that you have the SALOME platform installed with its Python interface enabled. Clone this repository to your local machine:

```bash
git clone https://github.com/yourgithubusername/aneupy.git
cd aneupy


[![DOI](https://zenodo.org/badge/22895/jacobo-diaz/aneupy.svg)](https://zenodo.org/badge/latestdoi/22895/jacobo-diaz/aneupy)

<a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-nd/4.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/">Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License</a>.
