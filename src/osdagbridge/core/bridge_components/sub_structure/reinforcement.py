"""
Reinforcement primitives shared by the substructure builders.

Rebar is modelled as a collection of straight cylinders (the way it is
detailed on site):

* vertical / longitudinal bars  -> one cylinder per bar,
* hoops and stirrups           -> a closed polygonal ring made from short
                                  cylinders, which is also what a bar-bending
                                  schedule would list.

Every function works in the global CAD coordinate system (millimetres).
The helpers are deliberately OCC-only and have no knowledge of bridge
dimensions, so the component builders stay readable.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCC.Core.TopoDS import TopoDS_Compound
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

Point3 = Tuple[float, float, float]
Segment = Tuple[Point3, Point3]


def bar(start: Point3, end: Point3, diameter: float):
    """Create one straight reinforcing bar between two global points."""
    p1 = gp_Pnt(*[float(v) for v in start])
    p2 = gp_Pnt(*[float(v) for v in end])
    vec = gp_Vec(p1, p2)
    length = vec.Magnitude()
    if length <= 1e-9 or diameter <= 0:
        return None

    axis = gp_Ax2(p1, gp_Dir(vec))
    return BRepPrimAPI_MakeCylinder(axis, float(diameter) / 2.0, float(length)).Shape()


def segment_length(segment: Segment) -> float:
    (x1, y1, z1), (x2, y2, z2) = segment
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)


def bar_group(
    segments: Iterable[Segment],
    diameter: float,
    name: str,
    role: str,
) -> dict:
    """
    Build a serialisable rebar group.

    The group is used twice:

    * by the OCC builders, to create the visible cylinders;
    * by the IFC extractor, to create ``IfcReinforcingBar`` objects with the
      correct bar length, diameter and quantity.

    ``role`` is ``"MAIN"`` or ``"TRANSVERSE"`` (IFC reinforcing-bar types
    ``MAIN`` / ``RING``).
    """
    segs = [tuple(tuple(float(c) for c in p) for p in seg) for seg in segments]
    total = sum(segment_length(s) for s in segs)
    return {
        "name": name,
        "role": role,
        "diameter": float(diameter),
        "bar_count": len(segs),
        "total_length": total,
        "segments": segs,
    }


def build_group_shapes(group: dict) -> List[object]:
    """Turn a rebar group produced by :func:`bar_group` into OCC solids."""
    shapes = []
    for seg in group["segments"]:
        solid = bar(seg[0], seg[1], group["diameter"])
        if solid is not None:
            shapes.append(solid)
    return shapes


# ---------------------------------------------------------------------------
# Geometry generators (return bar groups, not OCC shapes, so the IFC exporter
# can reuse the exact same bar schedule)
# ---------------------------------------------------------------------------

def vertical_bars_circular(
    centre: Tuple[float, float],
    z_bottom: float,
    z_top: float,
    cage_radius: float,
    diameter: float,
    spacing: float,
    name: str,
) -> dict:
    """Vertical main bars distributed around a circle."""
    circumference = 2.0 * math.pi * cage_radius
    count = max(8, int(round(circumference / max(spacing, 1.0))))
    # Keep the cage symmetric.
    if count % 2:
        count += 1

    cx, cy = centre
    segments = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        x = cx + cage_radius * math.cos(angle)
        y = cy + cage_radius * math.sin(angle)
        segments.append(((x, y, z_bottom), (x, y, z_top)))

    return bar_group(segments, diameter, name, "MAIN")


def vertical_bars_rectangular(
    x_positions: Sequence[float],
    y_positions: Sequence[float],
    z_bottom: float,
    z_top: float,
    diameter: float,
    name: str,
) -> dict:
    """Vertical bars on a rectangular grid (pile-cap dowels, column cages)."""
    segments = []
    for x in x_positions:
        for y in y_positions:
            segments.append(((x, y, z_bottom), (x, y, z_top)))
    return bar_group(segments, diameter, name, "MAIN")


def hoop_ring(
    centre: Tuple[float, float],
    z: float,
    radius: float,
    diameter: float,
    segments_count: int,
    name: str,
) -> dict:
    """A horizontal circular hoop approximated by a closed polygonal ring."""
    cx, cy = centre
    n = max(6, int(segments_count))
    points: List[Point3] = []
    for i in range(n):
        angle = 2.0 * math.pi * i / n
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle), z))

    segments = []
    for i in range(n):
        segments.append((points[i], points[(i + 1) % n]))
    return bar_group(segments, diameter, name, "TRANSVERSE")


def hoop_stack(
    centre: Tuple[float, float],
    z_bottom: float,
    z_top: float,
    radius: float,
    diameter: float,
    spacing: float,
    segments_count: int,
    name: str,
) -> dict:
    """A stack of circular hoops between two elevations."""
    segments: List[Segment] = []
    z = z_bottom
    while z <= z_top + 1e-6:
        group = hoop_ring(centre, z, radius, diameter, segments_count, name)
        segments.extend(group["segments"])
        z += max(spacing, 1.0)
    return bar_group(segments, diameter, name, "TRANSVERSE")


def rectangular_ring(
    centre: Tuple[float, float],
    z: float,
    half_x: float,
    half_y: float,
    diameter: float,
    name: str,
) -> dict:
    """A horizontal rectangular tie (pile cap perimeter)."""
    cx, cy = centre
    pts = [
        (cx - half_x, cy - half_y, z),
        (cx + half_x, cy - half_y, z),
        (cx + half_x, cy + half_y, z),
        (cx - half_x, cy + half_y, z),
    ]
    return bar_group([(pts[i], pts[(i + 1) % 4]) for i in range(4)], diameter, name, "TRANSVERSE")


def ring_from_points_3d(
    points: Sequence[Point3],
    diameter: float,
    name: str,
) -> dict:
    """A closed stirrup/hoop through explicit 3-D points."""
    segments = []
    n = len(points)
    for i in range(n):
        segments.append((points[i], points[(i + 1) % n]))
    return bar_group(segments, diameter, name, "TRANSVERSE")


def planar_ring_y(
    y: float,
    profile_points: Sequence[Tuple[float, float]],
    diameter: float,
    name: str,
) -> dict:
    """
    A closed stirrup lying in an XZ plane at ``y``.

    ``profile_points`` are ``(x, z)`` pairs in global coordinates, so the
    stirrup can follow a tapered pier cap.
    """
    segments = []
    n = len(profile_points)
    for i in range(n):
        x1, z1 = profile_points[i]
        x2, z2 = profile_points[(i + 1) % n]
        segments.append(((x1, y, z1), (x2, y, z2)))
    return bar_group(segments, diameter, name, "TRANSVERSE")


def longitudinal_bars(
    y_start: float,
    y_end: float,
    positions: Sequence[Tuple[float, float]],
    diameter: float,
    name: str,
) -> dict:
    """Bars running along Y (used for pier-cap main reinforcement)."""
    segments = []
    for x, z in positions:
        segments.append(((x, y_start, z), (x, y_end, z)))
    return bar_group(segments, diameter, name, "MAIN")


def grid_bars_xy(
    z: float,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    spacing: float,
    diameter: float,
    name: str,
    along: str = "X",
) -> dict:
    """
    A mat of bars in the XY plane at elevation ``z``.

    ``along="X"`` creates bars parallel to X, distributed along Y (and vice
    versa).  Used for the top and bottom mats of the pile cap.
    """
    x0, x1 = x_range
    y0, y1 = y_range
    segments = []

    if along.upper() == "X":
        count = max(2, int(math.floor(abs(y1 - y0) / max(spacing, 1.0))) + 1)
        step = (y1 - y0) / (count - 1)
        for i in range(count):
            y = y0 + i * step
            segments.append(((x0, y, z), (x1, y, z)))
    else:
        count = max(2, int(math.floor(abs(x1 - x0) / max(spacing, 1.0))) + 1)
        step = (x1 - x0) / (count - 1)
        for i in range(count):
            x = x0 + i * step
            segments.append(((x, y0, z), (x, y1, z)))

    return bar_group(segments, diameter, name, "MAIN")


def make_compound(shapes: Iterable[object]):
    """Fuse a list of shapes into a single ``TopoDS_Compound`` for display."""
    shapes = [s for s in shapes if s is not None]
    if not shapes:
        return None
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound
