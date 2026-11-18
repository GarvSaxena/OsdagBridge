"""
Substructure coordinator.

Stacks the four substructure components below the superstructure and returns
both the OCC geometry and a serialisable layout that the IFC exporter reuses.

Vertical stack (all elevations in mm, Z positive upwards):

    underside of girder bottom flange   <- deck_bottom_z (bearing level)
        pier cap            pier_cap_depth
        pier                pier_height
        pile cap            pile_cap_depth
        piles               pile_length

The origin stays where the superstructure already puts it (mid-depth of the
girder web), so the substructure is automatically below the bridge in every
view and every export.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List, Sequence

from osdagbridge.core.bridge_components.foundation.pile.builder import (
    build_pile,
    pile_layout,
    pile_positions,
)
from osdagbridge.core.bridge_components.foundation.pile_cap.builder import (
    build_pile_cap,
    pile_cap_layout,
)
from osdagbridge.core.bridge_components.sub_structure.pier.builder import (
    build_pier,
    pier_layout,
)
from osdagbridge.core.bridge_components.sub_structure.pier_cap.builder import (
    build_pier_cap,
    pier_cap_layout,
)
from osdagbridge.core.bridge_components.sub_structure.params import SubstructureParameters
from osdagbridge.core.bridge_components.sub_structure.reinforcement import make_compound


def bearing_level(girder_depth: float, bottom_flange_thickness: float) -> float:
    """Z of the underside of the girder bottom flange (top of the pier cap)."""
    return -(float(girder_depth) / 2.0 + float(bottom_flange_thickness))


def compute_substructure(
    *,
    support_x_positions: Sequence[float],
    support_y: float,
    deck_width: float,
    deck_bottom_z: float,
    skew_angle: float = 0.0,
    params: SubstructureParameters | None = None,
) -> dict:
    """
    Compute the full substructure layout without creating any geometry.

    This function is OCC-free so it can also be used by the IFC extractor and
    by unit tests.
    """
    params = params or SubstructureParameters()
    rotation = -float(skew_angle)

    pier_cap_top = float(deck_bottom_z)
    pier_cap_bottom = pier_cap_top - float(params.pier_cap_depth)
    pier_top = pier_cap_bottom
    pier_bottom = pier_top - float(params.pier_height)
    pile_cap_top = pier_bottom
    pile_cap_bottom = pile_cap_top - float(params.pile_cap_depth)
    pile_top = pile_cap_bottom

    supports = []
    elements = []

    for index, sx in enumerate(support_x_positions, start=1):
        support_centre = (float(sx), float(support_y))

        cap = pier_cap_layout(
            centre=support_centre,
            z_top=pier_cap_top,
            deck_width=deck_width,
            params=params,
            rotation_deg=rotation,
            label=f"Pier Cap {index}",
        )
        pier = pier_layout(
            centre=support_centre,
            z_top=pier_top,
            params=params,
            rotation_deg=rotation,
            label=f"Pier {index}",
        )
        footing = pile_cap_layout(
            centre=support_centre,
            z_top=pile_cap_top,
            params=params,
            rotation_deg=rotation,
            label=f"Pile Cap {index}",
        )

        piles = []
        for pile_index, position in enumerate(
            pile_positions(support_centre, params, rotation), start=1
        ):
            piles.append(
                pile_layout(
                    centre=position,
                    z_top=pile_top,
                    params=params,
                    rotation_deg=rotation,
                    label=f"Pile {index}.{pile_index}",
                )
            )

        support_elements = [cap, pier, footing] + piles
        elements.extend(support_elements)
        supports.append(
            {
                "index": index,
                "centre": support_centre,
                "rotation": rotation,
                "pier_cap": cap,
                "pier": pier,
                "pile_cap": footing,
                "piles": piles,
                # Convenience: every bar group in this support.
                "rebar": [g for element in support_elements for g in element.get("rebar", [])],
            }
        )

    return {
        "params": asdict(params),
        "rotation": rotation,
        "deck_width": float(deck_width),
        "deck_bottom_z": float(deck_bottom_z),
        "elevations": {
            "pier_cap_top": pier_cap_top,
            "pier_cap_bottom": pier_cap_bottom,
            "pier_top": pier_top,
            "pier_bottom": pier_bottom,
            "pile_cap_top": pile_cap_top,
            "pile_cap_bottom": pile_cap_bottom,
            "pile_top": pile_top,
        },
        "supports": supports,
        "elements": elements,
        "rebar_groups": [g for element in elements for g in element.get("rebar", [])],
    }


def _flatten(shapes: Iterable) -> List:
    out = []
    for shape in shapes:
        if shape is None:
            continue
        if isinstance(shape, (list, tuple)):
            out.extend(_flatten(shape))
        else:
            out.append(shape)
    return out


def build_substructure(
    *,
    support_x_positions: Sequence[float],
    support_y: float,
    deck_width: float,
    deck_bottom_z: float,
    skew_angle: float = 0.0,
    params: SubstructureParameters | None = None,
) -> dict:
    """
    Build the complete substructure.

    Returns a dictionary with per-component OCC shapes (``pier_caps``,
    ``piers``, ``pile_caps``, ``piles``), the individual reinforcement lists,
    and the ``layout`` used by the IFC exporter.
    """
    params = params or SubstructureParameters()
    layout = compute_substructure(
        support_x_positions=support_x_positions,
        support_y=support_y,
        deck_width=deck_width,
        deck_bottom_z=deck_bottom_z,
        skew_angle=skew_angle,
        params=params,
    )

    pier_caps, piers, pile_caps, piles = [], [], [], []
    pier_cap_rebar, pier_rebar, pile_cap_rebar, pile_rebar = [], [], [], []

    for support in layout["supports"]:
        cap = build_pier_cap(
            centre=support["centre"],
            z_top=support["pier_cap"]["z_top"],
            deck_width=deck_width,
            params=params,
            rotation_deg=support["rotation"],
            label=support["pier_cap"]["name"],
        )
        pier = build_pier(
            centre=support["centre"],
            z_top=support["pier"]["z_top"],
            params=params,
            rotation_deg=support["rotation"],
            label=support["pier"]["name"],
        )
        footing = build_pile_cap(
            centre=support["centre"],
            z_top=support["pile_cap"]["z_top"],
            params=params,
            rotation_deg=support["rotation"],
            label=support["pile_cap"]["name"],
        )

        pier_caps.append(cap["concrete"])
        pier_cap_rebar.extend(cap["rebar"])
        piers.append(pier["concrete"])
        pier_rebar.extend(pier["rebar"])
        pile_caps.append(footing["concrete"])
        pile_cap_rebar.extend(footing["rebar"])

        for pile in support["piles"]:
            built = build_pile(
                centre=pile["centre"],
                z_top=pile["z_top"],
                params=params,
                rotation_deg=pile["rotation"],
                label=pile["name"],
            )
            piles.append(built["concrete"])
            pile_rebar.extend(built["rebar"])

    all_rebar = _flatten([pier_cap_rebar, pier_rebar, pile_cap_rebar, pile_rebar])

    return {
        "layout": layout,
        "params": params,
        "pier_caps": pier_caps,
        "piers": piers,
        "pile_caps": pile_caps,
        "piles": piles,
        "pier_cap_reinforcement": pier_cap_rebar,
        "pier_reinforcement": pier_rebar,
        "pile_cap_reinforcement": pile_cap_rebar,
        "pile_reinforcement": pile_rebar,
        "reinforcement": all_rebar,
        # Compounds are what the UI displays (one AIS object per family).
        "reinforcement_compound": make_compound(all_rebar),
    }
