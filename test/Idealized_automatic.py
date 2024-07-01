#!/usr/bin/env python3

import os
import sys
import argparse
import json

# Access environment variables
geometry_module_dir = os.environ.get('GEOMETRY_MODULE_DIR', '../default/path/to/module')
geometry_data_dir = os.environ.get('GEOMETRY_DATA_DIR', '/default/path/to/data')
geometry_output_dir = os.environ.get('GEOMETRY_OUTPUT_DIR', '/default/path/to/output')

print(f"Module Directory: {geometry_module_dir}")
print(f"Data Directory: {geometry_data_dir}")
print(f"Output Directory: {geometry_output_dir}")

# Now you can import the Geometry module
import Geometry
aneupy = Geometry

import salome
salome.salome_init()

def parse_args_from_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return argparse.Namespace(**data)

parser = argparse.ArgumentParser(description="Create an aneurysm model")
parser.add_argument('--length', type=float, required=False, help='Total length of the aneurysm')
parser.add_argument('--radius_nondilated', type=float, required=False, help='Non-dilated radius of the aneurysm')
parser.add_argument('--radius_dilated', type=float, required=False, help='Radius of the aneurysm sac')
parser.add_argument('--wall_thickness_intima', type=float, required=False, help='Wall thickness of the intima')
parser.add_argument('--wall_thickness_media', type=float, required=False, help='Wall thickness of the media')
parser.add_argument('--wall_thickness_adventitia', type=float, required=False, help='Wall thickness of the adventitia')
parser.add_argument('--wall_thickness_ILT', type=float, required=False, help='Wall thickness of the ILT (thrombus)')
parser.add_argument('--x_shift', type=float, required=False, help='Assymetry of AAA sac in X-direction')
parser.add_argument('--y_shift', type=float, required=False, help='Assymetry of AAA sac in Y-direction')
parser.add_argument('--config_file', type=str, required=False, help='Path to configuration file containing all parameters')

args = parser.parse_args()

if args.config_file:
    args = parse_args_from_file(args.config_file)

Length = args.length if args.length else 100.0  # Default value if not specified
R0 = args.radius_nondilated if args.radius_nondilated else 5.0
wall_thickness_intima = args.wall_thickness_intima if args.wall_thickness_intima else 1.0
wall_thickness_media = args.wall_thickness_media if args.wall_thickness_media else 1.0
wall_thickness_adventitia = args.wall_thickness_adventitia if args.wall_thickness_adventitia else 1.0
ILT_thickness = args.wall_thickness_ILT if args.wall_thickness_ILT else 0.0
R_sac = args.radius_dilated if args.radius_dilated else 12.0
x_shift = args.x_shift if args.x_shift else 4.0
y_shift = args.y_shift if args.y_shift else 0.0

n_sections = 11

def interpolate_radius(R_nondilated, R_dilated):
    """
    Interpolates the radius between the non-dilated section (R0) and the dilated section (R_dilated).

    Parameters:
    R0 (float): Radius of the non-dilated section.
    R_dilated (float): Radius of the dilated section.

    Returns:
    float: Interpolated midpoint radius.
    """
    R_mid = (R_nondilated + R_dilated) / 2
    return R_mid


R_mid= interpolate_radius(R0,R_sac)

def add_sections(d, total_length, num_sections, prefix='a'):
    step = total_length / (num_sections - 1)
    for i in range(num_sections):
        length = total_length * (i / (num_sections - 1))
        name = f'{prefix}{i}'
        print(f"Adding section: {name}, origin: [0., 0., {length}]")  # Debug print
        d.add_section(name=name, origin=[0., 0., length])

	# Adding an extra control point at the beginning for a smooth transition
        if i == 0:
	    # First extra section at one-third
            extra_length1 = length + step / 3
            extra_name1 = f'{prefix}{i}a'
            print(f"Adding first extra section: {extra_name1}, origin: [0., 0., {extra_length1}]")  # Debug print
            d.add_section(name=extra_name1, origin=[0., 0., extra_length1])

	    # Second extra section at one-third
            extra_length2 = length + 2 * step / 3
            extra_name2 = f'{prefix}{i}b'
            print(f"Adding second extra section: {extra_name2}, origin: [0., 0., {extra_length2}]")  # Debug print
            d.add_section(name=extra_name2, origin=[0., 0., extra_length2])

        mid_section = num_sections // 2  # The middle section
        if i == mid_section-1:
            print(f"Adding shifted mid-section-1 -> origin: [{x_shift}/2,{y_shift}/2, length]")  # Debug print
            d.add_section(name=name, origin=[x_shift/2, y_shift/2, length])

        if i == mid_section:
            print(f"Adding shifted mid-section -> origin: [{x_shift}, {y_shift}, length]")  # Debug print
            d.add_section(name=name, origin=[x_shift, y_shift, length])

        if i == mid_section+1:
            print(f"Adding shifted mid-section+1 -> origin: [{x_shift}/2, {y_shift}/2, length]")  # Debug print
            d.add_section(name=name, origin=[x_shift/2, y_shift/2, length])

	# Adding an extra control point at the beginning for a smooth transition
        if i == num_sections - 2:
            extra_index3 = i + 1  # This is the original index of the last section
            extra_index4 = i + 1  # This will be the new index for an additional extra section

            # First extra section, halfway between the second-to-last and last original section
            extra_name3 = f'{prefix}{extra_index3}a'
            extra_length3 = length + step / 2
            print(f"Adding first extra section just before the last: {extra_name3}, origin: [0., 0., {extra_length3}]")
            d.add_section(name=extra_name3, origin=[0., 0., extra_length3])

            # Second extra section, halfway between the second-to-last and last original section
            extra_name4 = f'{prefix}{extra_index4}b'
            extra_length4 = length + 3 * step / 4
            print(f"Adding first extra section just before the last: {extra_name4}, origin: [0., 0., {extra_length4}]")
            d.add_section(name=extra_name4, origin=[0., 0., extra_length4])

           

def add_circles(d, num_sections, R0, R_sac, wall_thickness, prefix='a'):
    mid_section = num_sections // 2  # The middle section
    transition_range = 2  # Number of sections to transition on either side of the middle
    radii_map = {}
    
    for i in range(num_sections):
        if i == mid_section:
            radii_map[i] = R_sac
        elif i in range(mid_section - transition_range, mid_section) or i in range(mid_section + 1, mid_section + transition_range + 1):
            if i < mid_section:
                radius = R_sac + (R0 - R_sac) * (mid_section - i) / transition_range
            else:
                radius = R_sac + (R0 - R_sac) * (i - mid_section) / transition_range
            radii_map[i] = radius
        else:
            radii_map[i] = R0

    for i in range(num_sections):
        name = f'{prefix}{i}'
        radius = radii_map[i]
        # Adjust wall thickness based on the section
        if prefix == 'fluid':
            if i == mid_section-1:
                # Apply special thickness only at the mid_section
                radius -= ILT_thickness/2
            elif i == mid_section:
                # Apply special thickness only at the mid_section
                radius -= ILT_thickness
            elif i == mid_section+1:
                # Apply special thickness only at the mid_section
                radius -= ILT_thickness/2
            else:
                # Apply normal thickness elsewhere
                radius -= 0.0 if radius != R_sac else (wall_thickness)

        if name in d.sections:
            print(f"Adding circle to section {name}: radius = {radius}")  # Debug print
            d.sections[name].add_circle(radius=radius)

        # Adding circle to the extra control point at the beginning
        if i == 0:
            # First extra section
            extra_name1 = f'{prefix}{i}a'
            if extra_name1 in d.sections:
                print(f"Adding circle to first extra section at the beginning {extra_name1}: radius = {radius}")  # Debug print
                d.sections[extra_name1].add_circle(radius=radius)
            # Second extra section
            extra_name2 = f'{prefix}{i}b'
            if extra_name2 in d.sections:
                print(f"Adding circle to first extra section at the beginning {extra_name2}: radius = {radius}")  # Debug print
                d.sections[extra_name2].add_circle(radius=radius)

        # Adding circle to the extra control point at the beginning
 	# Adding circles to the extra sections just before the last original section
        if i == num_sections - 2:
            extra_index3 = i + 1  # Corrected to define extra_index1 before using it
            extra_name3 = f'{prefix}{extra_index3}a'
            if extra_name3 in d.sections:
                print(f"Adding circle to extra section just before the last {extra_name3}: radius = {radius}")
                d.sections[extra_name3].add_circle(radius=radius)

            extra_index4 = i + 1  # Corrected to define extra_index2 before using it
            extra_name4 = f'{prefix}{extra_index4}b'
            if extra_name4 in d.sections:
                print(f"Adding circle to extra section just before the last {extra_name4}: radius = {radius}")
                d.sections[extra_name4].add_circle(radius=radius)


def add_shell(d, num_sections, prefix='a'):
    section_names = [f'{prefix}{i}' for i in range(num_sections)]
    # Insert the first extra section after the first section
    section_names.insert(1, f'{prefix}0a')
    # Insert the second extra section after the first extra section
    section_names.insert(2, f'{prefix}0b')
    # Correctly place the extra section before the last section
    # Since 'a10' will be the last section, we insert 'a10a' just before it
    extra_section_index1 = num_sections - 1 + 2  # account for two extra sections added after 'a0'
    extra_section_index2 = extra_section_index1 + 1

    # Insert the first extra section ('a10a') before 'a10'
    section_names.insert(extra_section_index1, f'{prefix}{num_sections-1}a')
    # Insert the second extra section ('a10b') right after 'a10a'
    section_names.insert(extra_section_index2, f'{prefix}{num_sections-1}b')

    # Expanded inline conditional logic for determining shell name
    shell_name = ('aneurysm_inner' if prefix == 'fluid' else
                 ('intima_outer' if prefix == 'intima' else
                 ('media_outer' if prefix == 'media' else
                 ('adventitia_outer' if prefix == 'adventitia' else
                 'default_shell_name'))))

    print(f"Adding shell: {shell_name}, sections: {section_names}")  # Debug print
    d.add_shell(name=shell_name, sections=section_names, minBSplineDegree=10, maxBSplineDegree=20, approximation=True)

def add_solids(d):
    print("Adding solids from shells")  # Debug print
    d.add_solid_from_shell(name='intima_outer', shell='intima_outer')
    d.add_solid_from_shell(name='aneurysm_fluid', shell='aneurysm_inner')
    d.add_solid_from_cut(name='aneurysm_intima_ILT', solids=['intima_outer', 'aneurysm_fluid'])
    d.add_solid_from_shell(name='media_outer', shell='media_outer')
    d.add_solid_from_cut(name='media_solid', solids=['media_outer', 'intima_outer'])
    d.add_solid_from_shell(name='adventitia_outer', shell='adventitia_outer')
    d.add_solid_from_cut(name='adventitia_solid', solids=['adventitia_outer', 'media_outer'])

def export_files(d):
    # Define file types and corresponding method in a dictionary for cleaner execution
    file_types = {
        'iges': ['aneurysm_intima_ILT', 'aneurysm_fluid', 'media_solid', 'adventitia_solid'],
        'stl': ['aneurysm_fluid', 'aneurysm_intima_ILT', 'media_solid', 'adventitia_solid'],
        'step': ['aneurysm_fluid', 'aneurysm_intima_ILT', 'media_solid', 'adventitia_solid']
    }
    # Loop through each file type and export accordingly
    for f_type, solids in file_types.items():
        for solid in solids:
            file_path = os.path.join(geometry_output_dir, f'{solid}.{f_type}')
            export_method = getattr(d, f'export_{f_type}')
            export_method(solid=solid, file=file_path)

def save_files(d):
    """Save study files."""
    study_file_path = os.path.join(geometry_output_dir, 'idealized_automatic_study.hdf')
    d.save(study_file_path)
    print(f"Study saved successfully to {study_file_path}")

d = aneupy.Domain()

# Example class definitions and usage:
class Section:
    def __init__(self, name):
        self.name = name

    def add_circle(self, radius):
        print(f"Adding circle to section {self.name}: radius = {radius}")

class D:
    def __init__(self):
        self.sections = {}

    def add_section(self, name, origin):
        self.sections[name] = Section(name)
        print(f"Adding section: {name}, origin: {origin}")

    def add_shell(self, name, sections, minBSplineDegree, maxBSplineDegree, approximation):
        print(f"Adding shell: {name}, sections: {sections}, "
              f"minBSplineDegree: {minBSplineDegree}, maxBSplineDegree: {maxBSplineDegree}, approximation: {approximation}")

    def add_solid_from_shell(self, name, shell):
        print(f"Adding solid from shell: {name}, shell: {shell}")

    def add_solid_from_cut(self, name, solids):
        print(f"Adding solid from cut: {name}, solids: {solids}")

    def export_iges(self, solid, file):
        print(f"Exporting IGES: solid = {solid}, file = {file}")

    def export_stl(self, solid, file):
        print(f"Exporting STL: solid = {solid}, file = {file}")

    def export_step(self, solid, file):
        print(f"Exporting STEP: solid = {solid}, file = {file}")

# Adding 'fluid' sections for fluid
printing = D()
add_sections(d, total_length=Length, num_sections=n_sections, prefix='fluid')
add_sections(printing, total_length=Length, num_sections=n_sections, prefix='fluid')
add_circles(d, num_sections=n_sections, R0=R0, R_sac=R_sac, wall_thickness=wall_thickness_intima, prefix='fluid')
add_circles(printing, num_sections=n_sections, R0=R0, R_sac=R_sac, wall_thickness=wall_thickness_intima, prefix='fluid')
add_shell(d, num_sections=n_sections, prefix='fluid')
add_circles(printing, num_sections=n_sections, R0=R0, R_sac=R_sac, wall_thickness=wall_thickness_intima, prefix='fluid')

# Adding 'intima' sections for solid domain intima and ILT
R0_intima=R0+wall_thickness_intima
R_sac_intima=R_sac+wall_thickness_intima

add_sections(d, total_length=Length, num_sections=n_sections, prefix='intima')
add_sections(printing, total_length=Length, num_sections=n_sections, prefix='intima')
add_circles(d, num_sections=n_sections, R0=R0_intima, R_sac=R_sac_intima, wall_thickness=wall_thickness_intima, prefix='intima')
add_circles(printing, num_sections=n_sections, R0=R0_intima, R_sac=R_sac_intima, wall_thickness=wall_thickness_intima, prefix='intima')
add_shell(d, num_sections=n_sections, prefix='intima')
add_shell(printing, num_sections=n_sections, prefix='intima')

# Adding 'media' sections
printing = D()
R0_media=R0+wall_thickness_intima+wall_thickness_media
R_sac_media=R_sac+wall_thickness_intima+wall_thickness_media

add_sections(d, total_length=Length, num_sections=n_sections, prefix='media')
add_sections(printing, total_length=Length, num_sections=n_sections, prefix='media')
add_circles(d, num_sections=n_sections, R0=R0_media, R_sac=R_sac_media, wall_thickness=wall_thickness_media, prefix='media')
add_circles(printing, num_sections=n_sections, R0=R0_media, R_sac=R_sac_media, wall_thickness=wall_thickness_media, prefix='media')
add_shell(d, num_sections=n_sections, prefix='media')
add_circles(printing, num_sections=n_sections, R0=R0_media, R_sac=R_sac_media, wall_thickness=wall_thickness_media, prefix='media')

# Adding 'adventitia' sections
printing = D()
R0_adventitia=R0+wall_thickness_intima+wall_thickness_media+wall_thickness_adventitia
R_sac_adventitia=R_sac+wall_thickness_intima+wall_thickness_media+wall_thickness_adventitia

add_sections(d, total_length=Length, num_sections=n_sections, prefix='adventitia')
add_sections(printing, total_length=Length, num_sections=n_sections, prefix='adventitia')
add_circles(d, num_sections=n_sections, R0=R0_adventitia, R_sac=R_sac_adventitia, wall_thickness=wall_thickness_adventitia, prefix='adventitia')
add_circles(printing, num_sections=n_sections, R0=R0_adventitia, R_sac=R_sac_adventitia, wall_thickness=wall_thickness_adventitia, prefix='adventitia')
add_shell(d, num_sections=n_sections, prefix='adventitia')
add_circles(printing, num_sections=n_sections, R0=R0_adventitia, R_sac=R_sac_adventitia, wall_thickness=wall_thickness_adventitia, prefix='adventitia')

add_solids(d)
add_solids(printing)
export_files(d)
export_files(printing)
save_files(d)
print("Success! The AAA geometry creation has been completed with precision. Thank you for your collaboration.")
