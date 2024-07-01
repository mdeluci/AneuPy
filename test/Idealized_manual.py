# =============================================================================
#
# Idealized_manual.py
#
# Python module to generate idealized AAA geometries manually
#
# Jacobo Diaz - jdiaz@udc.es
# Mario de Lucio - mdeluci@purdue.edu
# 2024
#
# =============================================================================

#!/usr/bin/env python3

import os
import sys

# Access environment variables
geometry_module_dir = os.environ.get('GEOMETRY_MODULE_DIR', '../default/path/to/module')
geometry_data_dir = os.environ.get('GEOMETRY_DATA_DIR', '/default/path/to/data')
geometry_output_dir = os.environ.get('GEOMETRY_OUTPUT_DIR', '/default/path/to/output')

print(f"Module Directory: {geometry_module_dir}")
print(f"Data Directory: {geometry_data_dir}")
print(f"Output Directory: {geometry_output_dir}")

# Add the directory to the Python path
sys.path.append(geometry_module_dir)
# Now you can import the Geometry module
import Geometry
aneupy = Geometry

import salome
salome.salome_init()


d = aneupy.Domain()

d.add_section(name='a1', origin=[0., 0., 0.])
d.add_section(name='a1a', origin=[0., 0., 10.])
d.add_section(name='a2', origin=[0., 0., 20.])
d.add_section(name='a2a', origin=[0., 0., 30.])
d.add_section(name='a3', origin=[0., 0., 50.])
d.add_section(name='a4a', origin=[0., 0., 70.])
d.add_section(name='a4', origin=[0., 0., 80.])
d.add_section(name='a5a', origin=[0., 0., 90.])
d.add_section(name='a5', origin=[0., 0., 100.])

d.sections['a1'].add_circle(radius=5.)
d.sections['a1a'].add_circle(radius=5.)
d.sections['a2'].add_circle(radius=5.)
d.sections['a2a'].add_circle(radius=7.)
d.sections['a3'].add_circle(radius=12.5)
d.sections['a4a'].add_circle(radius=7.)
d.sections['a4'].add_circle(radius=5.)
d.sections['a5a'].add_circle(radius=5.)
d.sections['a5'].add_circle(radius=5.)

d.add_shell(name='aneurysm_outer', sections=['a1', 'a1a', 'a2', 'a2a', 'a3', 'a4a', 'a4', 'a5a', 'a5'],
            minBSplineDegree=10, maxBSplineDegree=20, approximation=True)

d.add_section(name='b1', origin=[0., 0., 0.])
d.add_section(name='b1a', origin=[0., 0., 10.])
d.add_section(name='b2', origin=[0., 0., 20.])
d.add_section(name='b2a', origin=[0., 0., 30.])
d.add_section(name='b3', origin=[0., 0., 50.])
d.add_section(name='b4a', origin=[0., 0., 70.])
d.add_section(name='b4', origin=[0., 0., 80.])
d.add_section(name='b5a', origin=[0., 0., 90.])
d.add_section(name='b5', origin=[0., 0., 100.])

d.sections['b1'].add_circle(radius=4.5)
d.sections['b1a'].add_circle(radius=4.5)
d.sections['b2'].add_circle(radius=4.5)
d.sections['b2a'].add_circle(radius=6.7)
d.sections['b3'].add_circle(radius=10.3)
d.sections['b4a'].add_circle(radius=6.7)
d.sections['b4'].add_circle(radius=4.5)
d.sections['b5a'].add_circle(radius=4.5)
d.sections['b5'].add_circle(radius=4.5)

d.add_shell(name='aneurysm_inner', sections=['b1', 'b1a', 'b2', 'b2a', 'b3', 'b4a', 'b4', 'b5a', 'b5'],
            minBSplineDegree=10, maxBSplineDegree=20, approximation=True)


d.add_solid_from_shell(name='aneurysm_outer', shell='aneurysm_outer')
d.add_solid_from_shell(name='aneurysm_fluid', shell='aneurysm_inner')
d.add_solid_from_cut(name='aneurysm_solid', solids=['aneurysm_outer', 'aneurysm_fluid'])


def export_files(d):
    # Define file types and corresponding method in a dictionary for cleaner execution
    file_types = {
        'iges': ['aneurysm_solid', 'aneurysm_fluid'],
        'stl': ['aneurysm_solid', 'aneurysm_fluid'],
        'step': ['aneurysm_solid', 'aneurysm_fluid']
    }
    # Loop through each file type and export accordingly
    for f_type, solids in file_types.items():
        for solid in solids:
            file_path = os.path.join(geometry_output_dir, f'{solid}.{f_type}')
            export_method = getattr(d, f'export_{f_type}')
            export_method(solid=solid, file=file_path)

def save_files(d):
    """Save study files."""
    study_file_path = os.path.join(geometry_output_dir, 'idealized_manual_study.hdf')
    d.save(study_file_path)
    print(f"Study saved successfully to {study_file_path}")

export_files(d)
save_files(d)

print("Success! The AAA geometry creation has been completed with precision. Thank you for your collaboration.")
