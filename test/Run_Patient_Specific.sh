#!/bin/bash

# Set the SALOME installation directory
export SALOME_ROOT_DIR=$HOME/Desktop/SALOME-9.11.0

# Add SALOME binaries to the PATH
export PATH=$SALOME_ROOT_DIR/BINARIES-CO7/KERNEL/bin:$PATH

# Set the PYTHONPATH to include SALOME Python modules
export PYTHONPATH=$SALOME_ROOT_DIR/BINARIES-CO7/KERNEL/lib/python3.6/site-packages:$PYTHONPATH

# Set other necessary environment variables
export LD_LIBRARY_PATH=$SALOME_ROOT_DIR/BINARIES-CO7/KERNEL/lib:$LD_LIBRARY_PATH

# Define and export directories
export GEOMETRY_MODULE_DIR="../aneupy-master/aneupy"
export GEOMETRY_DATA_DIR="/home/miguel/Desktop/aneupy-master/test/data"
export GEOMETRY_OUTPUT_DIR="/home/miguel/Desktop/aneupy-master/test/Geometry_Output/Patient_Specific"

# Define file paths
centerline_file="/home/miguel/Desktop/aneupy-master/test/data/centerline1.txt"
wall_area_file="/home/miguel/Desktop/aneupy-master/test/data/Wall_Area.txt"
lumen_area_file="/home/miguel/Desktop/aneupy-master/test/data/Lumen_Area.txt"
use_tangent_normal=false


# Run the Python script within the SALOME environment with specified arguments
$SALOME_ROOT_DIR/salome shell -- python3 /home/miguel/Desktop/aneupy-master/test/Patient_specific.py \
--centerline_file "$centerline_file" \
--wall_area_file "$wall_area_file" \
--lumen_area_file "$lumen_area_file" \
--use_tangent_normal "$use_tangent_normal"

# To run this script: 
# ./Run_Patient_Specific.sh
