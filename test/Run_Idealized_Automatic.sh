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
export GEOMETRY_DATA_DIR="~/Desktop/aneupy-master/test/data"
export GEOMETRY_OUTPUT_DIR="~/Desktop/aneupy-master/test/Geometry_Output/Idealized_Manual"

# Run idealized automatic script
$SALOME_ROOT_DIR/salome shell -- python3 /home/miguel/Desktop/aneupy-master/test/Idealized_automatic.py "$@"

## To run this script you have two options. You can manually input the arguments or use the config.json:

# ./Run_Idealized_Automatic.sh  --length 120 --radius_nondilated 3 --radius_dilated 8 --wall_thickness_intima 0.5 --wall_thickness_media 0.3 --wall_thickness_adventitia 0.7 --wall_thickness_ILT 2 --x_shift 1.5 --y_shift 2.0
# ./Run_Idealized_Automatic.sh --config_file ./Params_Idealized_Automatic
