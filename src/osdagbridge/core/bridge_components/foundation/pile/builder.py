"""
Pile builder (circular reinforced-concrete pile).

Piles are generated as a group below a pile cap (2 x 2 by default) at the
specified centre-to-centre spacing.  Each pile is a vertical cylinder with a
main-bar cage and circular hoops.

Default parametric dimensions:

    n_piles_per_cap = 4   (2 x 2 grid)
    pile_diameter   = 400 mm
    pile_length     = 5000 mm
    pile_spacing    = 600 mm (centre-to-centre)
"""

from __future__ import annotations

import math

from osdagbridge.core.bridge_components.sub_structure import reinforcement as rb
from osdagbridge.core.bridge_components.sub_structure.geometry_utils import (
    build_extruded_shape,
    rotate_xy,
)
from osdagbridge.core.bridge_components.sub_structure.params import SubstructureParameters


def pile_positions(
    cap_centre,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
):
    """Return the world ``(x, y)`` centre of every pile in the group."""
    offsets = params.pile_grid_offsets()
    positions = []
    for dx, dy in offsets:
        rotated = rotate_xy(
            (float(cap_centre[0]) + dx, float(cap_centre[1]) + dy, 0.0),
            (float(cap_centre[0]), float(cap_centre[1])),
            rotation_deg,
        )
        positions.append((rotated[0], rotated[1]))
    return positions


def pile_layout(
    centre,
    z_top: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pile",
) -> dict:
    """
    Compute one pile solid and its reinforcement cage.

    Args:
        centre: ``(x, y)`` world position of the pile centre.
        z_top: elevation of the pile cut-off (underside of the pile cap).
        params: substructure dimensions.
        rotation_deg: kept for naming consistency (a cylinder is axisymmetric).
        label: unique display/IFC name prefix.
    """
    cx, cy = float(centre[0]), float(centre[1])
    diameter = float(params.pile_diameter)
    length = float(params.pile_length)
    z_bottom = float(z_top) - length

    cover = float(params.rebar_cover)
    main_dia = float(params.rebar_main_diameter)
    trans_dia = float(params.rebar_transverse_diameter)

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
                segments_count=8,
                name=f"{label} Hoops",
            )
        )

    return {
        "kind": "pile",
        "name": label,
        "centre": (cx, cy),
        "rotation": float(rotation_deg),
        "origin": (cx, cy, z_bottom),
        "z_dir": (0.0, 0.0, 1.0),
        "x_dir": (1.0, 0.0, 0.0),
        "profile": {"type": "circle", "radius": diameter / 2.0},
        "depth": length,
        "diameter": diameter,
        "length": length,
        "z_top": float(z_top),
        "z_bottom": z_bottom,
        "material": "concrete",
        "rebar": rebar,
    }


def build_pile(
    centre,
    z_top: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pile",
) -> dict:
    """Create the OCC pile solid and its rebar cylinders."""
    layout = pile_layout(centre, z_top, params, rotation_deg, label)

    concrete = build_extruded_shape(
        layout["profile"],
        layout["origin"],
        layout["z_dir"],
        layout["x_dir"],
        layout["depth"],
    )

    rebar_shapes = []
    for group in layout["rebar"]:
        rebar_shapes.extend(rb.build_group_shapes(group))

    return {"concrete": concrete, "rebar": rebar_shapes, "layout": layout}
