import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "examples", "data")


@pytest.fixture(scope="session")
def data_dir():
    return DATA


@pytest.fixture(scope="session")
def geometry():
    """Return aneupy.geometry on the OpenCASCADE test shim."""
    pytest.importorskip("OCP")
    sys.path.insert(0, os.path.join(ROOT, "tools", "salome_shim"))
    return importlib.import_module("aneupy.geometry")
