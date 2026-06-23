"""
Model Geometry tools — creating and querying structural geometry.

Tools:
  - etabs_add_point
  - etabs_add_frame
  - etabs_add_area
  - etabs_get_all_points
  - etabs_get_all_frames
  - etabs_get_all_areas
  - etabs_delete_object
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register model-geometry tools on the MCP server."""

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def etabs_add_point(
        x: float,
        y: float,
        z: float,
        name: str = "",
        csys: str = "Global",
    ) -> str:
        """Add a point (joint) object at the specified coordinates.

        Args:
            x: X coordinate in current units.
            y: Y coordinate in current units.
            z: Z coordinate in current units.
            name: Optional user-defined name. ETABS assigns a default if blank.
            csys: Coordinate system name (default "Global").

        Returns:
            JSON with the assigned point name.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()

            result_name = ""
            ret = conn.sap_model.PointObj.AddCartesian(
                x, y, z, result_name, name, csys
            )
            # The return is (ret_code, name)
            if isinstance(ret, tuple):
                check_ret(ret[0], "PointObj.AddCartesian")
                result_name = ret[1] if len(ret) > 1 else name
            else:
                check_ret(ret, "PointObj.AddCartesian")
                result_name = name

            return success_response(
                {"name": result_name, "x": x, "y": y, "z": z},
                message=f"Point '{result_name}' added at ({x}, {y}, {z}).",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def etabs_add_frame(
        x1: float, y1: float, z1: float,
        x2: float, y2: float, z2: float,
        prop_name: str = "Default",
        name: str = "",
        csys: str = "Global",
    ) -> str:
        """Add a frame object (beam, column, brace) between two points by coordinates.

        Args:
            x1: X coordinate of start point.
            y1: Y coordinate of start point.
            z1: Z coordinate of start point.
            x2: X coordinate of end point.
            y2: Y coordinate of end point.
            z2: Z coordinate of end point.
            prop_name: Frame section property name. Use "Default" for auto-assigned.
            name: Optional user-defined name for the frame.
            csys: Coordinate system name (default "Global").

        Returns:
            JSON with the assigned frame name.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()

            result_name = ""
            ret = conn.sap_model.FrameObj.AddByCoord(
                x1, y1, z1, x2, y2, z2,
                result_name, prop_name, name, csys,
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "FrameObj.AddByCoord")
                result_name = ret[1] if len(ret) > 1 else name
            else:
                check_ret(ret, "FrameObj.AddByCoord")
                result_name = name

            return success_response(
                {
                    "name": result_name,
                    "start": {"x": x1, "y": y1, "z": z1},
                    "end": {"x": x2, "y": y2, "z": z2},
                    "section": prop_name,
                },
                message=f"Frame '{result_name}' added.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def etabs_add_area(
        x_coords: list[float],
        y_coords: list[float],
        z_coords: list[float],
        prop_name: str = "Default",
        name: str = "",
        csys: str = "Global",
    ) -> str:
        """Add an area object (slab, wall, deck) defined by corner coordinates.

        The coordinates should be ordered clockwise or counter-clockwise.
        Must have at least 3 points.

        Args:
            x_coords: List of X coordinates for each corner.
            y_coords: List of Y coordinates for each corner.
            z_coords: List of Z coordinates for each corner.
            prop_name: Area section property name. Use "Default" for auto-assigned.
            name: Optional user-defined name for the area.
            csys: Coordinate system name (default "Global").

        Returns:
            JSON with the assigned area name.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()

            num_points = len(x_coords)
            if num_points < 3:
                return error_response(
                    "At least 3 corner points are required.",
                    suggestion="Provide x_coords, y_coords, z_coords with 3+ values each.",
                )
            if len(y_coords) != num_points or len(z_coords) != num_points:
                return error_response(
                    "x_coords, y_coords, and z_coords must have the same length.",
                )

            result_name = ""
            ret = conn.sap_model.AreaObj.AddByCoord(
                num_points, x_coords, y_coords, z_coords,
                result_name, prop_name, name, csys,
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "AreaObj.AddByCoord")
                result_name = ret[1] if len(ret) > 1 else name
            else:
                check_ret(ret, "AreaObj.AddByCoord")
                result_name = name

            return success_response(
                {"name": result_name, "num_points": num_points, "section": prop_name},
                message=f"Area '{result_name}' added with {num_points} corners.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_get_all_points() -> str:
        """Get a list of all point/joint objects in the model with their coordinates.

        Returns:
            JSON array of points, each with name, x, y, z coordinates.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            num_names = 0
            names = []
            ret = sm.PointObj.GetNameList(num_names, names)
            if isinstance(ret, tuple):
                num_names = ret[1] if len(ret) > 1 else 0
                names = to_python_list(ret[2]) if len(ret) > 2 else []
            else:
                return success_response([], message="No points found.")

            points = []
            for name in names:
                x, y, z = 0.0, 0.0, 0.0
                coord_ret = sm.PointObj.GetCoordCartesian(name, x, y, z)
                if isinstance(coord_ret, tuple) and coord_ret[0] == 0:
                    x, y, z = coord_ret[1], coord_ret[2], coord_ret[3]
                points.append({"name": name, "x": x, "y": y, "z": z})

            return success_response(
                points,
                message=f"Found {len(points)} point(s).",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_get_all_frames() -> str:
        """Get a list of all frame objects in the model with connectivity and section info.

        Returns:
            JSON array of frames, each with name, start point, end point, section name.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            num_names = 0
            names = []
            ret = sm.FrameObj.GetNameList(num_names, names)
            if isinstance(ret, tuple):
                num_names = ret[1] if len(ret) > 1 else 0
                names = to_python_list(ret[2]) if len(ret) > 2 else []
            else:
                return success_response([], message="No frames found.")

            frames = []
            for name in names:
                frame_info = {"name": name}
                try:
                    pts_ret = sm.FrameObj.GetPoints(name, "", "")
                    if isinstance(pts_ret, tuple) and pts_ret[0] == 0:
                        frame_info["point_i"] = pts_ret[1]
                        frame_info["point_j"] = pts_ret[2]
                except Exception:
                    pass

                try:
                    sec_ret = sm.FrameObj.GetSection(name, "", "")
                    if isinstance(sec_ret, tuple) and sec_ret[0] == 0:
                        frame_info["section"] = sec_ret[1]
                except Exception:
                    pass

                frames.append(frame_info)

            return success_response(
                frames,
                message=f"Found {len(frames)} frame(s).",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_get_all_areas() -> str:
        """Get a list of all area objects in the model with connectivity and section info.

        Returns:
            JSON array of areas, each with name, number of points, point names, section.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            num_names = 0
            names = []
            ret = sm.AreaObj.GetNameList(num_names, names)
            if isinstance(ret, tuple):
                num_names = ret[1] if len(ret) > 1 else 0
                names = to_python_list(ret[2]) if len(ret) > 2 else []
            else:
                return success_response([], message="No areas found.")

            areas = []
            for name in names:
                area_info = {"name": name}
                try:
                    pts_ret = sm.AreaObj.GetPoints(name, 0, [])
                    if isinstance(pts_ret, tuple) and pts_ret[0] == 0:
                        area_info["num_points"] = pts_ret[1]
                        area_info["points"] = to_python_list(pts_ret[2])
                except Exception:
                    pass

                try:
                    sec_ret = sm.AreaObj.GetProperty(name, "")
                    if isinstance(sec_ret, tuple) and sec_ret[0] == 0:
                        area_info["section"] = sec_ret[1]
                except Exception:
                    pass

                areas.append(area_info)

            return success_response(
                areas,
                message=f"Found {len(areas)} area(s).",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_delete_object(
        object_type: str,
        name: str,
    ) -> str:
        """Delete a named object from the model.

        Args:
            object_type: Type of object — "point", "frame", "area", or "link".
            name: Name of the object to delete.

        Returns:
            Success confirmation.
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
                return error_response(
                    f"Unknown object type '{object_type}'.",
                    suggestion="Use one of: point, frame, area, link.",
                )

            ret = obj_interface.Delete(name)
            if isinstance(ret, tuple):
                check_ret(ret[0], f"{object_type}.Delete")
            else:
                check_ret(ret, f"{object_type}.Delete")

            return success_response(
                {"type": object_type, "name": name},
                message=f"Deleted {object_type} '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))
