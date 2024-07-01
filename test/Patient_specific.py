#!/usr/bin/env python3

import os
import numpy as np
import scipy.interpolate
import sys
from salome.geom import geomBuilder
import math
from scipy.interpolate import interp1d
import copy
import argparse

# Access environment variables
geometry_module_dir = os.environ.get('GEOMETRY_MODULE_DIR', '../default/path/to/module')
geometry_data_dir = os.environ.get('GEOMETRY_DATA_DIR', '/default/path/to/data')
geometry_output_dir = os.environ.get('GEOMETRY_OUTPUT_DIR', '/default/path/to/output')

print(f"Module Directory: {geometry_module_dir}")
print(f"Data Directory: {geometry_data_dir}")
print(f"Output Directory: {geometry_output_dir}")

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description="Process geometry data and configuration settings.")
parser.add_argument('--centerline_file', type=str, help='Path to the centerline file')
parser.add_argument('--wall_area_file', type=str, help='Path to the wall area file')
parser.add_argument('--lumen_area_file', type=str, help='Path to the lumen area file')
parser.add_argument('--use_tangent_normal', type=bool, default=False, help='Whether to use tangent normal (True) or upward normal in Z-direction (False)')

# Parse the arguments
args = parser.parse_args()

# Example use of arguments
centerline_file = args.centerline_file
wall_area_file = args.wall_area_file
lumen_area_file = args.lumen_area_file
use_tangent_normal = args.use_tangent_normal

print(f"Using Centerline File: {centerline_file}")
print(f"Using Wall Area File: {wall_area_file}")
print(f"Using Lumen Area File: {lumen_area_file}")
print(f"Using Tangent Normal: {use_tangent_normal}")

# Add the directory to the Python path
sys.path.append(geometry_module_dir)
sys.path.append(geometry_data_dir)

# Import the Geometry module
import Geometry
aneupy = Geometry
geompy = geomBuilder.New()

import salome
salome.salome_init()

def process_centerline_xyz_data(filepath, num_points=1):
    # Load the data from the file
    def load_data(filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"The file {filepath} does not exist. Please check the path.")
        data = np.loadtxt(filepath, delimiter=',')
        return data
    # Perform spline interpolation and generate additional points
    def interpolate_points(data, num_points):
        X, Y, Z = data[:,0], data[:,1], data[:,2]
        t = np.linspace(0, 1, len(X))
        t_new = np.linspace(0, 1, num_points * (len(X) - 1) + 1)
        spl_x = scipy.interpolate.CubicSpline(t, X)
        spl_y = scipy.interpolate.CubicSpline(t, Y)
        spl_z = scipy.interpolate.CubicSpline(t, Z)
        X_new = spl_x(t_new)
        Y_new = spl_y(t_new)
        Z_new = spl_z(t_new)
        return np.column_stack((X_new, Y_new, Z_new))
    
    # Load data
    data = load_data(filepath)
    interpolated_data = interpolate_points(data, num_points)

    # Save the interpolated data
    np.savetxt(f'{geometry_data_dir}/interpolated_centerline.txt', interpolated_data, delimiter=',', fmt='%f')

    # Load and create vertex objects
    points = []
    with open(f'{geometry_data_dir}/interpolated_centerline.txt', 'r') as file:
        for line in file:
            x, y, z = map(float, line.strip().split(','))
            vertex = geompy.MakeVertex(x, y, z)
            points.append(vertex)

    # Optionally print the points
    #for point in points:
        #print(point)
    # Create an interpolated spline as AAA centerline
    spline = geompy.MakeInterpol(points)
    geompy.addToStudy(spline, "InterpolatedSpline")
    
    # Compute tangent vectors if needed
    tangents = []
    coords = [geompy.PointCoordinates(pt) for pt in points]
    for i in range(len(coords)):
        if i == 0:
            tangent = [coords[1][j] - coords[0][j] for j in range(3)]
        elif i == len(coords) - 1:
            tangent = [coords[-1][j] - coords[-2][j] for j in range(3)]
        else:
            tangent = [(coords[i + 1][j] - coords[i - 1][j]) / 2.0 for j in range(3)]
        magnitude = math.sqrt(sum(ti**2 for ti in tangent))
        normalized_tangent = [t / magnitude for t in tangent]
        tangents.append(normalized_tangent)

    # Calculate the length of the spline
    length = geompy.BasicProperties(spline)[0]  # BasicProperties returns a tuple (Length, Area, Volume)
    print(f"The length of the spline is: {length} units")

    return spline, points, tangents, length  # Return the spline, points, and tangents for further use


def create_geometry_from_area(d,file_path, shell_name, points, L_model,prefix):
    # Load and preprocess data
    def load_and_preprocess_data(file_path, L_model):
        data = np.loadtxt(file_path, delimiter=',')
        Area_data = data[:, 1]  # Assuming second column is area in mm^2
        R_data = np.sqrt(Area_data / np.pi)

        Z_data = data[:, 0]
        Z_normalized = Z_data / Z_data.max() * L_model

        interp_func = interp1d(Z_normalized, R_data, kind='linear', fill_value="extrapolate")

        def positive_radius(z):
            return max(0, interp_func(z))
        
        return positive_radius

    radius_function = load_and_preprocess_data(file_path, L_model)

    # Add sections and circles
    section_names = []
    total_sections = len(points)
    prefix = f"{prefix}"

    for i, point in enumerate(points):
        section_name = f'{prefix}{i}'
        coords = geompy.PointCoordinates(point)
        d.add_section(name=section_name, origin=coords)
        print(f"Created Section {section_name} at {coords}")

    # Ensure points are assigned to each relevant section
    for i in range(total_sections):
        name = f'{prefix}{i}'
        coords = geompy.PointCoordinates(points[i])
        z_position = coords[2]
        interpolated_radius = radius_function(z_position)  # Ensure radius_function is defined and accessible
        if use_tangent_normal:
            normal = tangents[i]  # Use the tangent normal
        else:
            normal = [0, 0, 1]  # Use the standard upward normal

        circle_center = points[i]

        if name in d.sections:
            d.sections[name].add_circle2(circle_center=circle_center, normal=normal, radius=float(interpolated_radius))
            print(f"Adding Circle '{section_name}' at Z={z_position} with radius={interpolated_radius}")

    section_names = [f'{prefix}{i}' for i in range(total_sections)]
    d.add_shell(name=f'{prefix}_shell',sections=section_names,minBSplineDegree=10,maxBSplineDegree=20,approximation=True)

d = aneupy.Domain()

# Process the first set of geometry data
spline, points, tangents, length = process_centerline_xyz_data(centerline_file, 1)
geometry_data1 = create_geometry_from_area(d, wall_area_file, 'aneurysm_outer_shell', points, length, prefix='aneurysm_outer')
d.add_solid_from_shell(name='aneurysm_outer', shell='aneurysm_outer_shell')

# Process the second set of geometry data
spline2, points2, tangents2, length2 = process_centerline_xyz_data(centerline_file, 1)
geometry_data2 = create_geometry_from_area(d, lumen_area_file, 'ILT_shell', points2, length2, prefix='ILT')
d.add_solid_from_shell(name='Lumen', shell='ILT_shell')

# Cut solids (Boolean operation to substract solids)
d.add_solid_from_cut(name='ILT', solids=['aneurysm_outer', 'Lumen'])

# Function to export files
def export_files(d):
    # Define solids and their respective formats for export
    exports = {
        'IGES': ['ILT', 'Lumen'],
        'STL': ['ILT', 'Lumen'],
        'STEP': ['ILT', 'Lumen']
    }
  # Loop through each format and export each solid
    for format_type, solids in exports.items():
        for solid in solids:
            file_path = os.path.join(geometry_output_dir, f"{solid}.{format_type.lower()}")
            export_method = getattr(d, f"export_{format_type.lower()}")
            export_method(solid=solid, file=file_path)
            print(f"{format_type} file exported for {solid}: {file_path}")
# Assuming `d` is your object that has the export methods defined
export_files(d)

def save_files(d):
    """Save study files."""
    study_file_path = os.path.join(geometry_output_dir, 'Patient_specific_study.hdf')
    d.save(study_file_path)
    print(f"Study saved successfully to {study_file_path}")

save_files(d)
print("Success! The AAA geometry creation has been completed with precision. Thank you for your collaboration.")
