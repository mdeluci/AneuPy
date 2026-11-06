"""Idealized aneurysm from manually placed cross-sections.

Run with ``./run_in_salome.sh idealized_manual.py``.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from aneupy.geometry import Domain  # noqa: E402
from aneupy.pipelines import export_solids  # noqa: E402

OUTPUT = os.environ.get("ANEUPY_OUTPUT_DIR", "output/idealized_manual")

# Axial position, outer radius and lumen radius of each cross-section, in mm.
SECTIONS = [(0., 5., 4.5), (10., 5., 4.5), (20., 5., 4.5), (30., 7., 6.7), (50., 12.5, 10.3),
            (70., 7., 6.7), (80., 5., 4.5), (90., 5., 4.5), (100., 5., 4.5)]

domain = Domain()

for index, (axial, outer_radius, lumen_radius) in enumerate(SECTIONS):
    domain.add_section(name='outer_{}'.format(index), origin=[0., 0., axial])
    domain.sections['outer_{}'.format(index)].add_circle(radius=outer_radius)
    domain.add_section(name='lumen_{}'.format(index), origin=[0., 0., axial])
    domain.sections['lumen_{}'.format(index)].add_circle(radius=lumen_radius)

indices = range(len(SECTIONS))
domain.add_shell(name='outer_shell', sections=['outer_{}'.format(i) for i in indices])
domain.add_shell(name='lumen_shell', sections=['lumen_{}'.format(i) for i in indices])

domain.add_solid_from_shell(name='aneurysm_outer', shell='outer_shell')
domain.add_solid_from_shell(name='aneurysm_fluid', shell='lumen_shell')
domain.add_solid_from_cut(name='aneurysm_solid', solids=['aneurysm_outer', 'aneurysm_fluid'])

export_solids(domain, ['aneurysm_solid', 'aneurysm_fluid'], OUTPUT)
domain.save(os.path.join(OUTPUT, 'idealized_manual_study.hdf'))
