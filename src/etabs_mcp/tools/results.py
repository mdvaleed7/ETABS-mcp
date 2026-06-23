"""
Results tools — extracting analysis results.

Tools:
  - etabs_setup_results
  - etabs_get_joint_displacements
  - etabs_get_joint_reactions
  - etabs_get_frame_forces
  - etabs_get_base_reactions
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import ITEM_TYPE, check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register results extraction tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_setup_results(
        case_names: list[str] | None = None,
        combo_names: list[str] | None = None,
    ) -> str:
        """Configure which load cases/combos to include when extracting results.

        MUST be called before getting displacements, forces, or reactions if you want
        to filter the results.

        Args:
            case_names: List of load cases to select.
            combo_names: List of load combos to select.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.Results.Setup.DeselectAllCasesAndCombosForOutput()
            if isinstance(ret, tuple):
                check_ret(ret[0], "Results.Setup.DeselectAllCasesAndCombosForOutput")
            else:
                check_ret(ret, "Results.Setup.DeselectAllCasesAndCombosForOutput")

            if case_names:
                for name in case_names:
                    ret = sm.Results.Setup.SetCaseSelectedForOutput(name)
            if combo_names:
                for name in combo_names:
                    ret = sm.Results.Setup.SetComboSelectedForOutput(name)

            return success_response(
                {"cases": case_names, "combos": combo_names},
                message="Result output configuration updated.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_joint_displacements(
        name: str,
        item_type: str = "Object",
    ) -> str:
        """Get joint displacements for a specified point or group.

        Ensure analysis has been run and results are set up.

        Args:
            name: Name of the point or group.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            JSON array of displacements per load case/combo.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.Results.JointDispl(name, it, 0, [], [], [], [], [], [], [], [], [], [])
            
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response("Failed to get joint displacements or no results available.")

            num = ret[1]
            obj_names = to_python_list(ret[2])
            elm_names = to_python_list(ret[3])
            load_cases = to_python_list(ret[4])
            step_types = to_python_list(ret[5])
            step_nums = to_python_list(ret[6])
            u1 = to_python_list(ret[7])
            u2 = to_python_list(ret[8])
            u3 = to_python_list(ret[9])
            r1 = to_python_list(ret[10])
            r2 = to_python_list(ret[11])
            r3 = to_python_list(ret[12])

            results = []
            for i in range(num):
                results.append({
                    "object": obj_names[i],
                    "load_case": load_cases[i],
                    "step": f"{step_types[i]} {step_nums[i]}",
                    "U1": u1[i], "U2": u2[i], "U3": u3[i],
                    "R1": r1[i], "R2": r2[i], "R3": r3[i],
                })

            return success_response(results, message=f"Retrieved {num} displacement records.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_joint_reactions(
        name: str,
        item_type: str = "Object",
    ) -> str:
        """Get joint reactions (support forces) for a specified point or group.

        Ensure analysis has been run and results are set up.

        Args:
            name: Name of the point or group.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            JSON array of reactions per load case/combo.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.Results.JointReact(name, it, 0, [], [], [], [], [], [], [], [], [], [])
            
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response("Failed to get joint reactions or no results available.")

            num = ret[1]
            obj_names = to_python_list(ret[2])
            load_cases = to_python_list(ret[4])
            f1 = to_python_list(ret[7])
            f2 = to_python_list(ret[8])
            f3 = to_python_list(ret[9])
            m1 = to_python_list(ret[10])
            m2 = to_python_list(ret[11])
            m3 = to_python_list(ret[12])

            results = []
            for i in range(num):
                results.append({
                    "object": obj_names[i],
                    "load_case": load_cases[i],
                    "F1": f1[i], "F2": f2[i], "F3": f3[i],
                    "M1": m1[i], "M2": m2[i], "M3": m3[i],
                })

            return success_response(results, message=f"Retrieved {num} reaction records.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_frame_forces(
        name: str,
        item_type: str = "Object",
    ) -> str:
        """Get frame internal forces (P, V2, V3, T, M2, M3).

        Ensure analysis has been run and results are set up.

        Args:
            name: Name of the frame or group.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            JSON array of frame forces.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.Results.FrameForce(name, it, 0, [], [], [], [], [], [], [], [], [], [], [])
            
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response("Failed to get frame forces or no results available.")

            num = ret[1]
            obj_names = to_python_list(ret[2])
            obj_sta = to_python_list(ret[3])
            load_cases = to_python_list(ret[5])
            p = to_python_list(ret[8])
            v2 = to_python_list(ret[9])
            v3 = to_python_list(ret[10])
            t = to_python_list(ret[11])
            m2 = to_python_list(ret[12])
            m3 = to_python_list(ret[13])

            results = []
            for i in range(num):
                results.append({
                    "object": obj_names[i],
                    "station": obj_sta[i],
                    "load_case": load_cases[i],
                    "P": p[i], "V2": v2[i], "V3": v3[i],
                    "T": t[i], "M2": m2[i], "M3": m3[i],
                })

            return success_response(results, message=f"Retrieved {num} frame force records.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_base_reactions() -> str:
        """Get global base reactions for the model.

        Returns:
            JSON array of base reactions per load case.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.Results.BaseReact(0, [], [], [], [], [], [], [], [], [], [], [], [])
            
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response("Failed to get base reactions or no results available.")

            num = ret[1]
            load_cases = to_python_list(ret[2])
            fx = to_python_list(ret[5])
            fy = to_python_list(ret[6])
            fz = to_python_list(ret[7])
            mx = to_python_list(ret[8])
            my = to_python_list(ret[9])
            mz = to_python_list(ret[10])

            results = []
            for i in range(num):
                results.append({
                    "load_case": load_cases[i],
                    "FX": fx[i], "FY": fy[i], "FZ": fz[i],
                    "MX": mx[i], "MY": my[i], "MZ": mz[i],
                })

            return success_response(results, message=f"Retrieved {num} base reaction records.")
        except Exception as exc:
            return error_response(str(exc))
