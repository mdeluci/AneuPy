#!/bin/bash

# Set the SALOME installation directory
export SALOME_ROOT_DIR=$HOME/Desktop/SALOME-9.11.0

# Add SALOME binaries to the PATH
export PATH=$SALOME_ROOT_DIR/BINARIES-CO7/KERNEL/bin:$PATH

# Set the PYTHONPATH to include SALOME Python modules
export PYTHONPATH=$SALOME_ROOT_DIR/BINARIES-CO7/KERNEL/lib/python3.6/site-packages:$PYTHONPATH

# Set other necessary environment variables
export LD_LIBRARY_PATH=$SALOME_ROOT_DIR/BINARIES-CO7/KERNEL/lib:$LD_LIBRARY_PATH

export GEOMETRY_MODULE_DIR="/home/miguel/Desktop/aneupy-master/aneupy"
export GEOMETRY_DATA_DIR="/home/miguel/Desktop/aneupy-master/test/data"
export GEOMETRY_OUTPUT_DIR="/home/miguel/Desktop/aneupy-master/test/Geometry_Output/Patient_Specific"

# Set this to 1 for True or 0 for False
USE_TANGENT_NORMAL=0

# Conditional use of the tangent normal flag
if [ "$USE_TANGENT_NORMAL" -eq 1 ]; then
    use_tangent_normal="--use_tangent_normal"
else
    use_tangent_normal=""
fi

# Run the Python script within the SALOME environment with specified arguments
$SALOME_ROOT_DIR/salome shell -- python3 /home/miguel/Desktop/aneupy-master/test/Patient_specific.py \
--centerline_file "${GEOMETRY_DATA_DIR}/centerline2.txt" \
--wall_area_file "${GEOMETRY_DATA_DIR}/Wall_Area2.txt" \
--lumen_area_file "${GEOMETRY_DATA_DIR}/Lumen_Area2.txt" \
--use_tangent_normal

# To run this script: 
# ./Run_Patient_Specific.sh
