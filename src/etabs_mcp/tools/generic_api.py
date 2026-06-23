"""
Generic API tool — escape hatch for the full ETABS COM API.

Tools:
  - etabs_call_api
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register the generic API tool on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    def etabs_call_api(
        interface_path: str,
        method_name: str,
        arguments: list[Any] | None = None,
    ) -> str:
        """Call ANY method in the ETABS API that isn't covered by other tools.

        This is a powerful escape hatch to access all 1,300+ methods in the API.
        
        Examples:
          - interface_path="FrameObj", method_name="GetLabelFromName", arguments=["F1", "", ""]
          - interface_path="Results.Setup", method_name="GetCaseSelectedForOutput", arguments=["DEAD", False]
          - interface_path="", method_name="GetModelFilename", arguments=[] (uses SapModel directly)

        Args:
            interface_path: Dot-separated path to the interface relative to SapModel.
                            Leave empty string to call methods directly on SapModel.
            method_name: Name of the method to call.
            arguments: List of arguments to pass to the method. COM 'ref' and 'out'
                       parameters must still be provided (usually as dummy values or empty arrays).

        Returns:
            JSON representation of the COM method's raw return tuple.
            Typically the first element is the return code (0 = success).
        """
        try:
            conn = get_connection()
            conn.ensure_connected()

            # Resolve the COM object
            if interface_path:
                obj = conn.get_interface(interface_path)
            else:
                obj = conn.sap_model

            # Ensure method exists
            method = getattr(obj, method_name, None)
            if method is None:
                return error_response(
                    f"Method '{method_name}' not found on interface '{interface_path or 'SapModel'}'.",
                    suggestion=f"Available methods include: {[m for m in dir(obj) if not m.startswith('_')][:20]}...",
                )

            args = arguments or []
            
            # COM call via comtypes. Return values for out/ref parameters are automatically
            # returned as a tuple along with the method's return value.
            ret = method(*args)
            
            # Clean up COM SAFEARRAYS for JSON serialization
            clean_ret = to_python_list(ret)

            return success_response(
                {"raw_return": clean_ret},
                message=f"Called {interface_path}.{method_name} successfully.",
            )
        except Exception as exc:
            return error_response(str(exc))
