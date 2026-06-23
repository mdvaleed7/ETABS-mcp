"""
Model Control tools — application and model lifecycle management.

Tools:
  - etabs_get_status
  - etabs_new_model
  - etabs_open_model
  - etabs_save_model
  - etabs_close_model
  - etabs_set_units
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import (
    UNITS,
    UNITS_REVERSE,
    check_ret,
    error_response,
    success_response,
)


def register(mcp: FastMCP) -> None:
    """Register model-control tools on the MCP server."""

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_get_status() -> str:
        """Get the current ETABS connection status, model filename, and lock state.

        Returns JSON with: connected (bool), model_file (str), model_is_locked (bool).
        Use this tool first to verify ETABS is running before calling other tools.
        """
        try:
            conn = get_connection()
            if not conn.attached:
                conn.connect(attach_to_existing=True)
            status = conn.get_status()
            return success_response(status)
        except Exception as exc:
            return error_response(
                str(exc),
                suggestion="Make sure ETABS is running on this machine.",
            )

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def etabs_new_model(
        units: str = "kip_ft_F",
        template: str = "blank",
        num_stories: int = 1,
        typical_story_height: float = 12.0,
        bottom_story_height: float = 12.0,
        num_bays_x: int = 1,
        num_bays_y: int = 1,
        bay_width_x: float = 24.0,
        bay_width_y: float = 24.0,
    ) -> str:
        """Create a new ETABS model, optionally from a template.

        Args:
            units: Unit system. One of: lb_in_F, lb_ft_F, kip_in_F, kip_ft_F,
                   kN_mm_C, kN_m_C, kgf_mm_C, kgf_m_C, N_mm_C, N_m_C,
                   Ton_mm_C, Ton_m_C, kN_cm_C, kgf_cm_C, N_cm_C, Ton_cm_C.
            template: Template type — "blank", "steel_deck", or "grid_only".
            num_stories: Number of stories (for templates).
            typical_story_height: Typical story height in current units.
            bottom_story_height: Bottom story height in current units.
            num_bays_x: Number of bays in X direction (for templates).
            num_bays_y: Number of bays in Y direction (for templates).
            bay_width_x: Bay width in X direction in current units.
            bay_width_y: Bay width in Y direction in current units.

        Returns:
            Success confirmation with model info.
        """
        try:
            conn = get_connection()
            if not conn.attached:
                conn.connect()

            sm = conn.sap_model
            unit_val = UNITS.get(units, 4)  # default kip_ft_F

            ret = sm.InitializeNewModel(unit_val)
            check_ret(ret, "InitializeNewModel")

            if template == "steel_deck":
                ret = sm.File.NewSteelDeck(
                    num_stories, typical_story_height, bottom_story_height,
                    num_bays_x, num_bays_y, bay_width_x, bay_width_y,
                )
                check_ret(ret, "File.NewSteelDeck")
            elif template == "grid_only":
                ret = sm.File.NewGridOnly(
                    num_stories, typical_story_height, bottom_story_height,
                    num_bays_x, num_bays_y, bay_width_x, bay_width_y,
                )
                check_ret(ret, "File.NewGridOnly")
            else:
                ret = sm.File.NewBlank()
                check_ret(ret, "File.NewBlank")

            return success_response(
                {"template": template, "units": units},
                message=f"New {template} model created with units {units}.",
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
    def etabs_open_model(file_path: str) -> str:
        """Open an existing ETABS model (.edb) file.

        Args:
            file_path: Full path to the .edb model file (e.g. "C:/Models/Building.edb").

        Returns:
            Success confirmation.
        """
        try:
            conn = get_connection()
            if not conn.attached:
                conn.connect()

            ret = conn.sap_model.File.OpenFile(file_path)
            check_ret(ret, "File.OpenFile", detail=f"path={file_path}")
            return success_response(
                {"file_path": file_path},
                message=f"Opened model: {file_path}",
            )
        except Exception as exc:
            return error_response(
                str(exc),
                suggestion="Check that the file path exists and is a valid .edb file.",
            )

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_save_model(file_path: str = "") -> str:
        """Save the current ETABS model.

        Args:
            file_path: Full path to save as (e.g. "C:/Models/Building.edb").
                       Leave empty to save to the current file.

        Returns:
            Success confirmation with saved path.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()

            if file_path:
                ret = conn.sap_model.File.Save(file_path)
                check_ret(ret, "File.Save", detail=f"path={file_path}")
            else:
                ret = conn.sap_model.File.Save()
                check_ret(ret, "File.Save")

            saved_path = conn.sap_model.GetModelFilename()
            return success_response(
                {"saved_to": saved_path},
                message=f"Model saved to: {saved_path}",
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
    def etabs_close_model(save_first: bool = False) -> str:
        """Close the current ETABS model without exiting the application.

        Args:
            save_first: If True, save the model before closing.

        Returns:
            Success confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()

            if save_first:
                conn.sap_model.File.Save()

            ret = conn.sap_model.InitializeNewModel()
            check_ret(ret, "InitializeNewModel")
            ret = conn.sap_model.File.NewBlank()
            check_ret(ret, "File.NewBlank")

            return success_response(message="Model closed. Blank model active.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def etabs_set_units(units: str) -> str:
        """Set the active display units for the ETABS model.

        Args:
            units: Unit system. One of: lb_in_F, lb_ft_F, kip_in_F, kip_ft_F,
                   kN_mm_C, kN_m_C, kgf_mm_C, kgf_m_C, N_mm_C, N_m_C,
                   Ton_mm_C, Ton_m_C, kN_cm_C, kgf_cm_C, N_cm_C, Ton_cm_C.

        Returns:
            Confirmation of the unit change.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()

            unit_val = UNITS.get(units)
            if unit_val is None:
                return error_response(
                    f"Unknown unit system '{units}'.",
                    suggestion=f"Valid units: {', '.join(UNITS.keys())}",
                )

            ret = conn.sap_model.SetPresentUnits(unit_val)
            check_ret(ret, "SetPresentUnits")
            return success_response(
                {"units": units},
                message=f"Display units set to {units}.",
            )
        except Exception as exc:
            return error_response(str(exc))
