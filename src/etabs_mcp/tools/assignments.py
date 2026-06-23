"""
Assignments tools — assigning sections, releases, constraints, labels to objects.

Tools:
  - etabs_assign_frame_section
  - etabs_assign_frame_releases
  - etabs_assign_area_section
  - etabs_assign_diaphragm
  - etabs_assign_pier_label
  - etabs_assign_spandrel_label
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import ITEM_TYPE, check_ret, error_response, success_response


def register(mcp: FastMCP) -> None:
    """Register assignment tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_frame_section(
        name: str,
        section_name: str,
        item_type: str = "Object",
    ) -> str:
        """Assign a frame section property to a frame object.

        Args:
            name: Frame object name, or group name if item_type is "Group".
            section_name: Name of the frame section to assign.
            item_type: "Object" (single object), "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.FrameObj.SetSection(name, section_name, it)
            if isinstance(ret, tuple):
                check_ret(ret[0], "FrameObj.SetSection")
            else:
                check_ret(ret, "FrameObj.SetSection")

            return success_response(
                {"name": name, "section": section_name},
                message=f"Assigned section '{section_name}' to frame '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_frame_releases(
        name: str,
        start_release: list[bool] | None = None,
        end_release: list[bool] | None = None,
        item_type: str = "Object",
    ) -> str:
        """Set end releases (moment releases / pins) for a frame object.

        Each release list has 6 booleans for [P, V2, V3, T, M2, M3]:
          - True = released (free/pin), False = fixed.
        Common patterns:
          - Pin at start: [False, False, False, False, False, True]
          - Pin at both ends: set both start and end M3 to True.

        Args:
            name: Frame object name.
            start_release: 6-element list of bools for I-end (start) releases [P, V2, V3, T, M2, M3].
            end_release: 6-element list of bools for J-end (end) releases.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ii = start_release if start_release else [False] * 6
            jj = end_release if end_release else [False] * 6

            if len(ii) != 6 or len(jj) != 6:
                return error_response("Release lists must have exactly 6 boolean values [P, V2, V3, T, M2, M3].")

            start_values = [0.0] * 6
            end_values = [0.0] * 6
            it = ITEM_TYPE.get(item_type, 0)

            ret = sm.FrameObj.SetReleases(name, ii, jj, start_values, end_values, it)
            if isinstance(ret, tuple):
                check_ret(ret[0], "FrameObj.SetReleases")
            else:
                check_ret(ret, "FrameObj.SetReleases")

            return success_response(
                {"name": name, "start_release": ii, "end_release": jj},
                message=f"End releases set for frame '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_area_section(
        name: str,
        section_name: str,
        item_type: str = "Object",
    ) -> str:
        """Assign an area/shell section property to an area object.

        Args:
            name: Area object name, or group name if item_type is "Group".
            section_name: Name of the area section to assign.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.AreaObj.SetProperty(name, section_name, it)
            if isinstance(ret, tuple):
                check_ret(ret[0], "AreaObj.SetProperty")
            else:
                check_ret(ret, "AreaObj.SetProperty")

            return success_response(
                {"name": name, "section": section_name},
                message=f"Assigned section '{section_name}' to area '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_diaphragm(
        name: str,
        diaphragm_name: str,
        item_type: str = "Object",
    ) -> str:
        """Assign a diaphragm constraint to an area or point object.

        Args:
            name: Object name or group name.
            diaphragm_name: Name of the diaphragm to assign.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.AreaObj.SetDiaphragm(name, diaphragm_name, it)
            if isinstance(ret, tuple):
                check_ret(ret[0], "AreaObj.SetDiaphragm")
            else:
                check_ret(ret, "AreaObj.SetDiaphragm")

            return success_response(
                {"name": name, "diaphragm": diaphragm_name},
                message=f"Diaphragm '{diaphragm_name}' assigned to '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_pier_label(
        name: str,
        pier_name: str,
        item_type: str = "Object",
    ) -> str:
        """Assign a pier label to an area or line object (for wall piers).

        Args:
            name: Object name.
            pier_name: Name of the pier label.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.PierLabel.SetPier(name, pier_name, it)
            if isinstance(ret, tuple):
                check_ret(ret[0], "PierLabel.SetPier")
            else:
                check_ret(ret, "PierLabel.SetPier")

            return success_response(
                {"name": name, "pier": pier_name},
                message=f"Pier label '{pier_name}' assigned to '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_spandrel_label(
        name: str,
        spandrel_name: str,
        item_type: str = "Object",
    ) -> str:
        """Assign a spandrel label to an area or line object (for wall spandrels).

        Args:
            name: Object name.
            spandrel_name: Name of the spandrel label.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.SpandrelLabel.SetSpandrel(name, spandrel_name, it)
            if isinstance(ret, tuple):
                check_ret(ret[0], "SpandrelLabel.SetSpandrel")
            else:
                check_ret(ret, "SpandrelLabel.SetSpandrel")

            return success_response(
                {"name": name, "spandrel": spandrel_name},
                message=f"Spandrel label '{spandrel_name}' assigned to '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))
