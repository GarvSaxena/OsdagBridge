"""Tests for the parametric bridge substructure and its IFC integration.

These exercise the same code path the 3-D view and the IFC exporter use:

    SubstructureParameters  ->  compute_substructure / build_substructure
                            ->  PlateGirderIFCExtractor -> BridgeIfcGenerator

The checks cover the dimensions fixed by the screening task, the vertical
stack below the girders, the reinforcement schedule and the resulting IFC
entities (piers, caps, piles, rebar, storey, materials and quantities).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from osdagbridge.core.bridge_components.sub_structure.params import (
    SubstructureParameters,
)
from osdagbridge.core.bridge_components.sub_structure.substructure import (
    bearing_level,
    build_substructure,
    compute_substructure,
)


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


def test_default_dimensions_match_task_specification():
    params = SubstructureParameters()

    assert params.pier_diameter == 800
    assert params.pier_height == 3000

    assert params.pier_cap_top_width == 3000
    assert params.pier_cap_bottom_width == 1200
    assert params.pier_cap_depth == 600
    # None means "use the deck width".
    assert params.pier_cap_length is None

    assert params.pile_cap_length == 2200
    assert params.pile_cap_width == 1200
    assert params.pile_cap_depth == 600

    assert params.n_piles_per_cap == 4
    assert params.pile_diameter == 400
    assert params.pile_length == 5000
    assert params.pile_spacing == 600

    assert params.rebar_main_diameter == 16
    assert params.rebar_spacing_longitudinal == 150
    assert params.rebar_transverse_diameter == 8
    assert params.rebar_spacing_transverse == 200
    assert params.rebar_cover == 40


def test_concrete_is_semi_transparent():
    params = SubstructureParameters()

    assert params.concrete_opacity == pytest.approx(0.35)
    # OCC wants transparency, i.e. 1 - opacity.
    assert params.concrete_transparency == pytest.approx(0.65)


def test_pier_cap_length_follows_deck_width_unless_overridden():
    params = SubstructureParameters()

    assert params.resolved_pier_cap_length(12_000) == 12_000
    assert params.resolved_pier_cap_length(7_500) == 7_500

    fixed = params.with_overrides(pier_cap_length=9_000)
    assert fixed.resolved_pier_cap_length(12_000) == 9_000


def test_pile_grid_is_two_by_two():
    offsets = SubstructureParameters().pile_grid_offsets()

    assert len(offsets) == 4
    assert sorted(offsets) == [(-300.0, -300.0), (-300.0, 300.0), (300.0, -300.0), (300.0, 300.0)]


# ---------------------------------------------------------------------------
# Layout (OCC-free)
# ---------------------------------------------------------------------------


def _layout(**kwargs):
    options = dict(
        support_x_positions=[0.0, 20_000.0],
        support_y=0.0,
        deck_width=12_000.0,
        deck_bottom_z=bearing_level(1_500.0, 20.0),
        skew_angle=0.0,
    )
    options.update(kwargs)
    return compute_substructure(**options)


def test_bearing_level_is_below_the_girder():
    # Z = 0 is the mid-depth of the girder web.
    assert bearing_level(1_500.0, 20.0) == pytest.approx(-770.0)


def test_vertical_stack_is_continuous_and_downwards():
    layout = _layout()
    levels = layout["elevations"]

    top = bearing_level(1_500.0, 20.0)
    assert levels["pier_cap_top"] == pytest.approx(top)
    assert levels["pier_cap_bottom"] == pytest.approx(top - 600)
    assert levels["pier_top"] == pytest.approx(levels["pier_cap_bottom"])
    assert levels["pier_bottom"] == pytest.approx(levels["pier_top"] - 3_000)
    assert levels["pile_cap_top"] == pytest.approx(levels["pier_bottom"])
    assert levels["pile_cap_bottom"] == pytest.approx(levels["pile_cap_top"] - 600)
    assert levels["pile_top"] == pytest.approx(levels["pile_cap_bottom"])
    assert levels["pile_top"] < levels["pier_cap_top"]


def test_one_support_line_gets_cap_pier_footing_and_four_piles():
    layout = _layout()

    assert len(layout["supports"]) == 2
    assert len(layout["elements"]) == 14  # 2 * (cap + pier + footing + 4 piles)

    kinds = [element["kind"] for element in layout["elements"]]
    assert kinds.count("pier_cap") == 2
    assert kinds.count("pier") == 2
    assert kinds.count("pile_cap") == 2
    assert kinds.count("pile") == 8

    cap = layout["elements"][0]
    assert cap["length"] == pytest.approx(12_000.0)  # deck width
    assert cap["top_width"] == pytest.approx(3_000.0)
    assert cap["bottom_width"] == pytest.approx(1_200.0)
    assert cap["cap_depth"] == pytest.approx(600.0)

    pier = layout["elements"][1]
    assert pier["diameter"] == pytest.approx(800.0)
    assert pier["height"] == pytest.approx(3_000.0)

    footing = layout["elements"][2]
    assert footing["length"] == pytest.approx(2_200.0)
    assert footing["width"] == pytest.approx(1_200.0)
    assert footing["cap_depth"] == pytest.approx(600.0)

    piles = [element for element in layout["elements"] if element["kind"] == "pile"]
    assert all(pile["diameter"] == pytest.approx(400.0) for pile in piles)
    assert all(pile["length"] == pytest.approx(5_000.0) for pile in piles)

    centres = sorted((round(p["centre"][0], 3), round(p["centre"][1], 3)) for p in piles[:4])
    assert centres == [(-300.0, -300.0), (-300.0, 300.0), (300.0, -300.0), (300.0, 300.0)]


def test_reinforcement_schedule_uses_task_diameters_and_spacings():
    layout = _layout()
    groups = layout["rebar_groups"]

    assert groups
    main = [group for group in groups if group["role"] == "MAIN"]
    transverse = [group for group in groups if group["role"] != "MAIN"]

    assert main and transverse
    assert all(group["diameter"] == pytest.approx(16.0) for group in main)
    assert all(group["diameter"] == pytest.approx(8.0) for group in transverse)
    assert sum(group["bar_count"] for group in groups) > 0
    assert all(group["segments"] for group in groups)


def test_skew_rotates_the_pier_cap_in_plan():
    straight = _layout()
    skewed = _layout(skew_angle=15.0)

    assert straight["rotation"] == pytest.approx(0.0)
    assert skewed["rotation"] == pytest.approx(-15.0)

    cap_straight = straight["elements"][0]
    cap_skewed = skewed["elements"][0]
    # The cap runs along its rotated Y axis, so the extrusion direction changes.
    assert cap_skewed["z_dir"] != cap_straight["z_dir"]


# ---------------------------------------------------------------------------
# OCC geometry
# ---------------------------------------------------------------------------


def test_build_substructure_creates_valid_occ_solids():
    substructure = build_substructure(
        support_x_positions=[0.0, 20_000.0],
        support_y=0.0,
        deck_width=12_000.0,
        deck_bottom_z=bearing_level(1_500.0, 20.0),
    )

    assert len(substructure["pier_caps"]) == 2
    assert len(substructure["piers"]) == 2
    assert len(substructure["pile_caps"]) == 2
    assert len(substructure["piles"]) == 8
    assert substructure["reinforcement"]
    assert substructure["reinforcement_compound"] is not None

    for key in ("pier_caps", "piers", "pile_caps", "piles"):
        for shape in substructure[key]:
            assert shape is not None
            assert not shape.IsNull()


# ---------------------------------------------------------------------------
# IFC
# ---------------------------------------------------------------------------


def test_ifc_contains_substructure_elements_and_rebar(tmp_path):
    ifcopenshell = pytest.importorskip("ifcopenshell")

    from osdagbridge.core.ifc_export_bridge.bridge_ifc_generator import (
        BridgeIfcGenerator,
    )

    layout = _layout(skew_angle=10.0)
    cad_context = SimpleNamespace(
        concrete_grade="M30",
        steel_grade="E 250A",
        span_length_L=20_000.0,
    )

    output = tmp_path / "substructure.ifc"
    BridgeIfcGenerator(str(output)).generate_from_extracted_data(
        {"substructure": layout}, cad_context
    )

    model = ifcopenshell.open(str(output))

    assert len(model.by_type("IfcColumn")) == 2
    assert len(model.by_type("IfcBeam")) == 2
    assert len(model.by_type("IfcFooting")) == 2
    assert len(model.by_type("IfcPile")) == 8
    assert len(model.by_type("IfcReinforcingBar")) == len(layout["rebar_groups"])

    storeys = {storey.Name for storey in model.by_type("IfcBuildingStorey")}
    assert "Substructure" in storeys

    materials = {material.Name for material in model.by_type("IfcMaterial")}
    assert "Concrete M30" in materials
    assert "Steel Fe 500" in materials

    # BOQ-ready quantities on every substructure element.
    assert len(model.by_type("IfcElementQuantity")) >= 14

    pier = model.by_type("IfcColumn")[0]
    radius = pier.Representation.Representations[0].Items[0].SweptArea.Radius
    assert radius == pytest.approx(0.4)  # 800 mm -> 0.4 m

    placement_z = pier.ObjectPlacement.RelativePlacement.Location.Coordinates[2]
    assert placement_z == pytest.approx(-4.37, abs=1e-6)

    # BOQ data must be linked to the element, not just present in the file.
    linked_quantities = [
        rel.RelatingPropertyDefinition
        for rel in model.by_type("IfcRelDefinesByProperties")
        if pier in rel.RelatedObjects
        and rel.RelatingPropertyDefinition.is_a("IfcElementQuantity")
    ]
    assert linked_quantities
    assert linked_quantities[0].Name == "Qto_ColumnBaseQuantities"
    quantities = {q.Name: q for q in linked_quantities[0].Quantities}
    assert quantities["Length"].LengthValue == pytest.approx(3.0)
    assert quantities["GrossVolume"].VolumeValue == pytest.approx(1.508, rel=1e-2)

    assert any(
        pier in rel.RelatedObjects
        for rel in model.by_type("IfcRelAssociatesMaterial")
    )

    bar = model.by_type("IfcReinforcingBar")[0]
    assert bar.NominalDiameter in (pytest.approx(0.016), pytest.approx(0.008))
    assert bar.BarLength > 0

    # Concrete is exported at 35 % opacity (IFC transparency = 0.65).
    render_styles = model.by_type("IfcSurfaceStyleRendering")
    assert any(
        style.Transparency == pytest.approx(0.65) for style in render_styles
    )

    # The file must be schema-valid to open cleanly in Revit / BIM viewers.
    import ifcopenshell.validate

    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, logger)
    errors = [s for s in logger.statements if s.get("level") == "error"]
    assert errors == []
