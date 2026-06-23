"""
Stiffness Modifier tools — apply ACI 318 cracked-section factors to
beams, columns, walls, and slabs instantaneously.

Tools:
  - etabs_assign_frame_stiffness_modifiers   (beams / columns / braces)
  - etabs_assign_area_stiffness_modifiers    (walls / slabs / decks)
  - etabs_apply_aci_stiffness_modifiers      (one-shot convenience for all 4 categories)

These wrap the ETABS API methods:
  - FrameObj.SetModifiers(name, [Area, M2, M3, Torsion, M2_wt, M3_wt, Mass, Weight])
  - AreaObj.SetModifiers (name, [F11,    F22,  F12,  M11,   M22,  M12,  V13,  V23])

ACI 318-19 Table 6.6.3.1.1(a) effective-stiffness values are baked in as
named presets so an LLM can apply them with a single tool call.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response


# ────────────────────────────────────────────────────────────────────
#  ACI 318-19 Table 6.6.3.1.1(a) presets
# ────────────────────────────────────────────────────────────────────
#
# Frame modifier array order (8 elements):
#   [0] Area      [1] M2 (minor-axis I)   [2] M3 (major-axis I)
#   [3] Torsion   [4] M2_weight            [5] M3_weight
#   [6] Mass      [7] Weight
#
# Values are multipliers on gross-section stiffness (1.0 = uncracked).
# Mass and Weight are typically left at 1.0.
FRAME_PRESETS: dict[str, list[float]] = {
    # ACI 318-19 Table 6.6.3.1.1(a) — beams
    "aci_beam":              [1.00, 0.35, 0.35, 0.20, 1.0, 1.0, 1.0, 1.0],
    # More conservative beam (older practice / heavy cracking)
    "aci_beam_conservative": [1.00, 0.25, 0.25, 0.10, 1.0, 1.0, 1.0, 1.0],
    # Columns
    "aci_column":            [0.70, 0.70, 0.70, 0.70, 1.0, 1.0, 1.0, 1.0],
    # Columns in some load combos (e.g. wind drift checks)
    "aci_column_conservative":[0.50, 0.50, 0.50, 0.50, 1.0, 1.0, 1.0, 1.0],
    # Coupling beams / spandrels (heavily cracked)
    "aci_spandrel":          [1.00, 0.20, 0.20, 0.10, 1.0, 1.0, 1.0, 1.0],
    # Steel beams (uncracked, but minor-axis reduced per AISC serviceability practice)
    "aisc_beam":             [1.00, 1.00, 1.00, 1.00, 1.0, 1.0, 1.0, 1.0],

    # ── IS 456:2000 Cl. 22.3 — cracked section modifiers (Indian practice) ──
    # ETABS Indian design practice values (consistent with IS 456:2000 Cl. 22.3
    # and widely accepted in IS 1893 ductile frame modelling)
    "is456_beam":            [1.00, 0.35, 0.35, 0.10, 1.0, 1.0, 1.0, 1.0],  # matches ACI beam
    "is456_column":          [0.70, 0.70, 0.70, 0.70, 1.0, 1.0, 1.0, 1.0],  # matches ACI column
    # Conservative for heavily cracked beams under seismic (SMRF)
    "is456_beam_seismic":    [1.00, 0.25, 0.25, 0.10, 1.0, 1.0, 1.0, 1.0],
    # Shear walls — IS 456 / IS 13920:2016 uncracked
    "is456_shear_wall":      [0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 1.0, 1.0],
}

# Area modifier array order (8 elements):
#   [0] F11  [1] F22  [2] F12     (membrane)
#   [3] M11  [4] M22  [5] M12     (out-of-plane bending)
#   [6] V13  [7] V23              (transverse shear)
AREA_PRESETS: dict[str, list[float]] = {
    # ACI 318-19 — uncracked wall (pier)
    "aci_wall":              [0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 1.0, 1.0],
    # Cracked wall (coupling, severely cracked)
    "aci_wall_cracked":      [0.35, 0.35, 0.35, 0.35, 0.35, 0.35, 1.0, 1.0],
    # Flat plate / two-way slab
    "aci_slab":              [1.00, 1.00, 1.00, 0.25, 0.25, 0.25, 1.0, 1.0],
    # Slab with joists / ribs (stiffer in bending)
    "aci_slab_joist":        [1.00, 1.00, 1.00, 0.50, 0.50, 0.50, 1.0, 1.0],
    # Drop panels (between slab and full-depth)
    "aci_drop_panel":        [1.00, 1.00, 1.00, 0.50, 0.50, 0.50, 1.0, 1.0],
    # Steel deck (unmodified)
    "steel_deck":            [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.0, 1.0],

    # ── IS 456:2000 / IS 13920:2016 — Indian practice for walls and slabs ──
    # Shear wall — uncracked (matches ACI wall value, common Indian practice)
    "is456_wall":            [0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 1.0, 1.0],
    # Shear wall — cracked per IS 13920:2016 (heavily cracked, ductile)
    "is456_wall_cracked":    [0.35, 0.35, 0.35, 0.35, 0.35, 0.35, 1.0, 1.0],
    # Two-way slab — IS 456:2000 effective moment of inertia (gross × 0.25-0.35)
    "is456_slab":            [1.00, 1.00, 1.00, 0.25, 0.25, 0.25, 1.0, 1.0],
    # Flat slab / drop-panel system — slightly higher bending stiffness
    "is456_flat_slab":       [1.00, 1.00, 1.00, 0.35, 0.35, 0.35, 1.0, 1.0],
    # Ribbed / joist slab — closer to gross-section behavior
    "is456_ribbed_slab":     [1.00, 1.00, 1.00, 0.50, 0.50, 0.50, 1.0, 1.0],
}


# ────────────────────────────────────────────────────────────────────
#  Internal helpers
# ────────────────────────────────────────────────────────────────────

def _resolve_frame_names(sm: Any, names: Optional[list[str]], group: str) -> list[str]:
    """Resolve the list of frame names to act on."""
    if names:
        return list(names)
    if group:
        ret = sm.FrameObj.GetNameListInGroup(group, 0, [])
        if isinstance(ret, tuple) and ret[0] == 0 and len(ret) > 2:
            return list(ret[2])
        return []
    # All frames
    ret = sm.FrameObj.GetNameList(0, [])
    if isinstance(ret, tuple) and ret[0] == 0 and len(ret) > 2:
        return list(ret[2])
    return []


def _resolve_area_names(sm: Any, names: Optional[list[str]], group: str) -> list[str]:
    """Resolve the list of area names to act on."""
    if names:
        return list(names)
    if group:
        ret = sm.AreaObj.GetNameListInGroup(group, 0, [])
        if isinstance(ret, tuple) and ret[0] == 0 and len(ret) > 2:
            return list(ret[2])
        return []
    # All areas
    ret = sm.AreaObj.GetNameList(0, [])
    if isinstance(ret, tuple) and ret[0] == 0 and len(ret) > 2:
        return list(ret[2])
    return []


def _apply_frame_mods(sm: Any, names: list[str], mods: list[float]) -> int:
    """Apply modifier array to a list of frame objects. Returns count applied."""
    count = 0
    for name in names:
        ret = sm.FrameObj.SetModifiers(name, mods)
        if isinstance(ret, tuple):
            check_ret(ret[0], f"FrameObj.SetModifiers({name})")
        else:
            check_ret(ret, f"FrameObj.SetModifiers({name})")
        count += 1
    return count


def _apply_area_mods(sm: Any, names: list[str], mods: list[float]) -> int:
    """Apply modifier array to a list of area objects. Returns count applied."""
    count = 0
    for name in names:
        ret = sm.AreaObj.SetModifiers(name, mods)
        if isinstance(ret, tuple):
            check_ret(ret[0], f"AreaObj.SetModifiers({name})")
        else:
            check_ret(ret, f"AreaObj.SetModifiers({name})")
        count += 1
    return count


# ────────────────────────────────────────────────────────────────────
#  Tool registration
# ────────────────────────────────────────────────────────────────────

def register(mcp: FastMCP) -> None:
    """Register stiffness-modifier tools on the MCP server."""

    # ────────────────────────────────────────────────────────────────
    #  Tool 1: Frame stiffness modifiers (beams, columns, braces)
    # ────────────────────────────────────────────────────────────────
    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_assign_frame_stiffness_modifiers(
        names: Optional[list[str]] = None,
        group: str = "",
        preset: str = "",
        area: Optional[float] = None,
        m2: Optional[float] = None,
        m3: Optional[float] = None,
        torsion: Optional[float] = None,
        mass: Optional[float] = None,
        weight: Optional[float] = None,
    ) -> str:
        """Apply cracked-section stiffness modifiers to one or more frame
        objects (beams, columns, braces).

        Pick a target with either `names` (explicit list), `group` (named
        ETABS group), or leave both blank to apply to ALL frames.

        Pick a `preset` for ACI defaults, OR supply individual modifier
        values. If both are given, individual values override the preset.

        Presets (ACI 318-19 Table 6.6.3.1.1(a) + IS 456:2000 / IS 13920:2016):
          - "aci_beam"               I = 0.35 Ig, torsion = 0.20
          - "aci_beam_conservative"  I = 0.25 Ig, torsion = 0.10
          - "aci_column"             I = 0.70 Ig, A = 0.70 Ag
          - "aci_column_conservative" I = 0.50 Ig
          - "aci_spandrel"           I = 0.20 Ig  (coupling beams)
          - "aisc_beam"              unmodified (steel)
          - "is456_beam"             I = 0.35 Ig, torsion = 0.10 (IS 456 RC beam)
          - "is456_column"           I = 0.70 Ig, A = 0.70 Ag (IS 456 RC column)
          - "is456_beam_seismic"     I = 0.25 Ig, torsion = 0.10 (SMRF / IS 13920)
          - "is456_shear_wall"       I = 0.70 Ig, A = 0.70 Ag (IS 13920 uncracked)

        Args:
            names: List of frame object names (e.g. ["B1", "B2"]).
                   None/empty → apply to group, or to all frames if group is also blank.
            group: Apply to all frames in this named ETABS group.
            preset: One of the preset names above (case-insensitive).
            area:   Axial stiffness modifier (overrides preset).
            m2:     Minor-axis bending modifier (overrides preset).
            m3:     Major-axis bending modifier (overrides preset).
            torsion:Torsional stiffness modifier (overrides preset).
            mass:   Mass modifier (default 1.0 if neither preset nor arg given).
            weight: Self-weight modifier (default 1.0).

        Returns:
            JSON with the modifier values applied and the number of frames updated.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            # Build modifier array
            if preset:
                key = preset.lower()
                if key not in FRAME_PRESETS:
                    return error_response(
                        f"Unknown preset '{preset}'.",
                        suggestion=f"Valid presets: {', '.join(FRAME_PRESETS.keys())}",
                    )
                mods = list(FRAME_PRESETS[key])
                # Individual overrides
                if area    is not None: mods[0] = area
                if m2      is not None: mods[1] = m2
                if m3      is not None: mods[2] = m3
                if torsion is not None: mods[3] = torsion
                if mass    is not None: mods[6] = mass
                if weight  is not None: mods[7] = weight
            else:
                mods = [
                    area    if area    is not None else 1.0,
                    m2      if m2      is not None else 1.0,
                    m3      if m3      is not None else 1.0,
                    torsion if torsion is not None else 1.0,
                    1.0, 1.0,  # m2_weight, m3_weight — not exposed, default 1.0
                    mass    if mass    is not None else 1.0,
                    weight  if weight  is not None else 1.0,
                ]

            target_names = _resolve_frame_names(sm, names, group)
            if not target_names:
                return error_response(
                    "No frame objects found to modify.",
                    suggestion="Provide `names`, `group`, or leave both blank for all frames.",
                )

            count = _apply_frame_mods(sm, target_names, mods)

            return success_response(
                {
                    "frames_modified": count,
                    "preset": (preset.lower() if preset else "custom"),
                    "modifiers": {
                        "area": mods[0], "m2": mods[1], "m3": mods[2],
                        "torsion": mods[3],
                        "m2_weight": mods[4], "m3_weight": mods[5],
                        "mass": mods[6], "weight": mods[7],
                    },
                },
                message=f"Applied stiffness modifiers to {count} frame(s).",
            )
        except Exception as exc:
            return error_response(str(exc))

    # ────────────────────────────────────────────────────────────────
    #  Tool 2: Area stiffness modifiers (walls, slabs, decks)
    # ────────────────────────────────────────────────────────────────
    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_assign_area_stiffness_modifiers(
        names: Optional[list[str]] = None,
        group: str = "",
        preset: str = "",
        f11: Optional[float] = None,
        f22: Optional[float] = None,
        f12: Optional[float] = None,
        m11: Optional[float] = None,
        m22: Optional[float] = None,
        m12: Optional[float] = None,
        v13: Optional[float] = None,
        v23: Optional[float] = None,
    ) -> str:
        """Apply cracked-section stiffness modifiers to one or more area
        objects (walls, slabs, decks).

        Pick a target with `names`, `group`, or leave both blank for ALL areas.

        Presets (ACI 318-19 Table 6.6.3.1.1(a) + IS 456:2000 / IS 13920:2016):
          - "aci_wall"            I = 0.70 Ig, A = 0.70 Ag (uncracked)
          - "aci_wall_cracked"    I = 0.35 Ig, A = 0.35 Ag
          - "aci_slab"            I = 0.25 Ig (flat plate / two-way slab)
          - "aci_slab_joist"      I = 0.50 Ig (slab with joists / ribs)
          - "aci_drop_panel"      I = 0.50 Ig
          - "steel_deck"          unmodified
          - "is456_wall"          I = 0.70 Ig, A = 0.70 Ag (IS 13920 uncracked)
          - "is456_wall_cracked"  I = 0.35 Ig, A = 0.35 Ag (IS 13920 ductile)
          - "is456_slab"          I = 0.25 Ig (IS 456 two-way slab)
          - "is456_flat_slab"     I = 0.35 Ig (IS 456 flat slab / drop panel)
          - "is456_ribbed_slab"   I = 0.50 Ig (IS 456 ribbed / joist slab)

        Args:
            names: List of area object names. None → group, or all areas.
            group: Named ETABS group.
            preset: One of the preset names above (case-insensitive).
            f11, f22, f12: Membrane (in-plane) stiffness modifiers.
            m11, m22, m12: Bending (out-of-plane) stiffness modifiers.
            v13, v23:      Transverse shear modifiers.

        Returns:
            JSON with the modifier values applied and the number of areas updated.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            if preset:
                key = preset.lower()
                if key not in AREA_PRESETS:
                    return error_response(
                        f"Unknown preset '{preset}'.",
                        suggestion=f"Valid presets: {', '.join(AREA_PRESETS.keys())}",
                    )
                mods = list(AREA_PRESETS[key])
                if f11 is not None: mods[0] = f11
                if f22 is not None: mods[1] = f22
                if f12 is not None: mods[2] = f12
                if m11 is not None: mods[3] = m11
                if m22 is not None: mods[4] = m22
                if m12 is not None: mods[5] = m12
                if v13 is not None: mods[6] = v13
                if v23 is not None: mods[7] = v23
            else:
                mods = [
                    f11 if f11 is not None else 1.0,
                    f22 if f22 is not None else 1.0,
                    f12 if f12 is not None else 1.0,
                    m11 if m11 is not None else 1.0,
                    m22 if m22 is not None else 1.0,
                    m12 if m12 is not None else 1.0,
                    v13 if v13 is not None else 1.0,
                    v23 if v23 is not None else 1.0,
                ]

            target_names = _resolve_area_names(sm, names, group)
            if not target_names:
                return error_response(
                    "No area objects found to modify.",
                    suggestion="Provide `names`, `group`, or leave both blank for all areas.",
                )

            count = _apply_area_mods(sm, target_names, mods)

            return success_response(
                {
                    "areas_modified": count,
                    "preset": (preset.lower() if preset else "custom"),
                    "modifiers": {
                        "f11": mods[0], "f22": mods[1], "f12": mods[2],
                        "m11": mods[3], "m22": mods[4], "m12": mods[5],
                        "v13": mods[6], "v23": mods[7],
                    },
                },
                message=f"Applied stiffness modifiers to {count} area(s).",
            )
        except Exception as exc:
            return error_response(str(exc))

    # ────────────────────────────────────────────────────────────────
    #  Tool 3: One-shot ACI modifier application for all 4 categories
    # ────────────────────────────────────────────────────────────────
    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_apply_aci_stiffness_modifiers(
        beam_names: Optional[list[str]] = None,
        column_names: Optional[list[str]] = None,
        wall_names: Optional[list[str]] = None,
        slab_names: Optional[list[str]] = None,
        beam_group: str = "",
        column_group: str = "",
        wall_group: str = "",
        slab_group: str = "",
        beam_preset: str = "aci_beam",
        column_preset: str = "aci_column",
        wall_preset: str = "aci_wall",
        slab_preset: str = "aci_slab",
    ) -> str:
        """One-shot convenience: apply ACI 318 stiffness modifiers to beams,
        columns, walls, and slabs in a single tool call.

        For each category, supply either an explicit `*_names` list OR a
        named ETABS `*_group`. Any category with neither is skipped.

        Defaults (ACI 318-19 Table 6.6.3.1.1(a)):
          - Beams    → I = 0.35 Ig, torsion = 0.20
          - Columns  → I = 0.70 Ig, A = 0.70 Ag
          - Walls    → I = 0.70 Ig, A = 0.70 Ag  (uncracked)
          - Slabs    → I = 0.25 Ig

        Example — apply to all members via groups:
            beam_group="BEAMS", column_group="COLUMNS",
            wall_group="WALLS", slab_group="SLABS"

        Example — apply to specific objects:
            beam_names=["B1","B2"], column_names=["C1","C2","C3"],
            wall_names=["W1"], slab_names=["S1","S2"]

        Args:
            beam_names / column_names / wall_names / slab_names:
                Explicit lists of object names per category.
            beam_group / column_group / wall_group / slab_group:
                Named ETABS groups to apply each preset to.
            beam_preset / column_preset / wall_preset / slab_preset:
                Override the default ACI preset for any category.
                (See etabs_assign_frame_stiffness_modifiers and
                 etabs_assign_area_stiffness_modifiers for the full preset list.)

        Returns:
            JSON summary: per-category count + preset, plus grand totals.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            summary: dict[str, Any] = {"frames": {}, "areas": {}}

            # ---- Beams (frames) ----
            beam_n = _resolve_frame_names(sm, beam_names, beam_group)
            if beam_n:
                key = beam_preset.lower()
                if key not in FRAME_PRESETS:
                    return error_response(
                        f"Unknown beam_preset '{beam_preset}'.",
                        suggestion=f"Valid frame presets: {', '.join(FRAME_PRESETS.keys())}",
                    )
                cnt = _apply_frame_mods(sm, beam_n, FRAME_PRESETS[key])
                summary["frames"]["beams"] = {
                    "count": cnt, "preset": beam_preset, "sample": beam_n[:5],
                }

            # ---- Columns (frames) ----
            col_n = _resolve_frame_names(sm, column_names, column_group)
            if col_n:
                key = column_preset.lower()
                if key not in FRAME_PRESETS:
                    return error_response(
                        f"Unknown column_preset '{column_preset}'.",
                        suggestion=f"Valid frame presets: {', '.join(FRAME_PRESETS.keys())}",
                    )
                cnt = _apply_frame_mods(sm, col_n, FRAME_PRESETS[key])
                summary["frames"]["columns"] = {
                    "count": cnt, "preset": column_preset, "sample": col_n[:5],
                }

            # ---- Walls (areas) ----
            wall_n = _resolve_area_names(sm, wall_names, wall_group)
            if wall_n:
                key = wall_preset.lower()
                if key not in AREA_PRESETS:
                    return error_response(
                        f"Unknown wall_preset '{wall_preset}'.",
                        suggestion=f"Valid area presets: {', '.join(AREA_PRESETS.keys())}",
                    )
                cnt = _apply_area_mods(sm, wall_n, AREA_PRESETS[key])
                summary["areas"]["walls"] = {
                    "count": cnt, "preset": wall_preset, "sample": wall_n[:5],
                }

            # ---- Slabs (areas) ----
            slab_n = _resolve_area_names(sm, slab_names, slab_group)
            if slab_n:
                key = slab_preset.lower()
                if key not in AREA_PRESETS:
                    return error_response(
                        f"Unknown slab_preset '{slab_preset}'.",
                        suggestion=f"Valid area presets: {', '.join(AREA_PRESETS.keys())}",
                    )
                cnt = _apply_area_mods(sm, slab_n, AREA_PRESETS[key])
                summary["areas"]["slabs"] = {
                    "count": cnt, "preset": slab_preset, "sample": slab_n[:5],
                }

            total_frames = sum(v["count"] for v in summary["frames"].values())
            total_areas = sum(v["count"] for v in summary["areas"].values())

            if total_frames == 0 and total_areas == 0:
                return error_response(
                    "Nothing was modified — no names or groups were provided for any category.",
                    suggestion="Provide beam/column/wall/slab names or groups.",
                )

            return success_response(
                summary,
                message=(
                    f"ACI stiffness modifiers applied: "
                    f"{total_frames} frame(s), {total_areas} area(s)."
                ),
            )
        except Exception as exc:
            return error_response(str(exc))
