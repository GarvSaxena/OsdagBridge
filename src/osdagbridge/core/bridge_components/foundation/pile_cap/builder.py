"""
Pile cap builder (rectangular reinforced-concrete footing).

The pile cap is a rectangular prism sitting on the pile group and carrying
the pier.  Reinforcement is a top and a bottom mat of orthogonal bars, both
kept inside the specified cover.

Default parametric dimensions:

    pile_cap_length = 2200 mm
    pile_cap_width  = 1200 mm
    pile_cap_depth  = 600 mm
"""

from __future__ import annotations

import math

from osdagbridge.core.bridge_components.sub_structure import reinforcement as rb
from osdagbridge.core.bridge_components.sub_structure.geometry_utils import (
    build_extruded_shape,
    frame_vectors,
    local_to_world,
)
from osdagbridge.core.bridge_components.sub_structure.params import SubstructureParameters


def _mat_segments(
    centre,
    x_dir,
    y_dir,
    z,
    x_range,
    y_range,
    spacing,
    along_x: bool,
):
    """Return the segments of one mat layer, running along X or along Y."""
    x0, x1 = x_range
    y0, y1 = y_range
    segments = []

    if along_x:
        usable = y1 - y0
        count = max(2, int(math.floor(usable / spacing)) + 1)
        for i in range(count):
            y = y0 + i * (usable / (count - 1))
            segments.append(
                (
                    local_to_world(centre, x_dir, y_dir, x0, y, z),
                    local_to_world(centre, x_dir, y_dir, x1, y, z),
                )
            )
    else:
        usable = x1 - x0
        count = max(2, int(math.floor(usable / spacing)) + 1)
        for i in range(count):
            x = x0 + i * (usable / (count - 1))
            segments.append(
                (
                    local_to_world(centre, x_dir, y_dir, x, y0, z),
                    local_to_world(centre, x_dir, y_dir, x, y1, z),
                )
            )

    return segments


def pile_cap_layout(
    centre,
    z_top: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pile Cap",
) -> dict:
    """
    Compute the pile-cap solid and its reinforcement mats.

    Args:
        centre: ``(x, y)`` world position of the pile-cap centre.
        z_top: elevation of the top of the pile cap (underside of the pier).
        params: substructure dimensions.
        rotation_deg: plan rotation (``-skew_angle``).
        label: unique display/IFC name prefix.
    """
    cx, cy = float(centre[0]), float(centre[1])
    length = float(params.pile_cap_length)
    width = float(params.pile_cap_width)
    depth = float(params.pile_cap_depth)
    z_bottom = float(z_top) - depth

    x_dir, y_dir = frame_vectors(rotation_deg)

    cover = float(params.rebar_cover)
    main_dia = float(params.rebar_main_diameter)
    spacing = float(params.rebar_spacing_longitudinal)

    rebar = []
    if params.include_reinforcement:
        x_range = (-length / 2.0 + cover + main_dia / 2.0, length / 2.0 - cover - main_dia / 2.0)
        y_range = (-width / 2.0 + cover + main_dia / 2.0, width / 2.0 - cover - main_dia / 2.0)

        for layer_name, z in (
            ("Top", float(z_top) - cover - main_dia / 2.0),
            ("Bottom", z_bottom + cover + main_dia / 2.0),
        ):
            along_x = _mat_segments(
                centre, x_dir, y_dir, z, x_range, y_range, spacing, along_x=True
            )
            along_y = _mat_segments(
                centre, x_dir, y_dir, z, x_range, y_range, spacing, along_x=False
            )
            rebar.append(
                rb.bar_group(along_x, main_dia, f"{label} {layer_name} Bars (X)", "MAIN")
            )
            rebar.append(
                rb.bar_group(along_y, main_dia, f"{label} {layer_name} Bars (Y)", "MAIN")
            )

        # Perimeter tie around the cap at mid-depth keeps the cage together.
        tie_half_x = length / 2.0 - cover - params.rebar_transverse_diameter / 2.0
        tie_half_y = width / 2.0 - cover - params.rebar_transverse_diameter / 2.0
        z_tie = z_bottom + depth / 2.0
        tie_points = [
            local_to_world(centre, x_dir, y_dir, -tie_half_x, -tie_half_y, z_tie),
            local_to_world(centre, x_dir, y_dir, +tie_half_x, -tie_half_y, z_tie),
            local_to_world(centre, x_dir, y_dir, +tie_half_x, +tie_half_y, z_tie),
            local_to_world(centre, x_dir, y_dir, -tie_half_x, +tie_half_y, z_tie),
        ]
        rebar.append(
            rb.ring_from_points_3d(
                tie_points,
                float(params.rebar_transverse_diameter),
                f"{label} Perimeter Tie",
            )
        )

    return {
        "kind": "pile_cap",
        "name": label,
        "centre": (cx, cy),
        "rotation": float(rotation_deg),
        "origin": (cx, cy, z_bottom),
        "z_dir": (0.0, 0.0, 1.0),
        "x_dir": x_dir,
        "profile": {"type": "rect", "x": length, "y": width},
        "depth": depth,
        "length": length,
        "width": width,
        "cap_depth": depth,
        "z_top": float(z_top),
        "z_bottom": z_bottom,
        "material": "concrete",
        "rebar": rebar,
    }


def build_pile_cap(
    centre,
    z_top: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pile Cap",
) -> dict:
    """Create the OCC pile-cap solid and its rebar cylinders."""
    layout = pile_cap_layout(centre, z_top, params, rotation_deg, label)

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
