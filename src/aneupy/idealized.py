"""Parameters and analytic cross-section layout of idealized aneurysm models."""

import json
import math

import numpy as np

from .validation import GeometryError, as_finite_array, require_non_negative, require_positive


class IdealizedParameters:
    """Dimensional parameters of an idealized aneurysm.

    An idealized model has a straight reference axis along global Z, circular
    cross-sections, equal necks, uniform wall layers, and a sac centred at mid-length. Section
    centres may be offset from the axis inside the sac. The shape is prescribed by these
    parameters and it does not derive from an individual patient.

    Parameters
    ----------
    length : float
        Total model length in mm, including both necks.
    radius_nondilated : float
        Lumen radius of the necks in mm.
    radius_dilated : float
        Lumen radius at the sac midsection in mm, before any thrombus is added.
    wall_thickness_intima, wall_thickness_media, wall_thickness_adventitia : float
        Layer thicknesses in mm.
    ilt_thickness : float
        Intraluminal thrombus thickness at the sac midsection in mm. Zero means no
        thrombus.
    x_shift, y_shift : float
        Offset of the sac midsection centre from the Z axis in mm. Zero means symmetry.
    sac_fraction : float
        Aneurysm length as a fraction of ``length``.
    section_spacing : float
        Axial distance between cross-sections in mm.

    Notes
    -----
    Radius, thrombus thickness and centre shift all follow the shape function of
    :meth:`sac_weight`, so ``D_max``, ``L_AAA``, ``r`` and ``R`` hold exactly at the
    prescribed sections.
    """

    FIELDS = ("length", "radius_nondilated", "radius_dilated", "wall_thickness_intima",
              "wall_thickness_media", "wall_thickness_adventitia", "ilt_thickness",
              "x_shift", "y_shift", "sac_fraction", "section_spacing")

    def __init__(self, length=100.0, radius_nondilated=5.0, radius_dilated=12.0,
                 wall_thickness_intima=0.5, wall_thickness_media=0.3, wall_thickness_adventitia=0.7,
                 ilt_thickness=0.0, x_shift=0.0, y_shift=0.0, sac_fraction=0.4, section_spacing=5.0):
        self.length = require_positive(length, "length")
        self.radius_nondilated = require_positive(radius_nondilated, "radius_nondilated")
        self.radius_dilated = require_positive(radius_dilated, "radius_dilated")
        self.wall_thickness_intima = require_positive(wall_thickness_intima, "wall_thickness_intima")
        self.wall_thickness_media = require_positive(wall_thickness_media, "wall_thickness_media")
        self.wall_thickness_adventitia = require_positive(wall_thickness_adventitia,
                                                          "wall_thickness_adventitia")
        self.ilt_thickness = require_non_negative(ilt_thickness, "ilt_thickness")
        self.x_shift = float(as_finite_array(x_shift, "x_shift"))
        self.y_shift = float(as_finite_array(y_shift, "y_shift"))
        self.sac_fraction = require_positive(sac_fraction, "sac_fraction")
        self.section_spacing = require_positive(section_spacing, "section_spacing")
        if self.sac_fraction >= 1.0:
            raise GeometryError("sac_fraction must be below 1 so that both necks exist")
        if self.radius_dilated < self.radius_nondilated:
            raise GeometryError("radius_dilated must not be smaller than radius_nondilated")
        if self.shift >= self.radius_dilated:
            raise GeometryError("The sac shift must be smaller than radius_dilated so that the "
                                "axis stays inside the lumen (beta > 0)")
        if self.ilt_thickness >= self.radius_dilated:
            raise GeometryError("ilt_thickness must be smaller than radius_dilated")

    @classmethod
    def from_descriptors(cls, beta, gamma, chi, neck_diameter, sac_fraction=0.4, shift_angle=0.0, **layers):
        """Build parameters from the dimensionless descriptors of the manuscript.

        Parameters
        ----------
        beta : float
            Asymmetry ``r / R`` with ``0 < beta <= 1``.
        gamma : float
            Aspect ratio ``D_max / L_AAA``.
        chi : float
            Dilation ``D_max / D_neck``, at least 1.
        neck_diameter : float
            Neck lumen diameter in mm.
        sac_fraction : float, optional
            Aneurysm length as a fraction of total length.
        shift_angle : float, optional
            Direction of the sac shift in the XY plane, in degrees from +X.
        **layers
            Remaining keyword arguments of the constructor.
        """
        if not 0.0 < beta <= 1.0:
            raise GeometryError("beta must satisfy 0 < beta <= 1")
        require_positive(gamma, "gamma")
        if chi < 1.0:
            raise GeometryError("chi must be at least 1")
        radius_dilated = 0.5 * chi * require_positive(neck_diameter, "neck_diameter")
        shift = radius_dilated * (1.0 - beta) / (1.0 + beta)
        aneurysm_length = 2.0 * radius_dilated / gamma
        angle = math.radians(shift_angle)
        return cls(length=aneurysm_length / sac_fraction, radius_nondilated=0.5 * neck_diameter,
                   radius_dilated=radius_dilated, x_shift=shift * math.cos(angle),
                   y_shift=shift * math.sin(angle), sac_fraction=sac_fraction, **layers)

    @classmethod
    def from_json(cls, path, **overrides):
        """Read parameters from a JSON file, with optional overriding values."""
        try:
            with open(str(path)) as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            raise GeometryError("Cannot read {}: {}".format(path, error))
        unknown = sorted(set(data) - set(cls.FIELDS))
        if unknown:
            raise GeometryError("Unknown parameters in {}: {}. Valid names: {}".format(
                path, ", ".join(unknown), ", ".join(cls.FIELDS)))
        data.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**data)

    @property
    def n_sections(self):
        """Number of cross-sections."""
        return int(self.axial_positions().size)

    @property
    def shift(self):
        """Distance of the sac midsection centre from the Z axis in mm."""
        return math.hypot(self.x_shift, self.y_shift)

    @property
    def aneurysm_length(self):
        """Aneurysm length ``L_AAA`` in mm."""
        return self.sac_fraction * self.length

    @property
    def beta(self):
        """Asymmetry ``r / R``, measured from the axis to the vessel wall at the midsection."""
        return (self.radius_dilated - self.shift) / (self.radius_dilated + self.shift)

    @property
    def gamma(self):
        """Aspect ratio ``D_max / L_AAA``, with diameters measured on the vessel lumen."""
        return 2.0 * self.radius_dilated / self.aneurysm_length

    @property
    def chi(self):
        """Dilation ``D_max / D_neck``, with diameters measured on the vessel lumen."""
        return self.radius_dilated / self.radius_nondilated

    def axial_positions(self):
        """Return the axial position of each cross-section in mm.

        Sections always fall on the sac ends and on the midsection, so ``L_AAA`` and ``D_max``
        hold exactly at the sections.
        """
        neck = 0.5 * (self.length - self.aneurysm_length)
        neck_segments = max(3, int(math.ceil(neck / self.section_spacing)))
        half_sac_segments = max(4, int(math.ceil(0.5 * self.aneurysm_length / self.section_spacing)))
        proximal = np.linspace(0.0, neck, neck_segments + 1)
        sac = np.linspace(neck, self.length - neck, 2 * half_sac_segments + 1)
        distal = np.linspace(self.length - neck, self.length, neck_segments + 1)
        return np.r_[proximal, sac[1:], distal[1:]]

    def sac_weight(self, axial_position):
        """Return the sac shape function ``w(z)`` at the given axial positions.

        ``w = cos^2(pi (z - z_c) / L_AAA)`` inside the sac and zero in the necks, where
        ``z_c`` is the model mid-length. The function reaches 1 at the midsection and
        joins the necks with zero slope.
        """
        offset = np.asarray(axial_position, dtype=float) - 0.5 * self.length
        half_length = 0.5 * self.aneurysm_length
        return np.where(np.abs(offset) < half_length, np.cos(np.pi * offset / self.aneurysm_length) ** 2, 0.0)

    def centers(self):
        """Return cross-section centres in mm, with shape ``(n, 3)``."""
        positions = self.axial_positions()
        weights = self.sac_weight(positions)
        return np.column_stack([weights * self.x_shift, weights * self.y_shift, positions])

    def wall_inner_radii(self):
        """Return the radius of the inner vessel wall at each cross-section, in mm."""
        weights = self.sac_weight(self.axial_positions())
        return self.radius_nondilated + weights * (self.radius_dilated - self.radius_nondilated)

    def lumen_radii(self):
        """Return the flow lumen radius at each cross-section in mm, after any thrombus."""
        return self.wall_inner_radii() - self.sac_weight(self.axial_positions()) * self.ilt_thickness

    def to_dict(self):
        """Return the input parameters and derived descriptors as a dictionary."""
        data = {name: getattr(self, name) for name in self.FIELDS}
        data.update(beta=self.beta, gamma=self.gamma, chi=self.chi, aneurysm_length=self.aneurysm_length)
        return data
