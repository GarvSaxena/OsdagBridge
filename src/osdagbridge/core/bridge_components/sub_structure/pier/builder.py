"""
Pier builder (circular reinforced-concrete column).

The pier is a vertical cylinder that carries the pier cap.  Its geometry and
its reinforcement cage are computed in :func:`pier_layout`; the same layout is
consumed by the OCC display (:func:`build_pier`) and by the IFC exporter, so
the two can never drift apart.

Default parametric dimensions (see ``sub_structure/params.py``):

    pier_diameter = 800 mm
    pier_height   = 3000 mm
    rebar_main_diameter = 16 mm
    rebar_spacing_longitudinal = 150 mm
    rebar_transverse_diameter = 8 mm
    rebar_spacing_transverse = 200 mm
    rebar_cover = 40 mm
"""

from __future__ import annotations

import math

from osdagbridge.core.bridge_components.sub_structure import reinforcement as rb
from osdagbridge.core.bridge_components.sub_structure.geometry_utils import (
    build_extruded_shape,
    make_profile_face,
)
from osdagbridge.core.bridge_components.sub_structure.params import SubstructureParameters


def pier_layout(
    centre,
    z_top: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pier",
) -> dict:
    """
    Compute the pier solid and its rebar cage.

    Args:
        centre: ``(x, y)`` world position of the column centre.
        z_top: elevation of the top of the pier (underside of the pier cap).
        params: substructure dimensions.
        rotation_deg: plan rotation (``-skew_angle``) for skewed bridges.

    Returns:
        dict: a layout element consumable by the IFC exporter and by
        :func:`build_pier`.
    """
    cx, cy = float(centre[0]), float(centre[1])
    diameter = float(params.pier_diameter)
    height = float(params.pier_height)
    z_bottom = float(z_top) - height

    cover = float(params.rebar_cover)
    main_dia = float(params.rebar_main_diameter)
    trans_dia = float(params.rebar_transverse_diameter)

    # Main bars sit inside the cover, hoops wrap around them.
    main_cage_radius = max(diameter / 2.0 - cover - main_dia / 2.0, main_dia)
    hoop_radius = max(diameter / 2.0 - cover - trans_dia / 2.0, trans_dia)

    rebar = []
    if params.include_reinforcement:
        rebar.append(
            rb.vertical_bars_circular(
                centre=(cx, cy),
                z_bottom=z_bottom + cover,
                z_top=float(z_top) - cover,
                cage_radius=main_cage_radius,
                diameter=main_dia,
                spacing=float(params.rebar_spacing_longitudinal),
                name=f"{label} Main Bars",
            )
        )
        rebar.append(
            rb.hoop_stack(
                centre=(cx, cy),
                z_bottom=z_bottom + cover,
                z_top=float(z_top) - cover,
                radius=hoop_radius,
                diameter=trans_dia,
                spacing=float(params.rebar_spacing_transverse),
                segments_count=12,
                name=f"{label} Hoops",
            )
        )

    return {
        "kind": "pier",
        "name": label,
        "centre": (cx, cy),
        "rotation": float(rotation_deg),
        # Placement for IFC (cylinder extruded upwards from the base).
        "origin": (cx, cy, z_bottom),
        "z_dir": (0.0, 0.0, 1.0),
        "x_dir": (1.0, 0.0, 0.0),
        "profile": {"type": "circle", "radius": diameter / 2.0},
        "depth": height,
        # Semantic dimensions (metadata / BOQ).
        "diameter": diameter,
        "height": height,
        "z_top": float(z_top),
        "z_bottom": z_bottom,
        "material": "concrete",
        "rebar": rebar,
    }


def build_pier(
    centre,
    z_top: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pier",
) -> dict:
    """Create the OCC pier solid and its rebar cylinders."""
    layout = pier_layout(centre, z_top, params, rotation_deg, label)

    concrete = build_extruded_shape(
        layout["profile"],
        layout["origin"],
        layout["z_dir"],
        layout["x_dir"],
        layout["depth"],
    )
    rebar_shapes = rb.build_group_shapes(layout["rebar"][0]) if layout["rebar"] else []
    for group in layout["rebar"][1:]:
        rebar_shapes.extend(rb.build_group_shapes(group))

    return {"concrete": concrete, "rebar": rebar_shapes, "layout": layout}
