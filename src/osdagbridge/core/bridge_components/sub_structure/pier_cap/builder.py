"""
Pier cap builder (hammerhead / trapezoidal reinforced-concrete cap).

The cap is a trapezoidal prism: the top is ``pier_cap_top_width`` wide to
receive all the girders, the bottom narrows to ``pier_cap_bottom_width`` where
it meets the circular pier, and the section is extruded across the deck
(``pier_cap_length``, default = deck width).

The local frame used below has its X axis along the span and its Y axis along
the cap (the extrusion direction).  For skewed bridges the whole frame is
rotated by ``-skew_angle`` so the cap stays parallel to the girder end lines.

Default parametric dimensions:

    pier_cap_top_width    = 3000 mm
    pier_cap_bottom_width = 1200 mm
    pier_cap_depth        = 600 mm
    pier_cap_length       = deck width
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


def pier_cap_layout(
    centre,
    z_top: float,
    deck_width: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pier Cap",
) -> dict:
    """
    Compute the trapezoidal cap solid and its reinforcement.

    Args:
        centre: ``(x, y)`` world position of the pier/cap centre.
        z_top: elevation of the top of the cap (underside of bearings).
        deck_width: total deck width used when ``pier_cap_length`` is ``None``.
        params: substructure dimensions.
        rotation_deg: plan rotation (``-skew_angle``).
        label: unique display/IFC name prefix.
    """
    cx, cy = float(centre[0]), float(centre[1])
    length = float(params.resolved_pier_cap_length(deck_width))
    top_w = float(params.pier_cap_top_width)
    bot_w = float(params.pier_cap_bottom_width)
    depth = float(params.pier_cap_depth)
    z_bottom = float(z_top) - depth

    x_dir, y_dir = frame_vectors(rotation_deg)

    # Extrusion starts at one end of the cap and runs along +y_dir.
    origin = (
        cx - (length / 2.0) * y_dir[0],
        cy - (length / 2.0) * y_dir[1],
        float(z_top),
    )

    # Local profile: x = across the span, y = downwards from the cap top.
    profile_points = [
        (-top_w / 2.0, 0.0),
        (+top_w / 2.0, 0.0),
        (+bot_w / 2.0, depth),
        (-bot_w / 2.0, depth),
    ]

    cover = float(params.rebar_cover)
    main_dia = float(params.rebar_main_diameter)
    trans_dia = float(params.rebar_transverse_diameter)
    y_start = -(length / 2.0) + cover
    y_end = +(length / 2.0) - cover

    rebar = []
    if params.include_reinforcement:
        # --- Main bars along the cap (Y direction), top and bottom layers ---
        for layer_name, half_width, z in (
            ("Top", top_w / 2.0, float(z_top) - cover - main_dia / 2.0),
            ("Bottom", bot_w / 2.0, z_bottom + cover + main_dia / 2.0),
        ):
            usable = max(2.0 * (half_width - cover - main_dia / 2.0), main_dia)
            count = max(4, int(math.floor(usable / params.rebar_spacing_longitudinal)) + 1)
            positions = []
            for i in range(count):
                local_x = -usable / 2.0 + i * (usable / (count - 1))
                positions.append(
                    (
                        local_to_world(centre, x_dir, y_dir, local_x, y_start, z),
                        local_to_world(centre, x_dir, y_dir, local_x, y_end, z),
                    )
                )
            rebar.append(
                rb.bar_group(
                    positions,
                    main_dia,
                    f"{label} {layer_name} Main Bars",
                    "MAIN",
                )
            )

        # --- Closed stirrups following the taper, one every transverse spacing ---
        stirrup_segments = []
        y = y_start
        while y <= y_end + 1e-6:
            inset_top = max(top_w / 2.0 - cover, main_dia)
            inset_bottom = max(bot_w / 2.0 - cover, main_dia)
            ring_points = [
                local_to_world(centre, x_dir, y_dir, -inset_top, y, float(z_top) - cover),
                local_to_world(centre, x_dir, y_dir, +inset_top, y, float(z_top) - cover),
                local_to_world(centre, x_dir, y_dir, +inset_bottom, y, z_bottom + cover),
                local_to_world(centre, x_dir, y_dir, -inset_bottom, y, z_bottom + cover),
            ]
            stirrup_segments.extend(
                rb.ring_from_points_3d(ring_points, trans_dia, f"{label} Stirrups")["segments"]
            )
            y += max(float(params.rebar_spacing_transverse), 1.0)

        rebar.append(
            rb.bar_group(stirrup_segments, trans_dia, f"{label} Stirrups", "TRANSVERSE")
        )

    return {
        "kind": "pier_cap",
        "name": label,
        "centre": (cx, cy),
        "rotation": float(rotation_deg),
        # IFC placement: profile in the (span, vertical) plane, extruded along Y.
        "origin": origin,
        "z_dir": y_dir,
        "x_dir": x_dir,
        "profile": {"type": "polygon", "points": profile_points},
        "depth": length,
        # Semantic dimensions.
        "length": length,
        "top_width": top_w,
        "bottom_width": bot_w,
        "cap_depth": depth,
        "z_top": float(z_top),
        "z_bottom": z_bottom,
        "material": "concrete",
        "rebar": rebar,
    }


def build_pier_cap(
    centre,
    z_top: float,
    deck_width: float,
    params: SubstructureParameters,
    rotation_deg: float = 0.0,
    label: str = "Pier Cap",
) -> dict:
    """Create the OCC pier-cap solid and its rebar cylinders."""
    layout = pier_cap_layout(centre, z_top, deck_width, params, rotation_deg, label)

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
