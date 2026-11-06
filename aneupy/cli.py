"""Command-line interface: ``python -m aneupy {idealized,image-derived}``."""

import argparse
import json
import os
import sys

from .idealized import IdealizedParameters
from .pipelines import (
    DEFAULT_FORMATS,
    build_idealized_model,
    build_image_derived_model,
    export_solids,
    prepare_image_derived_stations,
)
from .profiles import load_area_profile, read_table
from .validation import GeometryError

IMAGE_DERIVED_DEFAULTS = {"n_sections": None, "centerline_cutoff": 30.0, "profile_cutoff": 30.0,
                          "normal_mode": "tangent", "flip_profiles": False}


def build_parser():
    """Return the argument parser."""
    parser = argparse.ArgumentParser(prog="aneupy", description="Generate aneurysm geometries in SALOME.")
    commands = parser.add_subparsers(dest="command")
    commands.required = True

    idealized = commands.add_parser("idealized", help="idealized model from parameters")
    idealized.add_argument("--config", help="JSON file with parameters")
    for field in IdealizedParameters.FIELDS:
        idealized.add_argument("--" + field, type=float, help="overrides the configuration file")

    derived = commands.add_parser("image-derived", help="parametric model from a centerline and area profiles")
    derived.add_argument("--config", required=True, help="JSON file (see examples/)")

    for sub_parser in (idealized, derived):
        sub_parser.add_argument("--output-dir", default="aneupy_output", help="output directory")
        sub_parser.add_argument("--formats", nargs="+", default=list(DEFAULT_FORMATS),
                                help="any of step, iges, brep, stl, vtk")
    return parser


def _read_image_derived_config(path):
    """Return the validated image-derived configuration, with paths relative to its file."""
    try:
        with open(path) as handle:
            config = json.load(handle)
    except (OSError, ValueError) as error:
        raise GeometryError("Cannot read {}: {}".format(path, error))
    required = ("centerline_file", "wall_area_file", "lumen_area_file")
    missing = [key for key in required if key not in config]
    if missing:
        raise GeometryError("{} lacks: {}".format(path, ", ".join(missing)))
    unknown = sorted(set(config) - set(required) - set(IMAGE_DERIVED_DEFAULTS))
    if unknown:
        raise GeometryError("Unknown keys in {}: {}".format(path, ", ".join(unknown)))
    base = os.path.dirname(os.path.abspath(path))
    for key in required:
        config[key] = os.path.join(base, config[key])
    return config


def run(arguments):
    """Build a model from parsed arguments and return the paths written."""
    # Imported here because it is the only part of the package that needs SALOME.
    from .geometry import Domain

    domain = Domain()
    if arguments.command == "idealized":
        overrides = {field: getattr(arguments, field) for field in IdealizedParameters.FIELDS}
        if arguments.config:
            parameters = IdealizedParameters.from_json(arguments.config, **overrides)
        else:
            parameters = IdealizedParameters(**{key: value for key, value in overrides.items() if value is not None})
        names = build_idealized_model(domain, parameters)
        diagnostics = parameters.to_dict()
        study = "idealized_study.hdf"
    else:
        config = _read_image_derived_config(arguments.config)
        options = {key: config.get(key, default) for key, default in IMAGE_DERIVED_DEFAULTS.items()}
        stations = prepare_image_derived_stations(
            read_table(config["centerline_file"], 3), load_area_profile(config["wall_area_file"], "wall area"),
            load_area_profile(config["lumen_area_file"], "lumen area"), **options)
        names = build_image_derived_model(domain, stations)
        diagnostics = stations.diagnostics
        study = "image_derived_study.hdf"
    written = export_solids(domain, names, arguments.output_dir, arguments.formats)
    domain.save(os.path.join(arguments.output_dir, study))
    with open(os.path.join(arguments.output_dir, "diagnostics.json"), "w") as handle:
        json.dump(diagnostics, handle, indent=2, sort_keys=True)
    return written


def main(argv=None):
    """Entry point. Returns a process exit code."""
    arguments = build_parser().parse_args(argv)
    try:
        for path in run(arguments):
            print(path)
    except GeometryError as error:
        print("aneupy: error: {}".format(error), file=sys.stderr)
        return 2
    return 0
