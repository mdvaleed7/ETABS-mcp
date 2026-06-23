"""
Seismic analysis tools — modal, response spectrum, story drift, story forces.

Covers IS 1893:2016, ASCE 7-22, and EC8 workflows.

Tools:
  - etabs_define_modal_case          Define Eigenvector or Ritz modal analysis case
  - etabs_define_response_spectrum   Define IS 1893 / ASCE 7 / EC8 response spectrum case
  - etabs_get_modal_results          Periods, frequencies, mass participation per mode
  - etabs_get_story_drifts           IS 1893 Cl. 7.11.1 / ASCE 7 Sec 12.8 drift check
  - etabs_get_story_forces           Base shear and storey shear distribution
  - etabs_set_is1893_seismic_params  IS 1893:2016 auto-seismic parameters (Zone, I, R, soil)
  - etabs_check_is1893_drift         Compute and compare storey drift ratios against code limit
"""

from __future__ import annotations

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response, to_python_list


# ─────────────────────────────────────────────────────────────────────────────
#  IS 1893:2016 Part 1 — Seismic Zone constants (Table 3)
# ─────────────────────────────────────────────────────────────────────────────

IS1893_ZONE_FACTOR: dict[str, float] = {
    "II":  0.10,
    "III": 0.16,
    "IV":  0.24,
    "V":   0.36,
}

# Soil types for IS 1893 site factor (Table 1)
IS1893_SOIL_TYPE: dict[str, str] = {
    "I":   "Hard rock / stiff soil  (vs > 760 m/s)",
    "II":  "Medium soil            (360–760 m/s)",
    "III": "Soft soil              (vs < 360 m/s)",
}

# Response reduction factor R (Table 9 IS 1893 Part 1:2016 — typical)
IS1893_R_FACTOR: dict[str, float] = {
    "OMRF":  3.0,
    "SMRF":  5.0,
    "RC_SW_OMRF": 3.0,
    "RC_SW_SMRF": 5.0,
    "STEEL_OMRF": 3.0,
    "STEEL_SMRF": 5.0,
    "CBF":   4.0,
    "EBF":   5.0,
}


def register(mcp: FastMCP) -> None:
    """Register seismic analysis tools on the MCP server."""

    # ─── 1. Modal Case Definition ────────────────────────────────────────────

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_define_modal_case(
        case_name: str = "MODAL",
        modal_type: str = "Eigenvector",
        max_modes: int = 12,
        min_modes: int = 1,
        shift_value: float = 0.0,
    ) -> str:
        """Define a modal analysis load case (Eigenvector or Ritz).

        IS 1893:2016 Cl. 7.7.5a requires at least enough modes to capture
        90% of the total seismic mass in each principal direction.
        Recommended: set max_modes = 3 × number of storeys, minimum 12.

        Args:
            case_name:   Name for the modal load case (default "MODAL").
            modal_type:  "Eigenvector" or "Ritz" (Ritz is faster for RSA).
            max_modes:   Maximum number of modes to compute.
            min_modes:   Minimum modes required.
            shift_value: Frequency shift (rad²/s²) for eigenvalue extraction;
                         0.0 for typical buildings.

        Returns:
            JSON confirmation with case name and parameters.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            # Create/update modal case
            ret = sm.LoadCases.ModalEigen.SetCase(case_name)
            _check_tuple(ret, "LoadCases.ModalEigen.SetCase")

            # Set number of modes
            ret = sm.LoadCases.ModalEigen.SetNumberModes(case_name, max_modes, min_modes)
            _check_tuple(ret, "LoadCases.ModalEigen.SetNumberModes")

            # Eigenvector shift value
            ret = sm.LoadCases.ModalEigen.SetParameters(case_name, shift_value, 1e-9, 0)
            _check_tuple(ret, "LoadCases.ModalEigen.SetParameters")

            return success_response(
                {
                    "case_name": case_name,
                    "modal_type": modal_type,
                    "max_modes": max_modes,
                    "min_modes": min_modes,
                    "note": "IS 1893:2016 Cl. 7.7.5a: capture >= 90% seismic mass. "
                            "Recommended max_modes = 3 × number_of_storeys.",
                },
                message=f"Modal case '{case_name}' defined ({modal_type}, {max_modes} modes).",
            )
        except Exception as exc:
            return error_response(
                str(exc),
                suggestion="Ensure a model is open and units are set before defining load cases.",
            )

    # ─── 2. Response Spectrum Case ───────────────────────────────────────────

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_define_response_spectrum(
        case_name: str,
        modal_case: str = "MODAL",
        direction_x: bool = True,
        direction_y: bool = True,
        direction_z: bool = False,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        scale_z: float = 1.0,
        modal_combo: str = "CQC",
        dir_combo: str = "SRSS",
        ecc_ratio: float = 0.05,
        func_name_x: str = "IS1893_X",
        func_name_y: str = "IS1893_Y",
        func_name_z: str = "",
    ) -> str:
        """Define a multi-directional Response Spectrum Analysis (RSA) load case.

        Per IS 1893:2016 Cl. 7.7.5:
          - Modal combination: CQC (preferred over SRSS for closely-spaced modes)
          - Directional combination: SRSS of X and Y
          - Accidental eccentricity: ±5% of floor plan dimension (ecc_ratio=0.05)
        
        Per ASCE 7-22 Sec. 12.9.1: same rules apply.

        The scale factors encode (Z/2R) × I × g for IS 1893 or (SD1 / R / Ie) × g
        for ASCE 7. Compute them before calling this tool or use
        etabs_set_is1893_seismic_params which calculates them automatically.

        Args:
            case_name:   Name for the RSA load case (e.g. "EQX", "RSX").
            modal_case:  Name of the modal case supplying mode shapes (default "MODAL").
            direction_x: Apply spectrum in the global X direction.
            direction_y: Apply spectrum in the global Y direction.
            direction_z: Apply spectrum in the vertical Z direction.
            scale_x:     Scale factor for X spectrum (Z·I·g / 2R for IS 1893).
            scale_y:     Scale factor for Y spectrum.
            scale_z:     Scale factor for Z spectrum (typically 0.5 × horizontal scale).
            modal_combo: Modal combination rule: "CQC" (recommended) or "SRSS".
            dir_combo:   Directional combination: "SRSS" or "ABS".
            ecc_ratio:   Accidental eccentricity ratio (default 0.05 = 5%).
            func_name_x: Name of the spectral function for X (must be pre-defined).
            func_name_y: Name of the spectral function for Y.
            func_name_z: Name of the spectral function for Z (empty = not used).

        Returns:
            JSON confirmation with RSA case parameters.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            # Create/update the RSA case
            ret = sm.LoadCases.ResponseSpectrum.SetCase(case_name)
            _check_tuple(ret, "LoadCases.ResponseSpectrum.SetCase")

            # Set the modal case (mode shapes source)
            ret = sm.LoadCases.ResponseSpectrum.SetModalCase(case_name, modal_case)
            _check_tuple(ret, "LoadCases.ResponseSpectrum.SetModalCase")

            # Modal combination rule: CQC=1, SRSS=2, ABS=3, GMC=4, NRC=5, MISSING=6
            modal_combo_map = {"CQC": 1, "SRSS": 2, "ABS": 3, "GMC": 4}
            modal_combo_val = modal_combo_map.get(modal_combo.upper(), 1)
            ret = sm.LoadCases.ResponseSpectrum.SetModalCombination(case_name, modal_combo_val, 5.0, 1, 0.0, 0.0)
            _check_tuple(ret, "LoadCases.ResponseSpectrum.SetModalCombination")

            # Directional combination: SRSS=1, ABS=2
            dir_combo_map = {"SRSS": 1, "ABS": 2}
            dir_combo_val = dir_combo_map.get(dir_combo.upper(), 1)
            ret = sm.LoadCases.ResponseSpectrum.SetDirCombination(case_name, dir_combo_val)
            _check_tuple(ret, "LoadCases.ResponseSpectrum.SetDirCombination")

            # Accidental eccentricity
            ret = sm.LoadCases.ResponseSpectrum.SetEccentricity(case_name, ecc_ratio)
            _check_tuple(ret, "LoadCases.ResponseSpectrum.SetEccentricity")

            # Load data: build lists for each active direction
            # ETABS API: SetLoads(Name, Number, LoadType[], [U1/U2/U3/R1/R2/R3], FuncName[], ScaleFactor[], Phase[], CSys[], Ang[])
            load_types: list[int] = []
            func_names: list[str] = []
            scale_factors: list[float] = []
            angles: list[float] = []

            # Direction integers: U1=1, U2=2, U3=3
            if direction_x:
                load_types.append(1)  # U1 = X translation
                func_names.append(func_name_x)
                scale_factors.append(scale_x)
                angles.append(0.0)
            if direction_y:
                load_types.append(2)  # U2 = Y translation
                func_names.append(func_name_y)
                scale_factors.append(scale_y)
                angles.append(90.0)
            if direction_z and func_name_z:
                load_types.append(3)  # U3 = Z translation
                func_names.append(func_name_z)
                scale_factors.append(scale_z)
                angles.append(0.0)

            n = len(load_types)
            phases = [0.0] * n
            csys = ["Global"] * n

            ret = sm.LoadCases.ResponseSpectrum.SetLoads(
                case_name, n, load_types, func_names, scale_factors, phases, csys, angles
            )
            _check_tuple(ret, "LoadCases.ResponseSpectrum.SetLoads")

            return success_response(
                {
                    "case_name": case_name,
                    "modal_case": modal_case,
                    "directions": {
                        "X": direction_x,
                        "Y": direction_y,
                        "Z": direction_z,
                    },
                    "scale_factors": {"X": scale_x, "Y": scale_y, "Z": scale_z},
                    "modal_combination": modal_combo,
                    "directional_combination": dir_combo,
                    "accidental_eccentricity": f"{ecc_ratio * 100:.1f}%",
                    "code_note": (
                        "IS 1893:2016 Cl. 7.7.5: CQC + SRSS + 5% eccentricity. "
                        "Scale = Z·I·g / (2R). Verify vs base shear from Cl. 7.6.1."
                    ),
                },
                message=f"RSA case '{case_name}' defined with {n} direction(s).",
            )
        except Exception as exc:
            return error_response(
                str(exc),
                suggestion=(
                    "Ensure the spectral function (func_name_x/y) is pre-defined in ETABS "
                    "Functions > Response Spectrum. Use etabs_call_api to define it if needed."
                ),
            )

    # ─── 3. Modal Results ────────────────────────────────────────────────────

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_get_modal_results(modal_case: str = "MODAL") -> str:
        """Get modal analysis results: periods, frequencies, and mass participation ratios.

        IS 1893:2016 Cl. 7.7.5a: The sum of modal masses considered shall be at
        least 90% of the total seismic mass. Verify the cumulative UX and UY
        columns against this criterion.

        Args:
            modal_case: Name of the modal load case (default "MODAL").

        Returns:
            JSON array of modes, each with:
              - mode_number, period_s, frequency_hz
              - mass_ratio_UX, mass_ratio_UY, mass_ratio_UZ  (per-mode fractions)
              - cum_UX, cum_UY, cum_UZ                       (cumulative fractions)
              - mass_ratio_RX, mass_ratio_RY, mass_ratio_RZ  (rotational)
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            # Ensure modal case is selected for output
            ret = sm.Results.Setup.DeselectAllCasesAndCombosForOutput()
            _check_tuple(ret, "Results.Setup.DeselectAllCasesAndCombosForOutput")
            ret = sm.Results.Setup.SetCaseSelectedForOutput(modal_case)
            _check_tuple(ret, "Results.Setup.SetCaseSelectedForOutput")

            # ModalParticipatingMassRatios returns:
            # Ret, NumberResults, LoadCase, StepType, StepNum,
            # Period, UX, UY, UZ, SumUX, SumUY, SumUZ, RX, RY, RZ, SumRX, SumRY, SumRZ
            ret = sm.Results.ModalParticipatingMassRatios(
                0, [], [], [], [], [], [], [], [], [], [], [], [], [], []
            )

            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response(
                    "Failed to retrieve modal mass ratios. "
                    "Ensure modal analysis has been run and results are available.",
                    suggestion="Run etabs_run_analysis first, then retry.",
                )

            n = ret[1]
            periods  = to_python_list(ret[5])
            ux       = to_python_list(ret[6])
            uy       = to_python_list(ret[7])
            uz       = to_python_list(ret[8])
            sum_ux   = to_python_list(ret[9])
            sum_uy   = to_python_list(ret[10])
            sum_uz   = to_python_list(ret[11])
            rx       = to_python_list(ret[12])
            ry       = to_python_list(ret[13])
            rz       = to_python_list(ret[14])

            modes = []
            for i in range(n):
                T = periods[i] if i < len(periods) else 0.0
                modes.append({
                    "mode": i + 1,
                    "period_s": round(T, 4),
                    "frequency_hz": round(1.0 / T, 4) if T > 0 else 0.0,
                    "mass_UX": round(ux[i], 4) if i < len(ux) else 0.0,
                    "mass_UY": round(uy[i], 4) if i < len(uy) else 0.0,
                    "mass_UZ": round(uz[i], 4) if i < len(uz) else 0.0,
                    "cum_UX": round(sum_ux[i], 4) if i < len(sum_ux) else 0.0,
                    "cum_UY": round(sum_uy[i], 4) if i < len(sum_uy) else 0.0,
                    "cum_UZ": round(sum_uz[i], 4) if i < len(sum_uz) else 0.0,
                    "mass_RX": round(rx[i], 4) if i < len(rx) else 0.0,
                    "mass_RY": round(ry[i], 4) if i < len(ry) else 0.0,
                    "mass_RZ": round(rz[i], 4) if i < len(rz) else 0.0,
                })

            # IS 1893 compliance check
            cum_ux_final = modes[-1]["cum_UX"] if modes else 0.0
            cum_uy_final = modes[-1]["cum_UY"] if modes else 0.0
            is1893_ok = cum_ux_final >= 0.90 and cum_uy_final >= 0.90

            return success_response(
                {
                    "modes": modes,
                    "is1893_90pct_check": {
                        "cum_UX": round(cum_ux_final, 4),
                        "cum_UY": round(cum_uy_final, 4),
                        "pass": is1893_ok,
                        "clause": "IS 1893:2016 Cl. 7.7.5a — sum of modal masses >= 90%",
                        "recommendation": (
                            "PASS" if is1893_ok
                            else f"FAIL — increase max_modes in '{modal_case}'. "
                                 f"Currently UX={cum_ux_final*100:.1f}%, UY={cum_uy_final*100:.1f}%"
                        ),
                    },
                },
                message=f"Retrieved {n} modes from case '{modal_case}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    # ─── 4. Story Drifts ─────────────────────────────────────────────────────

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_get_story_drifts(
        case_or_combo: str = "",
        direction: str = "Both",
        check_is1893: bool = True,
    ) -> str:
        """Get inter-storey drift ratios and check IS 1893:2016 / ASCE 7-22 limits.

        IS 1893:2016 Cl. 7.11.1: Maximum storey drift under seismic loads
        (with R = 1.0, i.e. on the Design Basis Earthquake forces) shall not
        exceed 0.004 × storey height (= h/250).

        ASCE 7-22 Table 12.12-1: Δa / hsx (varies 0.010 to 0.025 by risk category
        and structure type).

        Args:
            case_or_combo: Load case or combo name. Empty string = all selected cases.
            direction:     "X", "Y", or "Both".
            check_is1893:  If True, flag storeys exceeding IS 1893 Cl. 7.11.1 limit
                           of 0.004 (= h/250).

        Returns:
            JSON array of storeys, each with drift ratio and code-check result.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            # Select only the requested case if specified
            if case_or_combo:
                ret = sm.Results.Setup.DeselectAllCasesAndCombosForOutput()
                _check_tuple(ret, "Results.Setup.DeselectAllCasesAndCombosForOutput")
                # Try as load case first
                sm.Results.Setup.SetCaseSelectedForOutput(case_or_combo)
                # Also try as combo
                sm.Results.Setup.SetComboSelectedForOutput(case_or_combo)

            # Results.StoryDrifts returns:
            # Ret, NumberResults, Story[], LoadCase[], StepType[], StepNum[],
            # Direction[], Drift[], Label[], X[], Y[], Z[]
            ret = sm.Results.StoryDrifts(
                0, [], [], [], [], [], [], [], [], [], []
            )

            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response(
                    "Failed to retrieve story drifts. "
                    "Ensure analysis has been run and the model is locked with results.",
                    suggestion="Call etabs_run_analysis first, then etabs_setup_results, then retry.",
                )

            n        = ret[1]
            stories  = to_python_list(ret[2])
            cases    = to_python_list(ret[3])
            dirs     = to_python_list(ret[6])
            drifts   = to_python_list(ret[7])

            IS1893_LIMIT = 0.004  # h/250

            results: list[dict] = []
            for i in range(n):
                d = dirs[i] if i < len(dirs) else ""
                if direction.upper() not in ("BOTH", "ALL") and d.upper() != direction.upper():
                    continue

                drift_val = drifts[i] if i < len(drifts) else 0.0
                exceeded = drift_val > IS1893_LIMIT if check_is1893 else None

                results.append({
                    "story":     stories[i] if i < len(stories) else "",
                    "load_case": cases[i]   if i < len(cases)   else "",
                    "direction": d,
                    "drift_ratio": round(drift_val, 5),
                    "drift_h_fraction": f"h/{int(round(1.0 / drift_val)):d}" if drift_val > 0 else "0",
                    "is1893_limit": IS1893_LIMIT if check_is1893 else None,
                    "is1893_check": (
                        "FAIL ⚠" if exceeded
                        else "PASS ✓" if exceeded is not None
                        else "N/A"
                    ),
                })

            failed = [r for r in results if r.get("is1893_check", "").startswith("FAIL")]

            return success_response(
                {
                    "drifts": results,
                    "summary": {
                        "total_records": len(results),
                        "is1893_failures": len(failed),
                        "is1893_limit": IS1893_LIMIT,
                        "clause": "IS 1893:2016 Cl. 7.11.1 — drift <= 0.004h",
                        "failed_stories": [f["story"] + " " + f["direction"] for f in failed],
                    },
                },
                message=f"Retrieved {len(results)} drift records. "
                        f"IS 1893 failures: {len(failed)}.",
            )
        except Exception as exc:
            return error_response(str(exc))

    # ─── 5. Story Forces ─────────────────────────────────────────────────────

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_get_story_forces(case_or_combo: str = "") -> str:
        """Get storey forces (shear, overturning moment, axial) for each floor.

        Used to verify base shear distribution meets IS 1893:2016 Cl. 7.6.3
        (parabolic distribution of seismic forces with height).

        Args:
            case_or_combo: Load case or combo name. Empty = use currently selected.

        Returns:
            JSON array of story forces including:
              - story, load_case
              - P (axial), VX, VY (storey shear), MX, MY (overturning moment), MZ
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            if case_or_combo:
                ret = sm.Results.Setup.DeselectAllCasesAndCombosForOutput()
                _check_tuple(ret, "Results.Setup.DeselectAllCasesAndCombosForOutput")
                sm.Results.Setup.SetCaseSelectedForOutput(case_or_combo)
                sm.Results.Setup.SetComboSelectedForOutput(case_or_combo)

            # Results.StoryForces returns:
            # Ret, NumberResults, Story[], LoadCase[], StepType[], StepNum[],
            # Location[], P[], VX[], VY[], T[], MX[], MY[]
            ret = sm.Results.StoryForces(
                0, [], [], [], [], [], [], [], [], [], [], []
            )

            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response(
                    "Failed to retrieve story forces. "
                    "Ensure analysis results are available.",
                )

            n      = ret[1]
            stor   = to_python_list(ret[2])
            cases  = to_python_list(ret[3])
            locs   = to_python_list(ret[6])
            P      = to_python_list(ret[7])
            VX     = to_python_list(ret[8])
            VY     = to_python_list(ret[9])
            T      = to_python_list(ret[10])
            MX     = to_python_list(ret[11])
            MY     = to_python_list(ret[12])

            forces = []
            for i in range(n):
                forces.append({
                    "story":       stor[i]  if i < len(stor)  else "",
                    "load_case":   cases[i] if i < len(cases) else "",
                    "location":    locs[i]  if i < len(locs)  else "",
                    "P":           round(P[i],  2) if i < len(P)  else 0.0,
                    "VX":          round(VX[i], 2) if i < len(VX) else 0.0,
                    "VY":          round(VY[i], 2) if i < len(VY) else 0.0,
                    "T":           round(T[i],  2) if i < len(T)  else 0.0,
                    "MX":          round(MX[i], 2) if i < len(MX) else 0.0,
                    "MY":          round(MY[i], 2) if i < len(MY) else 0.0,
                })

            return success_response(
                forces,
                message=f"Retrieved {n} storey force records.",
            )
        except Exception as exc:
            return error_response(str(exc))

    # ─── 6. IS 1893 Auto-Seismic Parameters ─────────────────────────────────

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_set_is1893_seismic_params(
        load_case_x: str,
        load_case_y: str,
        zone: str = "III",
        importance_factor: float = 1.2,
        response_reduction: float = 5.0,
        soil_type: str = "II",
        damping_ratio: float = 0.05,
        structure_type: str = "RC_frame",
        modal_case: str = "MODAL",
        apply_scale_to_rsa: bool = True,
    ) -> str:
        """Compute and report IS 1893:2016 seismic scale factors for RSA cases.

        Calculates the scale factor  SF = (Z/2) × (I/R) × (g/Sa_g_at_T1)
        for use in etabs_define_response_spectrum.

        The full equivalent static base shear:
          VB = Ah × W   where Ah = (Z/2) × (Sa/g) × (I/R)

        For response spectrum analysis the ETABS scale factor applied to the
        spectrum function is typically:  g × I / R  (when the spectrum function
        is already in units of Sa/g, i.e. normalized). ETABS multiplies the
        function value by scale_factor to get spectral acceleration in
        length/time² units.

        Args:
            load_case_x:        Name of RSA case in X direction (e.g. "EQX").
            load_case_y:        Name of RSA case in Y direction (e.g. "EQY").
            zone:               IS 1893 seismic zone "II", "III", "IV", or "V".
            importance_factor:  I — importance factor (1.0 ordinary, 1.2 important,
                                1.5 critical). IS 1893:2016 Table 8.
            response_reduction: R — response reduction factor. IS 1893:2016 Table 9.
                                 Typical: OMRF=3.0, SMRF=5.0.
            soil_type:          Site type "I" (hard), "II" (medium), "III" (soft).
                                 IS 1893:2016 Table 1.
            damping_ratio:      Critical damping ratio (default 0.05 = 5%).
                                 IS 1893:2016 Cl. 6.4.6.
            structure_type:     "RC_frame", "Steel_frame", "Shear_wall", "Composite".
                                 Used for informational note only.
            modal_case:         Name of the modal case.
            apply_scale_to_rsa: If True, returns ready-to-use ETABS scale factor
                                (in m/s² for SI kN_m models). Set False for kip_ft models.

        Returns:
            JSON with zone factor Z, Ah, scale factors, and IS 1893 clause references.
        """
        try:
            Z = IS1893_ZONE_FACTOR.get(zone.upper())
            if Z is None:
                return error_response(
                    f"Invalid seismic zone '{zone}'.",
                    suggestion="Valid zones: II, III, IV, V (IS 1893:2016 Table 3).",
                )

            I = importance_factor
            R = response_reduction
            g = 9.81  # m/s²

            # IS 1893:2016 Cl. 6.4.2: Ah = (Z/2) × (Sa/g) / (I/R) → CHECK: it's
            # Ah = (Z × I × Sa/g) / (2R)
            # The scale factor for ETABS RSA (when spectral function = Sa/g curve):
            # SF = Z × I × g / (2 × R)
            # ETABS multiplies: SF × f(T) = (Z I g / 2R) × (Sa/g) = Z I Sa / 2R
            SF = (Z * I * g) / (2.0 * R)

            # Damping correction factor per IS 1893:2016 Table 3 (clause 6.4.6)
            # At 5% damping, factor = 1.0; at 2%, factor ≈ 1.4; at 10%, factor ≈ 0.8
            damping_correction = {
                0.02: 1.40, 0.05: 1.00, 0.07: 0.90, 0.10: 0.80,
            }
            damp_factor = damping_correction.get(damping_ratio, 1.0)
            SF_damped = SF * damp_factor

            result = {
                "is1893_parameters": {
                    "zone": zone,
                    "Z_zone_factor": Z,
                    "I_importance": I,
                    "R_response_reduction": R,
                    "soil_type": soil_type,
                    "damping_ratio": f"{damping_ratio*100:.0f}%",
                    "damping_correction": damp_factor,
                },
                "scale_factor": {
                    "formula": "SF = Z × I × g / (2R)",
                    "value_5pct_damp": round(SF, 4),
                    "value_corrected": round(SF_damped, 4),
                    "units": "m/s² (use for kN_m_C models only)",
                    "note_kip_ft": "For kip_ft models, use SF / 0.3048 to convert to ft/s²",
                },
                "load_cases": {
                    "EQX": load_case_x,
                    "EQY": load_case_y,
                    "modal_case": modal_case,
                },
                "code_references": {
                    "zone_factor": f"IS 1893:2016 Table 3 — Zone {zone}: Z = {Z}",
                    "response_reduction": "IS 1893:2016 Table 9",
                    "importance": "IS 1893:2016 Table 8",
                    "ah_formula": "IS 1893:2016 Cl. 6.4.2: Ah = Z × Sa/g × I / (2R)",
                    "modal_combination": "IS 1893:2016 Cl. 7.7.5 — CQC preferred",
                    "drift_limit": "IS 1893:2016 Cl. 7.11.1 — Δ/h ≤ 0.004",
                    "mass_participation": "IS 1893:2016 Cl. 7.7.5a — ≥ 90% seismic mass",
                },
                "workflow": [
                    "1. Define spectral function (IS 1893 Sa/g curve) in ETABS",
                    f"2. Call etabs_define_modal_case(case_name='{modal_case}', max_modes=3×N_stories)",
                    f"3. Call etabs_run_analysis() to compute modes",
                    f"4. Call etabs_get_modal_results('{modal_case}') — verify ≥ 90% mass",
                    f"5. Call etabs_define_response_spectrum('{load_case_x}', scale_x={round(SF_damped,4)})",
                    f"6. Call etabs_define_response_spectrum('{load_case_y}', scale_y={round(SF_damped,4)})",
                    "7. Run full analysis, then call etabs_get_story_drifts() for IS 1893 Cl. 7.11.1 check",
                ],
            }

            return success_response(
                result,
                message=(
                    f"IS 1893:2016 Zone {zone} — Z={Z}, I={I}, R={R}. "
                    f"ETABS scale factor = {round(SF_damped, 4)} m/s²."
                ),
            )
        except Exception as exc:
            return error_response(str(exc))

    # ─── 7. IS 1893 Drift Report ─────────────────────────────────────────────

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_check_is1893_drift(
        rsa_case_x: str,
        rsa_case_y: str,
        story_heights_m: Optional[dict[str, float]] = None,
    ) -> str:
        """Run IS 1893:2016 Cl. 7.11.1 inter-storey drift compliance check.

        Retrieves drifts for both seismic directions and classifies each storey
        as PASS/FAIL against the 0.004h limit (= h/250).

        IS 1893:2016 Cl. 7.11.1:
          The storey drift in any storey due to the minimum specified design
          lateral force, with partial load factor of 1.0, shall not exceed
          0.004 times the storey height (h/250).

        Args:
            rsa_case_x:        RSA load case name for X seismic (e.g. "EQX").
            rsa_case_y:        RSA load case name for Y seismic (e.g. "EQY").
            story_heights_m:   Optional dict of {story_name: height_m} to compute
                               absolute drift in mm. If None, uses drift ratio only.

        Returns:
            Tabulated compliance report with PASS/FAIL per storey per direction.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            IS1893_LIMIT = 0.004  # h/250

            all_records: list[dict] = []

            for direction, case_name in [("X", rsa_case_x), ("Y", rsa_case_y)]:
                ret = sm.Results.Setup.DeselectAllCasesAndCombosForOutput()
                _check_tuple(ret, "Results.Setup.DeselectAllCasesAndCombosForOutput")
                sm.Results.Setup.SetCaseSelectedForOutput(case_name)
                sm.Results.Setup.SetComboSelectedForOutput(case_name)

                ret = sm.Results.StoryDrifts(0, [], [], [], [], [], [], [], [], [], [])
                if not isinstance(ret, tuple) or ret[0] != 0:
                    continue

                n     = ret[1]
                stor  = to_python_list(ret[2])
                cases = to_python_list(ret[3])
                dirs  = to_python_list(ret[6])
                drifts = to_python_list(ret[7])

                for i in range(n):
                    story_name = stor[i] if i < len(stor) else ""
                    drift_val  = drifts[i] if i < len(drifts) else 0.0
                    dir_val    = dirs[i] if i < len(dirs) else ""

                    # Only keep the drift in the loading direction
                    if direction not in dir_val.upper():
                        continue

                    h_m = (story_heights_m or {}).get(story_name, None)
                    abs_drift_mm = round(drift_val * h_m * 1000, 1) if h_m else None

                    all_records.append({
                        "story":      story_name,
                        "direction":  direction,
                        "load_case":  case_name,
                        "drift_ratio": round(drift_val, 6),
                        "drift_h_over": f"h/{int(round(1.0/drift_val)):d}" if drift_val > 0 else "∞",
                        "abs_drift_mm": abs_drift_mm,
                        "is1893_limit": IS1893_LIMIT,
                        "check": "FAIL ⚠" if drift_val > IS1893_LIMIT else "PASS ✓",
                        "excess_pct": (
                            round((drift_val / IS1893_LIMIT - 1.0) * 100, 1)
                            if drift_val > IS1893_LIMIT else 0.0
                        ),
                    })

            failed = [r for r in all_records if r["check"].startswith("FAIL")]
            max_drift = max((r["drift_ratio"] for r in all_records), default=0.0)

            return success_response(
                {
                    "records": all_records,
                    "summary": {
                        "total_checks": len(all_records),
                        "failures": len(failed),
                        "max_drift_ratio": round(max_drift, 6),
                        "max_drift_h_over": f"h/{int(round(1.0/max_drift)):d}" if max_drift > 0 else "∞",
                        "is1893_limit": IS1893_LIMIT,
                        "is1893_clause": "IS 1893:2016 Cl. 7.11.1",
                        "failed_storeys": [
                            f"{r['story']} ({r['direction']}) — {r['drift_h_over']}"
                            for r in failed
                        ],
                        "overall": "COMPLIANT ✓" if not failed else f"NON-COMPLIANT ⚠ ({len(failed)} failures)",
                    },
                },
                message=(
                    f"IS 1893 drift check complete. "
                    f"{'All storeys comply.' if not failed else f'{len(failed)} storey(s) exceed h/250.'}"
                ),
            )
        except Exception as exc:
            return error_response(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
#  Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_tuple(ret: object, method_name: str) -> None:
    """Check a COM return value — tolerates both scalar and tuple returns."""
    from etabs_mcp.helpers import check_ret
    if isinstance(ret, tuple):
        check_ret(ret[0], method_name)
    elif isinstance(ret, int):
        check_ret(ret, method_name)
