"""Command-line entry point for use inside SALOME.

Example: ``./run_in_salome.sh aneupy_cli.py idealized --config params_idealized_automatic.json``.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))

from aneupy.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
