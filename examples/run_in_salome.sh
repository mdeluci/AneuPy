#!/usr/bin/env bash
# Run a Python command inside the SALOME environment.
#
# Usage:
#   SALOME_ROOT_DIR=/path/to/SALOME-9.11.0 ./run_in_salome.sh idealized_automatic.py
set -euo pipefail
: "${SALOME_ROOT_DIR:?Set SALOME_ROOT_DIR to the folder of your SALOME installation}"
exec "${SALOME_ROOT_DIR}/salome" shell -- python3 "$@"
