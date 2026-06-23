"""
Selection tools — object selection and grouping.

Tools:
  - etabs_select_objects
  - etabs_get_selected
  - etabs_define_group
  - etabs_add_to_group
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register selection tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_select_objects(
        name: str,
        object_type: str = "Frame",
        clear_previous: bool = False,
    ) -> str:
        """Select objects by name in the ETABS UI.

        Args:
            name: Name of the object to select.
            object_type: "Point", "Frame", "Area", or "Link".
            clear_previous: If True, clears existing selection before selecting.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            if clear_previous:
                sm.Select.ClearSelection()

            type_map = {
                "point": sm.PointObj,
                "frame": sm.FrameObj,
                "area": sm.AreaObj,
                "link": sm.LinkObj,
            }
            obj_interface = type_map.get(object_type.lower())
            if obj_interface is None:
                return error_response(f"Unknown object type '{object_type}'.")

            ret = obj_interface.SetSelected(name, True)
            if isinstance(ret, tuple):
                check_ret(ret[0], f"{object_type}.SetSelected")
            else:
                check_ret(ret, f"{object_type}.SetSelected")

            return success_response({"name": name}, message=f"Selected {object_type} '{name}'.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_selected() -> str:
        """Get a list of currently selected objects.

        Returns:
            JSON array of selected object names and types.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.Select.GetSelected(0, [], [])
            if not isinstance(ret, tuple) or ret[0] != 0:
                return success_response([], message="No objects selected.")

            num = ret[1]
            obj_types_int = to_python_list(ret[2])
            obj_names = to_python_list(ret[3])
            
            type_map = {1: "Point", 2: "Frame", 3: "Cable", 4: "Tendon", 5: "Area", 6: "Solid", 7: "Link"}
            
            selected = []
            for i in range(num):
                t_str = type_map.get(obj_types_int[i], "Unknown") if i < len(obj_types_int) else "Unknown"
                name = obj_names[i] if i < len(obj_names) else ""
                selected.append({"type": t_str, "name": name})

            return success_response(selected, message=f"Found {num} selected object(s).")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_define_group(
        group_name: str,
        color: int = -1,
        specified_for_selection: bool = True,
        specified_for_section_cut: bool = True,
        specified_for_steel_design: bool = True,
        specified_for_concrete_design: bool = True,
    ) -> str:
        """Define a new group.

        Args:
            group_name: Name of the group.
            color: Color for the group (-1 for auto).
            specified_for_selection: Whether group is available for selection.
            specified_for_section_cut: Whether group is available for section cuts.
            specified_for_steel_design: Whether group is available for steel design.
            specified_for_concrete_design: Whether group is available for concrete design.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.GroupDef.SetGroup(
                group_name, color, specified_for_selection, specified_for_section_cut,
                specified_for_steel_design, specified_for_concrete_design, True, True, True
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "GroupDef.SetGroup")
            else:
                check_ret(ret, "GroupDef.SetGroup")

            return success_response({"name": group_name}, message=f"Group '{group_name}' defined.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_add_to_group(
        name: str,
        group_name: str,
        object_type: str = "Frame",
        remove: bool = False,
    ) -> str:
        """Add or remove an object from a group.

        Args:
            name: Name of the object.
            group_name: Name of the group.
            object_type: "Point", "Frame", "Area", or "Link".
            remove: If True, removes the object from the group instead of adding.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            type_map = {
                "point": sm.PointObj,
                "frame": sm.FrameObj,
                "area": sm.AreaObj,
                "link": sm.LinkObj,
            }
            obj_interface = type_map.get(object_type.lower())
            if obj_interface is None:
                return error_response(f"Unknown object type '{object_type}'.")

            ret = obj_interface.SetGroupAssign(name, group_name, remove)
            if isinstance(ret, tuple):
                check_ret(ret[0], f"{object_type}.SetGroupAssign")
            else:
                check_ret(ret, f"{object_type}.SetGroupAssign")

            action = "Removed from" if remove else "Added to"
            return success_response(
                {"name": name, "group": group_name},
                message=f"{action} group '{group_name}': {object_type} '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))
