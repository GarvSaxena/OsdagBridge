"""
Parametric dimensions for the bridge substructure.

Every dimension is in millimetres to match the existing superstructure
builders (girders, deck, bracing).  The defaults are the values specified in
the screening task; they can be overridden from the DTO without touching any
builder code.

Coordinate convention (shared with the superstructure):

    X -> longitudinal (along the span, 0 .. span_length_L)
    Y -> transverse   (across the deck, centred on the bridge centreline)
    Z -> vertical     (upwards)

The substructure is stacked downwards from the underside of the girder
bottom flange, so it stays consistent with the existing CAD model where
Z = 0 is the mid-depth of the girder web.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class SubstructureParameters:
    """Parametric dimensions of the bridge substructure (all in mm)."""

    # --- Piers (circular columns) ---
    pier_diameter: float = 800.0
    pier_height: float = 3000.0

    # --- Pier cap (hammerhead / trapezoidal prism) ---
    pier_cap_top_width: float = 3000.0
    pier_cap_bottom_width: float = 1200.0
    pier_cap_depth: float = 600.0
    #: ``None`` means "match the deck width" (resolved per design).
    pier_cap_length: Optional[float] = None

    # --- Pile cap (rectangular prism) ---
    pile_cap_length: float = 2200.0
    pile_cap_width: float = 1200.0
    pile_cap_depth: float = 600.0

    # --- Piles (circular, 2 x 2 grid by default) ---
    n_piles_per_cap: int = 4
    pile_diameter: float = 400.0
    pile_length: float = 5000.0
    pile_spacing: float = 600.0

    # --- Reinforcement ---
    rebar_main_diameter: float = 16.0
    rebar_spacing_longitudinal: float = 150.0
    rebar_transverse_diameter: float = 8.0
    rebar_spacing_transverse: float = 200.0
    rebar_cover: float = 40.0

    # --- Display / export ---
    include_reinforcement: bool = True
    #: Concrete opacity requested by the task (0.35 = 35 % opaque).
    concrete_opacity: float = 0.35

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolved_pier_cap_length(self, deck_width: float) -> float:
        """Return the pier-cap length, falling back to the deck width."""
        if self.pier_cap_length is not None and self.pier_cap_length > 0:
            return float(self.pier_cap_length)
        return float(deck_width)

    def with_overrides(self, **overrides) -> "SubstructureParameters":
        """Return a copy with selected dimensions replaced."""
        clean = {k: v for k, v in overrides.items() if v is not None}
        return replace(self, **clean) if clean else self

    @property
    def concrete_transparency(self) -> float:
        """OCC transparency (0 = opaque, 1 = invisible) for the concrete."""
        opacity = min(max(float(self.concrete_opacity), 0.0), 1.0)
        return 1.0 - opacity

    def pile_grid_offsets(self):
        """
        Return ``(dx, dy)`` offsets of the pile centres relative to the pile
        cap centre.

        Four piles are arranged in a 2 x 2 grid at ``pile_spacing``; other
        counts fall back to an evenly spaced row so the builder never fails.
        """
        n = max(1, int(self.n_piles_per_cap))
        if n == 4:
            s = float(self.pile_spacing) / 2.0
            return [(-s, -s), (+s, -s), (-s, +s), (+s, +s)]

        # Generic fallback: a single centred row/exact circle layout.
        if n == 1:
            return [(0.0, 0.0)]
        span = (n - 1) * float(self.pile_spacing)
        return [(-span / 2.0 + i * float(self.pile_spacing), 0.0) for i in range(n)]
