"""Regenerate Figures 1, 3 and 4 of the article and the values of its smoothing table.

Geometry comes from AneuPy itself. Without SALOME, the script uses tools/salome_shim, which
reproduces GEOM's operations with OpenCASCADE. Requires pyvista and matplotlib.

Usage: python tools/make_paper_figures.py OUTPUT_DIRECTORY
"""
import json
import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools", "salome_shim")]

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pyvista as pv  # noqa: E402
from OCP.BRepMesh import BRepMesh_IncrementalMesh  # noqa: E402
from OCP.StlAPI import StlAPI_Writer  # noqa: E402

from aneupy import (IdealizedParameters, build_idealized_model, build_image_derived_model,  # noqa: E402
                    load_area_profile, prepare_image_derived_stations)
from aneupy.centerline import Centerline  # noqa: E402
from aneupy.geometry import Domain  # noqa: E402
from aneupy.profiles import read_table  # noqa: E402

pv.OFF_SCREEN = True
plt.rcParams.update({"font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm",
                     "axes.formatter.use_mathtext": True, "axes.unicode_minus": False, "font.size": 8,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.5, "ytick.major.width": 0.5})

COLORS = {"intima": "#a33a3a", "media": "#14578c", "adventitia": "#4a9a82", "lumen": "#d1cfb8", "line": "#26332f"}
DATA = os.path.join(ROOT, "examples", "data")
CASES = {"1": ("centerline1.txt", "Wall_Area.txt", "Lumen_Area.txt", True),
         "2": ("centerline2.txt", "Wall_Area2.txt", "Lumen_Area2.txt", False)}


def to_polydata(shape, path):
    """Tessellate a shape finely and return it as PolyData."""
    mesh = BRepMesh_IncrementalMesh(shape, 0.02, False, 0.08, True)
    mesh.Perform()
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    writer.Write(shape, path)
    return pv.read(path).clean()


def render(meshes, path, position, roll=0.0, size=(1500, 1000), zoom=1.0, specular=0.25):
    """Render (mesh, color) pairs to a transparent PNG."""
    plotter = pv.Plotter(off_screen=True, window_size=list(size))
    plotter.set_background("white")
    for mesh, color in meshes:
        surface = mesh.compute_normals(feature_angle=35.0, split_vertices=True, auto_orient_normals=True)
        plotter.add_mesh(surface, color=color, smooth_shading=True, specular=specular, specular_power=25,
                         ambient=0.25, diffuse=0.75)
    center = np.mean([np.array(mesh.center) for mesh, _ in meshes], axis=0)
    plotter.camera.focal_point = tuple(center)
    plotter.camera.position = tuple(center + np.array(position))
    plotter.camera.up = (0.0, 0.0, 1.0)
    plotter.camera.roll = plotter.camera.roll + roll
    plotter.reset_camera(bounds=None)
    plotter.camera.zoom(zoom)
    plotter.enable_anti_aliasing("ssaa")
    plotter.screenshot(path, transparent_background=True)
    plotter.close()


def trim(path):
    """Crop the transparent border of an image."""
    image = mpimg.imread(path)
    alpha = image[:, :, 3] > 0.01
    rows = np.nonzero(alpha.any(axis=1))[0]
    columns = np.nonzero(alpha.any(axis=0))[0]
    cropped = image[rows[0]:rows[-1] + 1, columns[0]:columns[-1] + 1]
    mpimg.imsave(path, cropped)
    return cropped


def show(axis, image):
    """Show an image without axes."""
    axis.imshow(image, interpolation="lanczos")
    axis.set_axis_off()


def cross_section(axis, parameters, title):
    """Draw the midsection with its layers and the neck lumen."""
    outer = parameters.radius_dilated
    center = (parameters.shift, 0.0)
    layers = [(outer + parameters.wall_thickness_intima + parameters.wall_thickness_media
               + parameters.wall_thickness_adventitia, COLORS["adventitia"]),
              (outer + parameters.wall_thickness_intima + parameters.wall_thickness_media, COLORS["media"]),
              (outer + parameters.wall_thickness_intima, COLORS["intima"]),
              (outer - parameters.ilt_thickness, COLORS["lumen"])]
    for radius, color in layers:
        axis.add_patch(mpatches.Circle(center, radius, facecolor=color, edgecolor="none"))
    axis.add_patch(mpatches.Circle((0.0, 0.0), parameters.radius_nondilated, fill=False, linestyle=(0, (1, 1.5)),
                                   edgecolor="black", linewidth=0.7))
    limit = max(layers[0][0] + parameters.shift, parameters.radius_nondilated) * 1.03
    axis.set_xlim(parameters.shift - limit, parameters.shift + limit)
    axis.set_ylim(-limit, limit)
    axis.set_aspect("equal")
    axis.set_axis_off()
    axis.text(0.5, -0.09, title, transform=axis.transAxes, ha="center", va="center", fontsize=8)


def build_idealized(parameters, work, tag):
    """Build an idealized model and return its surfaces in axial order of the layers."""
    domain = Domain()
    build_idealized_model(domain, parameters)
    names = ("aneurysm_fluid", "intima_outer", "media_outer", "adventitia_outer")
    boundaries = {}
    for name in ("aneurysm_fluid", "aneurysm_intima_ILT_outer", "media_solid_outer", "adventitia_solid_outer"):
        boundaries[name] = to_polydata(domain.solids[name].geom.shape, os.path.join(work, "{}_{}.stl".format(tag, name)))
    del names
    return boundaries


def half_model(boundaries):
    """Return half of each boundary, closed on the plane y = 0, ready for rendering."""
    pieces = []
    keys = [("adventitia_solid_outer", COLORS["adventitia"]), ("media_solid_outer", COLORS["media"]),
            ("aneurysm_intima_ILT_outer", COLORS["intima"]), ("aneurysm_fluid", COLORS["lumen"])]
    for key, color in keys:
        pieces.append((boundaries[key].clip_closed_surface(normal=(0.0, 1.0, 0.0), origin=(0.0, 0.0, 0.0)), color))
    return pieces


def figure_3(output, work):
    """Idealized models with parameters computed from the actual inputs."""
    models = {
        "A": IdealizedParameters(length=100.0, radius_nondilated=5.0, radius_dilated=5.0),
        "B": IdealizedParameters.from_descriptors(beta=1.0, gamma=0.625, chi=2.5, neck_diameter=10.0),
        "D": IdealizedParameters.from_descriptors(beta=0.25, gamma=0.625, chi=2.5, neck_diameter=10.0),
        "E": IdealizedParameters.from_descriptors(beta=0.25, gamma=0.625, chi=2.5, neck_diameter=10.0, ilt_thickness=6.0),
    }
    images = {}
    for key, parameters in models.items():
        boundaries = build_idealized(parameters, work, key)
        center = (0.0, 0.0, 0.5 * parameters.length)
        path = os.path.join(work, "fig3_{}_cut.png".format(key))
        pieces = [(mesh.rotate_y(62.0, point=center), color) for mesh, color in half_model(boundaries)]
        render(pieces, path, position=(0.0, -520.0, 0.0), zoom=1.05, size=(1800, 1100))
        images[key + "cut"] = trim(path)
        path = os.path.join(work, "fig3_{}_full.png".format(key))
        whole = boundaries["adventitia_solid_outer"].rotate_y(62.0, point=center)
        render([(whole, COLORS["adventitia"])], path, position=(40.0, -520.0, 60.0), zoom=1.05, size=(1800, 1100))
        images[key + "full"] = trim(path)

    def label(parameters, healthy=False):
        if healthy:
            return r"($\beta={:.1f}$; $\chi={:.1f}$)".format(parameters.beta, parameters.chi)
        return r"($\beta={:.2f}$; $\gamma={:.3f}$; $\chi={:.1f}$)".format(parameters.beta, parameters.gamma, parameters.chi)

    figure = plt.figure(figsize=(6.5, 5.5))

    def place(rectangle, image):
        axis = figure.add_axes(rectangle)
        show(axis, image)
        return axis

    figure.text(0.255, 0.965, "A) Healthy aorta " + label(models["A"], True), ha="center", va="center", fontsize=9)
    figure.text(0.745, 0.965, "B) Fusiform aneurysm " + label(models["B"]), ha="center", va="center", fontsize=9)
    place([0.00, 0.72, 0.245, 0.22], images["Acut"])
    place([0.25, 0.72, 0.245, 0.22], images["Afull"])
    place([0.505, 0.72, 0.245, 0.22], images["Bcut"])
    place([0.755, 0.72, 0.245, 0.22], images["Bfull"])
    cross_section(figure.add_axes([0.16, 0.555, 0.18, 0.15]), models["A"], "Midsection")
    cross_section(figure.add_axes([0.53, 0.555, 0.18, 0.15]), models["B"], "Midsection")
    legend = figure.add_axes([0.76, 0.555, 0.2, 0.15])
    legend.set_axis_off()
    legend.legend(handles=[mpatches.Patch(color=COLORS["intima"], label="Intima/ILT"),
                           mpatches.Patch(color=COLORS["media"], label="Media"),
                           mpatches.Patch(color=COLORS["adventitia"], label="Adventitia"),
                           mpatches.Patch(color=COLORS["lumen"], label="Lumen")], loc="center", fontsize=8,
                  frameon=True, fancybox=False, edgecolor="black")
    figure.text(0.165, 0.465, "C) Saccular aneurysm\n" + label(models["D"]), ha="center", va="center", fontsize=9, linespacing=1.1)
    figure.text(0.50, 0.465, "D) Cut, no ILT", ha="center", va="center", fontsize=9)
    figure.text(0.835, 0.465, "E) Cut, with ILT", ha="center", va="center", fontsize=9)
    place([0.01, 0.20, 0.32, 0.23], images["Dfull"])
    place([0.34, 0.20, 0.32, 0.23], images["Dcut"])
    place([0.675, 0.20, 0.32, 0.23], images["Ecut"])
    cross_section(figure.add_axes([0.41, 0.045, 0.18, 0.15]), models["D"], "Midsection")
    cross_section(figure.add_axes([0.745, 0.045, 0.18, 0.15]), models["E"], "Midsection")
    figure.savefig(os.path.join(output, "fig3_idealized.png"), dpi=400, facecolor="white")
    plt.close(figure)
    return {key: parameters.to_dict() for key, parameters in models.items()}


def prepare_case(key, centerline_cutoff, profile_cutoff):
    """Return stations for an example."""
    centerline_file, wall_file, lumen_file, flip = CASES[key]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wall = load_area_profile(os.path.join(DATA, wall_file), "wall")
        lumen = load_area_profile(os.path.join(DATA, lumen_file), "lumen")
        stations = prepare_image_derived_stations(read_table(os.path.join(DATA, centerline_file), 3), wall, lumen,
                                                  centerline_cutoff=centerline_cutoff, profile_cutoff=profile_cutoff,
                                                  flip_profiles=flip)
    return stations, wall, lumen, flip


def build_case(stations, work, tag):
    """Build an image-derived model and return outer and lumen surfaces."""
    domain = Domain()
    build_image_derived_model(domain, stations)
    outer = to_polydata(domain.solids["wall_ilt_outer"].geom.shape, os.path.join(work, tag + "_outer.stl"))
    lumen = to_polydata(domain.solids["lumen"].geom.shape, os.path.join(work, tag + "_lumen.stl"))
    return outer, lumen


def profile_panel(axis, key, label):
    """Plot raw and smoothed radius and thickness against normalized arc length."""
    raw, wall, lumen, flip = prepare_case(key, 0.0, 0.0)
    smooth, _, _, _ = prepare_case(key, 30.0, 30.0)
    first = min(wall.abscissa_range[0], lumen.abscissa_range[0])
    last = max(wall.abscissa_range[1], lumen.abscissa_range[1])
    length = 1000.0
    arguments = dict(length=length, flip=flip, abscissa_range=(first, last))
    grid, wall_raw = wall.radius_on_arc_length(**arguments)
    _, lumen_raw = lumen.radius_on_arc_length(**arguments)
    u_raw = grid / length
    u_smooth = smooth.arc_length / smooth.arc_length[-1]
    red, blue = "#d4191c", "#1a33cc"
    axis.plot(wall_raw, u_raw, color=red, linewidth=0.6, alpha=0.55)
    axis.plot(smooth.wall_radius, u_smooth, color=red, linewidth=1.5)
    axis.set_ylabel("Normalized arc length", fontsize=7.5, labelpad=1)
    axis.set_ylim(0.0, 1.0)
    axis.set_yticks([0.0, 0.5, 1.0])
    twin = axis.twiny()
    twin.plot(wall_raw - lumen_raw, u_raw, color=blue, linewidth=0.6, alpha=0.55)
    twin.plot(smooth.wall_radius - smooth.lumen_radius, u_smooth, color=blue, linewidth=1.5)
    axis.xaxis.tick_top()
    axis.xaxis.set_label_position("top")
    twin.xaxis.tick_bottom()
    twin.xaxis.set_label_position("bottom")
    axis.set_xlabel("Outer wall radius (mm)", color=red, fontsize=7.5, labelpad=2)
    twin.set_xlabel("Wall and ILT thickness (mm)", color=blue, fontsize=7.5, labelpad=2)
    axis.tick_params(axis="x", colors=red, labelsize=7, length=2, pad=1)
    axis.tick_params(axis="y", labelsize=7, length=2, pad=1)
    twin.tick_params(axis="x", colors=blue, labelsize=7, length=2, pad=1)
    del label


def longitudinal_panel(axis, stations, label):
    """Draw the cut through the plane that contains the centerline."""
    centers, normals = stations.centers, stations.normals
    in_plane = np.column_stack([normals[:, 2], np.zeros(len(normals)), -normals[:, 0]])
    in_plane = in_plane / np.linalg.norm(in_plane, axis=1, keepdims=True)
    for radius, color, edge in ((stations.wall_radius, COLORS["adventitia"], COLORS["line"]),
                                (stations.lumen_radius, COLORS["lumen"], COLORS["line"])):
        upper = centers + radius[:, None] * in_plane
        lower = centers - radius[:, None] * in_plane
        polygon = np.vstack([upper, lower[::-1]])
        axis.fill(polygon[:, 0], polygon[:, 2], facecolor=color, edgecolor=edge, linewidth=0.4)
    axis.plot(centers[:, 0], centers[:, 2], color="black", linewidth=0.7, linestyle=(0, (5, 2, 1, 2)))
    axis.set_aspect("equal")
    axis.set_axis_off()
    del label
    return in_plane


def figure_4(output, work):
    """Image-derived examples with and without smoothing."""
    figure = plt.figure(figsize=(6.5, 5.7))
    grid = figure.add_gridspec(2, 4, width_ratios=[0.8, 1.0, 1.0, 1.0], wspace=0.22, hspace=0.34,
                               left=0.075, right=0.995, top=0.92, bottom=0.075)
    labels = {"1": "ACEG", "2": "BDFH"}
    titles = (None, "Without smoothing", "With smoothing", "Cut with smoothing")
    for row, key in enumerate(("1", "2")):
        raw, _, _, _ = prepare_case(key, 0.0, 0.0)
        smooth, _, _, _ = prepare_case(key, 30.0, 30.0)
        for column in range(4):
            box_position = grid[row, column].get_position(figure)
            figure.text(box_position.x0 - (0.07 if column == 0 else 0.0), box_position.y1 + 0.038, labels[key][column],
                        fontsize=10, va="center")
            if titles[column]:
                figure.text(0.5 * (box_position.x0 + box_position.x1), box_position.y1 + 0.012, titles[column],
                            ha="center", va="center", fontsize=8)
        profile_panel(figure.add_subplot(grid[row, 0]), key, labels[key][0])
        outer_raw, _ = build_case(raw, work, "ex{}raw".format(key))
        outer_smooth, _ = build_case(smooth, work, "ex{}smooth".format(key))
        for column, (mesh, name) in enumerate(((outer_raw, "raw"), (outer_smooth, "smooth"))):
            path = os.path.join(work, "fig4_{}_{}.png".format(key, name))
            render([(mesh, COLORS["adventitia"])], path, position=(0.0, 500.0, 0.0), size=(900, 1300), zoom=1.1, specular=0.35)
            show(figure.add_subplot(grid[row, column + 1]), trim(path))
        longitudinal_panel(figure.add_subplot(grid[row, 3]), smooth, "")
    figure.savefig(os.path.join(output, "fig4_image_derived.png"), dpi=400, facecolor="white")
    plt.close(figure)


def box(axis, x, y, text, color, width=0.17, height=0.075, code=False, fontsize=7):
    """Draw a text box in axis coordinates."""
    axis.add_patch(mpatches.Rectangle((x - width / 2.0, y - height / 2.0), width, height, facecolor=color,
                                      edgecolor="black", linewidth=0.5, transform=axis.transAxes, zorder=3))
    axis.text(x, y, text, ha="center", va="center", fontsize=fontsize, transform=axis.transAxes, zorder=4,
              family="monospace" if code else "serif")


def arrow(axis, start, end):
    """Draw an arrow in axis coordinates."""
    axis.annotate("", xy=end, xytext=start, xycoords="axes fraction",
                  arrowprops=dict(arrowstyle="-|>", color="black", linewidth=0.6, mutation_scale=7, shrinkA=0, shrinkB=0),
                  zorder=2)


def figure_1(output, work):
    """Workflow of the image-derived pipeline."""
    stations, _, _, _ = prepare_case("1", 30.0, 30.0)
    points = read_table(os.path.join(DATA, CASES["1"][0]), 3)
    line = Centerline(points, cutoff_length=30.0)
    outer, lumen = build_case(stations, work, "fig1")
    view = (-140.0, 470.0, 170.0)

    plotter = pv.Plotter(off_screen=True, window_size=[1000, 1500])
    plotter.set_background("white")
    angles = np.linspace(0.0, 2.0 * np.pi, 121)
    for index in range(len(stations.centers)):
        for radius, color, width in ((stations.wall_radius[index], "#128a4a", 3.0), (stations.lumen_radius[index], "#26332f", 2.5)):
            circle = (stations.centers[index] + radius * (np.cos(angles)[:, None] * stations.x_axes[index]
                                                          + np.sin(angles)[:, None] * stations.y_axes[index]))
            plotter.add_mesh(pv.lines_from_points(circle), color=color, line_width=width, render_lines_as_tubes=True)
    plotter.add_mesh(pv.lines_from_points(line.xyz), color="#1a33cc", line_width=7, render_lines_as_tubes=True)
    plotter.camera.focal_point = tuple(outer.center)
    plotter.camera.position = tuple(np.array(outer.center) + np.array(view))
    plotter.camera.up = (0.0, 0.0, 1.0)
    plotter.reset_camera()
    plotter.enable_anti_aliasing("ssaa")
    sections_path = os.path.join(work, "fig1_sections.png")
    plotter.screenshot(sections_path, transparent_background=True)
    plotter.close()

    surface_path = os.path.join(work, "fig1_surface.png")
    outer_path = os.path.join(work, "fig1_outer.png")
    lumen_path = os.path.join(work, "fig1_lumen.png")
    render([(outer, COLORS["adventitia"])], surface_path, position=view, size=(1000, 1500), zoom=1.05)
    cut = (outer.clip_closed_surface(normal=(0.0, 1.0, 0.0), origin=outer.center),
           lumen.clip_closed_surface(normal=(0.0, 1.0, 0.0), origin=outer.center))
    render([(cut[0], COLORS["adventitia"]), (cut[1], COLORS["lumen"])], outer_path, position=(0.0, -500.0, 0.0),
           size=(1000, 1500), zoom=1.05)
    render([(lumen, COLORS["lumen"])], lumen_path, position=view, size=(1000, 1500), zoom=1.05)

    figure = plt.figure(figsize=(6.5, 2.75))
    axis = figure.add_axes([0.0, 0.0, 1.0, 1.0])
    axis.set_axis_off()
    input_color, step_color, class_color, output_color = "#c9cdf5", "#fdfbcb", "#fddac6", "#c8f5cc"

    def header(x, text, width, code=True, color=class_color):
        box(axis, x, 0.93, text, color, width=width, height=0.085, code=code, fontsize=5.6 if len(text) > 12 else 6.5)

    def place(path, rectangle):
        show(figure.add_axes(rectangle), trim(path))

    header(0.075, "Input", 0.14, code=False, color=input_color)
    box(axis, 0.075, 0.70, "Centerline\n$(X,Y,Z)$", input_color, width=0.14, height=0.13)
    box(axis, 0.075, 0.51, "Wall area\nvs. position", input_color, width=0.14, height=0.13)
    box(axis, 0.075, 0.32, "Lumen area\nvs. position", input_color, width=0.14, height=0.13)

    header(0.285, "prepare_image_derived_stations()", 0.235)
    box(axis, 0.285, 0.70, "Smoothing, arc length,\nrotation-minimizing frames", step_color, width=0.215, height=0.13, fontsize=6.6)
    box(axis, 0.285, 0.51, "Equivalent radius, mapping\nto arc length, smoothing", step_color, width=0.215, height=0.13, fontsize=6.6)
    box(axis, 0.285, 0.32, "Checks: nested radii,\n$\\kappa\\rho<1$, no crossing sections", step_color, width=0.215, height=0.13, fontsize=6.6)
    arrow(axis, (0.145, 0.70), (0.177, 0.70))
    arrow(axis, (0.145, 0.51), (0.177, 0.51))
    arrow(axis, (0.145, 0.32), (0.177, 0.51))
    arrow(axis, (0.285, 0.635), (0.285, 0.575))
    arrow(axis, (0.285, 0.445), (0.285, 0.385))

    header(0.495, "Section", 0.09)
    place(sections_path, [0.425, 0.04, 0.14, 0.82])
    arrow(axis, (0.395, 0.51), (0.43, 0.51))
    header(0.645, "Shell", 0.09)
    place(surface_path, [0.575, 0.04, 0.14, 0.82])
    arrow(axis, (0.4025, 0.93), (0.45, 0.93))
    arrow(axis, (0.54, 0.93), (0.60, 0.93))
    header(0.85, "Solid", 0.09)
    place(outer_path, [0.725, 0.15, 0.13, 0.71])
    place(lumen_path, [0.86, 0.15, 0.13, 0.71])
    arrow(axis, (0.69, 0.93), (0.805, 0.93))
    box(axis, 0.79, 0.07, "Wall + ILT, cut", output_color, width=0.13, height=0.085, fontsize=6.3)
    box(axis, 0.925, 0.07, "Lumen", output_color, width=0.11, height=0.085, fontsize=6.3)
    figure.savefig(os.path.join(output, "fig1_workflow.png"), dpi=400, facecolor="white")
    plt.close(figure)


def main():
    """Create all figures in the directory given on the command line."""
    output = sys.argv[1]
    work = os.path.join(output, "work")
    os.makedirs(work, exist_ok=True)
    parameters = figure_3(output, work)
    figure_4(output, work)
    figure_1(output, work)
    with open(os.path.join(output, "fig3_parameters.json"), "w") as handle:
        json.dump(parameters, handle, indent=2)


if __name__ == "__main__":
    main()
