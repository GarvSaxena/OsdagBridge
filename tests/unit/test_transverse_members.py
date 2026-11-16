"""Tests for transverse-member classification used by the result plots.

The plotting dropdown exposes one entry per transverse type (End Diaphragms,
Intermediate Cross Bracings).  ``classify_transverse_members`` is the single
place that decides which element tags belong to which type, so these tests pin
down its grouping and ordering rules.
"""

from __future__ import annotations

from osdagbridge.core.bridge_types.plate_girder.results_data import (
    TRANSVERSE_GROUP_END_DIAPHRAGMS,
    TRANSVERSE_GROUP_INTERMEDIATE_BRACINGS,
    classify_transverse_members,
)

# Three girder lines at z = 0, 5, 10.  Transverse frames sit at x = 0 (start),
# x = 5 (middle) and x = 10 (end).
NODES = {
    1: [0.0, 0.0, 0.0], 2: [0.0, 0.0, 5.0], 3: [0.0, 0.0, 10.0],
    4: [5.0, 0.0, 0.0], 5: [5.0, 0.0, 5.0], 6: [5.0, 0.0, 10.0],
    7: [10.0, 0.0, 0.0], 8: [10.0, 0.0, 5.0], 9: [10.0, 0.0, 10.0],
}

MEMBERS = {
    # Longitudinal girders (same z, different x) — must be ignored.
    101: [1, 7], 102: [2, 8], 103: [3, 9],
    # Transverse frames.
    201: [1, 2], 202: [2, 3],   # x = 0
    203: [4, 5], 204: [5, 6],   # x = 5
    205: [7, 8], 206: [8, 9],   # x = 10
}


def _flat(groups):
    return [tag for frames in groups.values() for frame in frames for tag in frame]


def test_classifies_end_and_intermediate_frames_by_geometry():
    groups = classify_transverse_members(NODES, MEMBERS)

    end_frames = groups[TRANSVERSE_GROUP_END_DIAPHRAGMS]
    mid_frames = groups[TRANSVERSE_GROUP_INTERMEDIATE_BRACINGS]

    assert end_frames == [[201, 202], [205, 206]]
    assert mid_frames == [[203, 204]]

    # Longitudinal elements never leak into a transverse group.
    assert set(_flat(groups)) == {201, 202, 203, 204, 205, 206}


def test_frames_are_ordered_across_the_bridge_width():
    groups = classify_transverse_members(NODES, MEMBERS)
    frame = groups[TRANSVERSE_GROUP_END_DIAPHRAGMS][0]

    # Walking order must start at the low-z edge and end at the high-z edge.
    assert frame[0] == 201
    assert frame[-1] == 202
    assert NODES[MEMBERS[frame[0]][0]][2] == 0.0
    assert NODES[MEMBERS[frame[-1]][1]][2] == 10.0


def test_groups_take_precedence_over_geometric_guess():
    # Force the middle frame into the end-diaphragm group and vice versa.
    groups = classify_transverse_members(
        NODES,
        MEMBERS,
        groups={
            "start_edge": [201, 202, 203, 204],
            "transverse_slab": [205, 206],
        },
    )

    assert groups[TRANSVERSE_GROUP_END_DIAPHRAGMS] == [[201, 202], [203, 204]]
    assert groups[TRANSVERSE_GROUP_INTERMEDIATE_BRACINGS] == [[205, 206]]


def test_diagonals_stay_in_their_frame():
    # A frame with two chords and one diagonal.  The diagonal must not become a
    # separate group or get dropped: all three tags stay in one frame.
    nodes = {
        1: [0.0, 0.0, 0.0], 2: [0.0, 0.0, 5.0], 3: [0.0, 0.0, 10.0],
        4: [10.0, 0.0, 0.0], 5: [10.0, 0.0, 5.0], 6: [10.0, 0.0, 10.0],
    }
    members = {
        11: [1, 2], 12: [2, 3], 13: [1, 3],  # frame at x = 0 (chords + diagonal)
        21: [4, 5], 22: [5, 6],              # frame at x = 10
        31: [1, 4], 32: [2, 5], 33: [3, 6],  # longitudinal
    }

    groups = classify_transverse_members(
        nodes, members, groups={"start_edge": [11, 12, 13]}
    )

    end_frames = groups[TRANSVERSE_GROUP_END_DIAPHRAGMS]
    assert any(set(frame) == {11, 12, 13} for frame in end_frames)


def test_returns_empty_without_transverse_members():
    nodes = {1: [0.0, 0.0, 0.0], 2: [10.0, 0.0, 0.0]}
    members = {1: [1, 2]}
    assert classify_transverse_members(nodes, members) == {}


def test_explicit_transverse_member_list_is_respected():
    # Only the supplied tags are considered, even if other elements look
    # transverse geometrically.
    groups = classify_transverse_members(
        NODES, MEMBERS, transverse_members=[203, 204]
    )
    assert set(_flat(groups)) == {203, 204}
    assert groups[TRANSVERSE_GROUP_INTERMEDIATE_BRACINGS] == [[203, 204]]


def _synthetic_dataset():
    """One load case of forces/displacements for NODES/MEMBERS."""
    import numpy as np
    import xarray as xr

    elements = list(MEMBERS)
    force_components = [
        "Vx_i", "Vx_j", "Vy_i", "Vy_j", "Vz_i", "Vz_j",
        "Mx_i", "Mx_j", "My_i", "My_j", "Mz_i", "Mz_j",
    ]
    rng = np.random.default_rng(0)
    forces = xr.DataArray(
        rng.normal(size=(len(elements), len(force_components))) * 1000.0,
        dims=("Element", "Component"),
        coords={"Element": elements, "Component": force_components},
    )
    node_ids = list(NODES)
    displacements = xr.DataArray(
        rng.normal(size=(len(node_ids), 3)) * 0.01,
        dims=("Node", "Component"),
        coords={"Node": node_ids, "Component": ["x", "y", "z"]},
    )
    return xr.Dataset({"forces": forces, "displacements": displacements})


def test_build_figure_transverse_plots_forces_and_displacements():
    import matplotlib

    matplotlib.use("Agg", force=True)

    from osdagbridge.core.bridge_types.plate_girder.plot_generator import (
        build_figure_transverse,
    )

    ds = _synthetic_dataset()
    frames = classify_transverse_members(NODES, MEMBERS)[
        TRANSVERSE_GROUP_END_DIAPHRAGMS
    ]

    fig, summary = build_figure_transverse(
        ds, "Fy", NODES, MEMBERS, frames,
        group_label=TRANSVERSE_GROUP_END_DIAPHRAGMS,
    )
    assert summary[TRANSVERSE_GROUP_END_DIAPHRAGMS]["max"] >= summary[
        TRANSVERSE_GROUP_END_DIAPHRAGMS
    ]["min"]

    # Every element of every frame is drawn as its own segment (two lines:
    # the zero baseline and the force line), so chords/diagonals are never
    # dropped or merged into a zig-zag.
    n_elements = sum(len(frame) for frame in frames)
    force_lines = [ln for ln in fig.axes[0].lines if ln.get_linewidth() == 2.0]
    assert len(force_lines) == n_elements

    fig2, summary2 = build_figure_transverse(
        ds, "Dz", NODES, MEMBERS, frames,
        group_label=TRANSVERSE_GROUP_END_DIAPHRAGMS,
    )
    assert TRANSVERSE_GROUP_END_DIAPHRAGMS in summary2
    assert fig2.axes[0].get_zlabel().endswith("(mm)")
