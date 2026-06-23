"""
Analysis tools — configuration and execution.

Tools:
  - etabs_run_analysis
  - etabs_get_analysis_status
  - etabs_set_active_dof
  - etabs_delete_results
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register analysis tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_run_analysis() -> str:
        """Run the structural analysis for all active load cases.

        Note: The model must be saved (have a file path) before running analysis.

        Returns:
            Confirmation of analysis completion.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.Analyze.RunAnalysis()
            if isinstance(ret, tuple):
                check_ret(ret[0], "Analyze.RunAnalysis")
            else:
                check_ret(ret, "Analyze.RunAnalysis")

            return success_response(message="Analysis completed successfully.")
        except Exception as exc:
            return error_response(
                str(exc),
                suggestion="Make sure the model is saved before running the analysis.",
            )

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_analysis_status() -> str:
        """Get the status of all analysis cases.

        Returns:
            JSON array of load cases and their status (e.g. "Finished", "Not Run").
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.Analyze.GetCaseStatus(0, [], [])
            if isinstance(ret, tuple) and ret[0] == 0:
                names = to_python_list(ret[2]) if len(ret) > 2 else []
                statuses_int = to_python_list(ret[3]) if len(ret) > 3 else []
                
                status_map = {1: "Not Run", 2: "Could Not Start", 3: "Not Finished", 4: "Finished"}
                
                cases = []
                for idx, name in enumerate(names):
                    s_int = statuses_int[idx] if idx < len(statuses_int) else 0
                    cases.append({"case": name, "status": status_map.get(s_int, "Unknown")})
                    
                return success_response(cases, message=f"Found {len(cases)} analysis case(s).")
            return success_response([], message="No analysis cases found.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_set_active_dof(
        u1: bool = True, u2: bool = True, u3: bool = True,
        r1: bool = True, r2: bool = True, r3: bool = True,
    ) -> str:
        """Set the active degrees of freedom for the analysis (e.g. 3D, 2D X-Z).

        For 3D space: all True.
        For 2D X-Z plane: u1=True, u3=True, r2=True, others False.

        Args:
            u1, u2, u3: Active translations (X, Y, Z).
            r1, r2, r3: Active rotations (about X, Y, Z).

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            dof = [u1, u2, u3, r1, r2, r3]
            ret = sm.Analyze.SetActiveDOF(dof)
            if isinstance(ret, tuple):
                check_ret(ret[0], "Analyze.SetActiveDOF")
            else:
                check_ret(ret, "Analyze.SetActiveDOF")

            return success_response({"dof": dof}, message="Active DOF set.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_delete_results() -> str:
        """Delete all analysis results, unlocking the model.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.Analyze.DeleteResults(0, "")
            if isinstance(ret, tuple):
                check_ret(ret[0], "Analyze.DeleteResults")
            else:
                check_ret(ret, "Analyze.DeleteResults")

            return success_response(message="Analysis results deleted. Model is unlocked.")
        except Exception as exc:
            return error_response(str(exc))
