"""
Stories & Grids tools — defining building stories and grid systems.

Tools:
  - etabs_get_stories
  - etabs_set_stories
  - etabs_get_grid_systems
  - etabs_set_grid_system
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register stories/grids tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_stories() -> str:
        """Get all story definitions in the model.

        Returns:
            JSON array of stories with name, elevation, height, is_master, and similar_to.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.Story.GetStories_2(
                0, [], [], [], [], [], [], [], 0, ""
            )
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response("Failed to get stories.")

            num = ret[1]
            story_names = to_python_list(ret[2])
            elevations = to_python_list(ret[3])
            heights = to_python_list(ret[4])
            is_master = to_python_list(ret[5])
            similar_to = to_python_list(ret[6])
            splice = to_python_list(ret[7])
            splice_height = to_python_list(ret[8])

            stories = []
            for i in range(num):
                stories.append({
                    "name": story_names[i] if i < len(story_names) else "",
                    "elevation": elevations[i] if i < len(elevations) else 0,
                    "height": heights[i] if i < len(heights) else 0,
                    "is_master": bool(is_master[i]) if i < len(is_master) else True,
                    "similar_to": similar_to[i] if i < len(similar_to) else "",
                })

            return success_response(stories, message=f"Found {num} stories.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_set_stories(
        story_names: list[str],
        story_heights: list[float],
        bottom_elevation: float = 0.0,
    ) -> str:
        """Define the building stories. Stories are listed from bottom to top.

        Args:
            story_names: List of story names, bottom to top (e.g. ["Base", "Story1", "Story2"]).
            story_heights: List of story heights for each story (same length).
            bottom_elevation: Elevation of the base (default 0.0).

        Returns:
            Confirmation with the story definitions.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            n = len(story_names)
            if len(story_heights) != n:
                return error_response("story_names and story_heights must have the same length.")

            is_master = [True] * n
            similar_to = [""] * n
            splice = [False] * n
            splice_height = [0.0] * n

            ret = sm.Story.SetStories_2(
                n, story_names, story_heights,
                is_master, similar_to, splice, splice_height,
                bottom_elevation, "",
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "Story.SetStories_2")
            else:
                check_ret(ret, "Story.SetStories_2")

            return success_response(
                {"stories": [{"name": story_names[i], "height": story_heights[i]} for i in range(n)]},
                message=f"Defined {n} stories.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_grid_systems() -> str:
        """Get all grid system names defined in the model.

        Returns:
            JSON array of grid system names.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.GridSys.GetNameList(0, [])
            if isinstance(ret, tuple) and ret[0] == 0:
                names = to_python_list(ret[2]) if len(ret) > 2 else []
                return success_response(names, message=f"Found {len(names)} grid system(s).")
            return success_response([], message="No grid systems found.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_set_grid_system(
        name: str,
        x_spacings: list[float],
        y_spacings: list[float],
        x_grid_ids: list[str] | None = None,
        y_grid_ids: list[str] | None = None,
    ) -> str:
        """Define or modify a Cartesian grid system.

        Args:
            name: Name of the grid system.
            x_spacings: List of X-direction grid spacings (e.g. [6.0, 6.0, 6.0] for 3 bays).
            y_spacings: List of Y-direction grid spacings.
            x_grid_ids: Optional grid line IDs for X (default: A, B, C, ...).
            y_grid_ids: Optional grid line IDs for Y (default: 1, 2, 3, ...).

        Returns:
            Confirmation with the grid system definition.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            nx = len(x_spacings) + 1
            ny = len(y_spacings) + 1

            if x_grid_ids is None:
                x_grid_ids = [chr(65 + i) for i in range(nx)]
            if y_grid_ids is None:
                y_grid_ids = [str(i + 1) for i in range(ny)]

            # Build cumulative ordinates
            x_ords = [0.0]
            for s in x_spacings:
                x_ords.append(x_ords[-1] + s)
            y_ords = [0.0]
            for s in y_spacings:
                y_ords.append(y_ords[-1] + s)

            ret = sm.GridSys.SetGridSys(
                name, nx, ny,
                x_ords, y_ords,
                x_grid_ids, y_grid_ids,
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "GridSys.SetGridSys")
            else:
                check_ret(ret, "GridSys.SetGridSys")

            return success_response(
                {"name": name, "x_lines": nx, "y_lines": ny},
                message=f"Grid system '{name}' defined with {nx}x{ny} lines.",
            )
        except Exception as exc:
            return error_response(str(exc))
