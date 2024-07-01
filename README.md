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

Before you can use Aneupy, ensure that your system meets the following prerequisites:

### Prerequisites

1. **Python 3**:
   - Aneupy requires Python 3. Ensure you have Python 3 installed on your system. You can download Python 3 from the [official Python website](https://www.python.org/downloads/).
   - To verify Python is installed, run the following command in your terminal or command prompt:
     ```bash
     python --version
     # or
     python3 --version
     ```
     Ensure that the output indicates a Python 3 version.

2. **SALOME**:
   - Aneupy utilizes the SALOME platform for geometric modeling. Install SALOME version 9.11.0 or newer. You can download it from the [SALOME website](https://www.salome-platform.org/?page_id=2430).
   - Follow the installation instructions provided on the SALOME website to ensure it is correctly installed on your system.

### Installing Aneupy

Once you have the prerequisites installed, you can install Aneupy by cloning its repository:

```bash
git clone https://github.com/yourgithubusername/aneupy.git
cd aneupy
```

[![DOI](https://zenodo.org/badge/22895/jacobo-diaz/aneupy.svg)](https://zenodo.org/badge/latestdoi/22895/jacobo-diaz/aneupy)

<a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-nd/4.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/">Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License</a>.
