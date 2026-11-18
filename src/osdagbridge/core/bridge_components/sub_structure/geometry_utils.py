"""
Small geometry helpers for the substructure builders.

They convert the serialisable layout produced by each builder into real
OpenCASCADE solids, and provide the skew rotation used to keep the piers
parallel to the girders' end lines.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from OCC.Core.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
)
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

Point3 = Tuple[float, float, float]


def rotate_xy(point: Sequence[float], centre: Tuple[float, float], angle_deg: float) -> Point3:
    """Rotate a 3-D point about a vertical axis through ``centre``."""
    if abs(angle_deg) < 1e-12:
        return (float(point[0]), float(point[1]), float(point[2]))

    theta = math.radians(angle_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    dx = float(point[0]) - float(centre[0])
    dy = float(point[1]) - float(centre[1])

    return (
        float(centre[0]) + dx * cos_t - dy * sin_t,
        float(centre[1]) + dx * sin_t + dy * cos_t,
        float(point[2]),
    )


def frame_vectors(angle_deg: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Return the ``(x_dir, y_dir)`` of a frame rotated by ``angle_deg`` about Z.

    The cap axis follows ``y_dir``; with ``angle_deg = -skew`` the pier cap is
    parallel to the skewed girder end lines.
    """
    theta = math.radians(angle_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    return (cos_t, sin_t, 0.0), (-sin_t, cos_t, 0.0)


def local_to_world(
    centre: Tuple[float, float],
    x_dir: Point3,
    y_dir: Point3,
    local_x: float,
    local_y: float,
    z: float,
) -> Point3:
    """Map a local (x, y) offset plus elevation to a world point."""
    return (
        float(centre[0]) + local_x * x_dir[0] + local_y * y_dir[0],
        float(centre[1]) + local_x * x_dir[1] + local_y * y_dir[1],
        float(z),
    )


def _point_on_plane(
    origin: Point3,
    x_dir: Point3,
    y_dir: Point3,
    local_x: float,
    local_y: float,
) -> gp_Pnt:
    return gp_Pnt(
        origin[0] + local_x * x_dir[0] + local_y * y_dir[0],
        origin[1] + local_x * x_dir[1] + local_y * y_dir[1],
        origin[2] + local_x * x_dir[2] + local_y * y_dir[2],
    )


def make_profile_face(
    profile: dict,
    origin: Point3,
    x_dir: Point3,
    y_dir: Point3,
):
    """Create a planar face from a layout profile description."""
    if profile["type"] == "polygon":
        polygon = BRepBuilderAPI_MakePolygon()
        for px, py in profile["points"]:
            polygon.Add(_point_on_plane(origin, x_dir, y_dir, px, py))
        polygon.Close()
        return BRepBuilderAPI_MakeFace(polygon.Wire()).Face()

    if profile["type"] == "rect":
        hx = float(profile["x"]) / 2.0
        hy = float(profile["y"]) / 2.0
        polygon = BRepBuilderAPI_MakePolygon()
        for px, py in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
            polygon.Add(_point_on_plane(origin, x_dir, y_dir, px, py))
        polygon.Close()
        return BRepBuilderAPI_MakeFace(polygon.Wire()).Face()

    raise ValueError(f"Unsupported profile type for a face: {profile['type']}")


def build_extruded_shape(
    profile: dict,
    origin: Point3,
    z_dir: Point3,
    x_dir: Point3,
    depth: float,
):
    """
    Build the OCC solid described by a layout element.

    ``circle`` profiles become cylinders; ``rect`` / ``polygon`` profiles are
    extruded along ``z_dir``.  This mirrors the IFC
    ``IfcExtrudedAreaSolid`` representation exactly.
    """
    if profile["type"] == "circle":
        axis = gp_Ax2(gp_Pnt(*origin), gp_Dir(*z_dir), gp_Dir(*x_dir))
        return BRepPrimAPI_MakeCylinder(axis, float(profile["radius"]), float(depth)).Shape()

    theta = math.radians(0.0)
    # y_dir is always Z x X for the frames used here.
    zx, zy, zz = (float(v) for v in z_dir)
    xx, xy, xz = (float(v) for v in x_dir)
    y_dir = (
        zy * xz - zz * xy,
        zz * xx - zx * xz,
        zx * xy - zy * xx,
    )

    face = make_profile_face(profile, origin, x_dir, y_dir)
    vector = gp_Vec(zx * depth, zy * depth, zz * depth)
    return BRepPrimAPI_MakePrism(face, vector).Shape()


def collect_rebar_shapes(groups: Sequence[dict]) -> List[object]:
    """Build every cylinder of every rebar group."""
    from osdagbridge.core.bridge_components.sub_structure.reinforcement import (
        build_group_shapes,
    )

    shapes = []
    for group in groups:
        shapes.extend(build_group_shapes(group))
    return shapes
