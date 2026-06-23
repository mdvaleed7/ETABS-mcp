"""
Design tools — structural design checks.

Tools:
  - etabs_run_steel_design
  - etabs_run_concrete_design
  - etabs_get_design_results_summary
  - etabs_set_design_code
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import ITEM_TYPE, check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register design tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_run_steel_design() -> str:
        """Run the steel frame design check.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.DesignSteel.StartDesign()
            if isinstance(ret, tuple):
                check_ret(ret[0], "DesignSteel.StartDesign")
            else:
                check_ret(ret, "DesignSteel.StartDesign")

            return success_response(message="Steel frame design completed.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_run_concrete_design() -> str:
        """Run the concrete frame design check.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.DesignConcrete.StartDesign()
            if isinstance(ret, tuple):
                check_ret(ret[0], "DesignConcrete.StartDesign")
            else:
                check_ret(ret, "DesignConcrete.StartDesign")

            return success_response(message="Concrete frame design completed.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_design_results_summary(
        design_type: str,
        name: str = "",
        item_type: str = "Object",
    ) -> str:
        """Get a summary of design results for frames.

        Args:
            design_type: "Steel" or "Concrete".
            name: Object or group name. Leave empty for all objects.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            JSON array of design summary results (e.g., PMM ratio).
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            
            if design_type.lower() == "steel":
                ret = sm.DesignSteel.GetSummaryResults(name, 0, [], [], [], [], [], [], it)
                if not isinstance(ret, tuple) or ret[0] != 0:
                    return error_response("Failed to get steel design summary.")
                
                num = ret[1]
                frame_names = to_python_list(ret[2])
                ratios = to_python_list(ret[3])
                ratio_types = to_python_list(ret[4])
                locations = to_python_list(ret[5])
                combos = to_python_list(ret[6])
                errors = to_python_list(ret[7])
                
                results = []
                for i in range(num):
                    results.append({
                        "frame": frame_names[i],
                        "ratio": ratios[i],
                        "ratio_type": ratio_types[i],
                        "location": locations[i],
                        "combo": combos[i],
                        "error": errors[i],
                    })
                return success_response(results, message=f"Retrieved {num} steel design results.")
                
            elif design_type.lower() == "concrete":
                ret = sm.DesignConcrete.GetSummaryResultsColumn(name, 0, [], [], [], [], [], [], [], [], it)
                # Note: This is just for columns for brevity. Concrete design is split into beams/columns/joints.
                if not isinstance(ret, tuple) or ret[0] != 0:
                    return error_response("Failed to get concrete column design summary (try generic database tables tool for complete results).")
                
                num = ret[1]
                frame_names = to_python_list(ret[2])
                my_options = to_python_list(ret[3])
                locations = to_python_list(ret[4])
                pmm_combos = to_python_list(ret[5])
                pmm_areas = to_python_list(ret[6])
                pmm_ratios = to_python_list(ret[7])
                v_combos = to_python_list(ret[8])
                v_areas = to_python_list(ret[9])
                errors = to_python_list(ret[10])
                
                results = []
                for i in range(num):
                    results.append({
                        "frame": frame_names[i],
                        "location": locations[i],
                        "pmm_combo": pmm_combos[i],
                        "pmm_ratio": pmm_ratios[i],
                        "error": errors[i],
                    })
                return success_response(results, message=f"Retrieved {num} concrete column design results.")
            else:
                return error_response("design_type must be 'Steel' or 'Concrete'.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_set_design_code(
        design_type: str,
        code_name: str,
    ) -> str:
        """Set the design code for steel or concrete design.

        Args:
            design_type: "Steel" or "Concrete".
            code_name: The exact string name of the code (e.g., "AISC 360-16", "ACI 318-19").

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            if design_type.lower() == "steel":
                ret = sm.DesignSteel.SetCode(code_name)
                if isinstance(ret, tuple):
                    check_ret(ret[0], "DesignSteel.SetCode")
                else:
                    check_ret(ret, "DesignSteel.SetCode")
            elif design_type.lower() == "concrete":
                ret = sm.DesignConcrete.SetCode(code_name)
                if isinstance(ret, tuple):
                    check_ret(ret[0], "DesignConcrete.SetCode")
                else:
                    check_ret(ret, "DesignConcrete.SetCode")
            else:
                return error_response("design_type must be 'Steel' or 'Concrete'.")

            return success_response({"type": design_type, "code": code_name}, message=f"Design code set to {code_name}.")
        except Exception as exc:
            return error_response(str(exc))
