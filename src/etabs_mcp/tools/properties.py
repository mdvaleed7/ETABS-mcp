"""
Properties tools — defining materials and section properties.

Tools:
  - etabs_define_material
  - etabs_get_materials
  - etabs_define_frame_section
  - etabs_get_frame_sections
  - etabs_define_area_section
  - etabs_get_area_sections
  - etabs_define_rebar
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response, to_python_list

# ETABS material types
MATERIAL_TYPES = {
    "Steel": 1,
    "Concrete": 2,
    "NoDesign": 3,
    "Aluminum": 4,
    "ColdFormed": 5,
    "Rebar": 6,
    "Tendon": 7,
    "Masonry": 8,
}

# ETABS frame section shape types
FRAME_SECTION_SHAPES = {
    "I": 1, "Channel": 2, "Tee": 3, "Angle": 4,
    "DblAngle": 5, "Box": 6, "Pipe": 7, "Rectangular": 8,
    "Circular": 9, "General": 10, "DbChannel": 11,
    "Auto": 0, "SteelPlate": 15,
}


def register(mcp: FastMCP) -> None:
    """Register property-definition tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_define_material(
        name: str,
        material_type: str = "Concrete",
        region: str = "United States",
        standard: str = "",
        grade: str = "",
    ) -> str:
        """Define a new material property.

        Args:
            name: Name for the material (e.g. "4000Psi", "A992Fy50").
            material_type: One of: Steel, Concrete, NoDesign, Aluminum,
                           ColdFormed, Rebar, Tendon, Masonry.
            region: Design region (default "United States").
            standard: Standard name (e.g. "ASTM A992" for steel, "ACI 318" for concrete).
            grade: Grade/class (e.g. "Grade 50", "f'c 4000 psi").

        Returns:
            Confirmation of the material definition.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            mat_type = MATERIAL_TYPES.get(material_type, 2)

            ret = sm.PropMaterial.SetMaterial(name, mat_type)
            if isinstance(ret, tuple):
                check_ret(ret[0], "PropMaterial.SetMaterial")
            else:
                check_ret(ret, "PropMaterial.SetMaterial")

            return success_response(
                {"name": name, "type": material_type},
                message=f"Material '{name}' defined as {material_type}.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_materials() -> str:
        """Get a list of all defined materials in the model.

        Returns:
            JSON array of material names and types.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.PropMaterial.GetNameList(0, [])
            if isinstance(ret, tuple) and ret[0] == 0:
                names = to_python_list(ret[2]) if len(ret) > 2 else []
                materials = []
                for mat_name in names:
                    try:
                        type_ret = sm.PropMaterial.GetMaterial(mat_name, 0)
                        if isinstance(type_ret, tuple) and type_ret[0] == 0:
                            mat_type_num = type_ret[1]
                            mat_type_str = next(
                                (k for k, v in MATERIAL_TYPES.items() if v == mat_type_num),
                                "Unknown",
                            )
                        else:
                            mat_type_str = "Unknown"
                    except Exception:
                        mat_type_str = "Unknown"
                    materials.append({"name": mat_name, "type": mat_type_str})
                return success_response(materials, message=f"Found {len(materials)} material(s).")
            return success_response([], message="No materials found.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_define_frame_section(
        name: str,
        material: str,
        shape: str = "Rectangular",
        depth: float = 24.0,
        width: float = 12.0,
        flange_width_top: float = 0.0,
        flange_thickness_top: float = 0.0,
        web_thickness: float = 0.0,
        flange_width_bot: float = 0.0,
        flange_thickness_bot: float = 0.0,
    ) -> str:
        """Define a frame section property (beam/column cross-section).

        For Rectangular and Circular shapes, only depth and width are needed.
        For I, Tee, Channel shapes, provide flange and web dimensions.

        Args:
            name: Section name (e.g. "W14X22", "C24x12", "Beam24x12").
            material: Material name (must be previously defined).
            shape: Section shape — Rectangular, Circular, I, Tee, Channel, Box, Pipe, Angle.
            depth: Total depth (or diameter for circular).
            width: Total width (or diameter for Pipe).
            flange_width_top: Top flange width (for I, Tee, Channel).
            flange_thickness_top: Top flange thickness.
            web_thickness: Web thickness.
            flange_width_bot: Bottom flange width (for I).
            flange_thickness_bot: Bottom flange thickness (for I).

        Returns:
            Confirmation with section details.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            if shape == "Rectangular":
                ret = sm.PropFrame.SetRectangle(name, material, depth, width)
            elif shape == "Circular":
                ret = sm.PropFrame.SetCircle(name, material, depth)
            elif shape == "Pipe":
                ret = sm.PropFrame.SetPipe(name, material, depth, web_thickness)
            elif shape == "Box":
                ret = sm.PropFrame.SetTube(
                    name, material, depth, width,
                    flange_thickness_top, web_thickness,
                )
            elif shape == "I":
                ret = sm.PropFrame.SetISection(
                    name, material, depth,
                    flange_width_top, flange_thickness_top,
                    web_thickness,
                    flange_width_bot, flange_thickness_bot,
                )
            elif shape == "Tee":
                ret = sm.PropFrame.SetTee(
                    name, material, depth,
                    flange_width_top, flange_thickness_top, web_thickness,
                )
            elif shape == "Channel":
                ret = sm.PropFrame.SetChannel(
                    name, material, depth,
                    flange_width_top, flange_thickness_top, web_thickness,
                )
            else:
                return error_response(
                    f"Unsupported shape '{shape}'.",
                    suggestion="Use: Rectangular, Circular, I, Tee, Channel, Box, Pipe.",
                )

            if isinstance(ret, tuple):
                check_ret(ret[0], f"PropFrame.Set{shape}")
            else:
                check_ret(ret, f"PropFrame.Set{shape}")

            return success_response(
                {"name": name, "material": material, "shape": shape, "depth": depth, "width": width},
                message=f"Frame section '{name}' defined as {shape}.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_frame_sections() -> str:
        """Get a list of all defined frame section properties.

        Returns:
            JSON array of section names.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.PropFrame.GetNameList(0, [])
            if isinstance(ret, tuple) and ret[0] == 0:
                names = to_python_list(ret[2]) if len(ret) > 2 else []
                return success_response(names, message=f"Found {len(names)} frame section(s).")
            return success_response([], message="No frame sections found.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_define_area_section(
        name: str,
        material: str,
        section_type: str = "Shell-Thin",
        thickness: float = 8.0,
        shell_type: int = 1,
    ) -> str:
        """Define an area/shell section property (for slabs, walls, decks).

        Args:
            name: Section name (e.g. "Slab8in", "Wall12in").
            material: Material name (must be previously defined).
            section_type: "Shell-Thin", "Shell-Thick", "Membrane", "Plate-Thin", "Plate-Thick".
            thickness: Shell thickness in current units.
            shell_type: 1=Shell-Thin, 2=Shell-Thick, 3=Plate-Thin,
                        4=Plate-Thick, 5=Membrane, 6=Shell-Layered.

        Returns:
            Confirmation with section details.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            type_map = {
                "Shell-Thin": 1, "Shell-Thick": 2, "Plate-Thin": 3,
                "Plate-Thick": 4, "Membrane": 5, "Shell-Layered": 6,
            }
            st = type_map.get(section_type, shell_type)

            ret = sm.PropArea.SetShell_1(
                name, st, False, material, 0.0, thickness, thickness,
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "PropArea.SetShell_1")
            else:
                check_ret(ret, "PropArea.SetShell_1")

            return success_response(
                {"name": name, "material": material, "type": section_type, "thickness": thickness},
                message=f"Area section '{name}' defined as {section_type} ({thickness} thick).",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_area_sections() -> str:
        """Get a list of all defined area/shell section properties.

        Returns:
            JSON array of area section names.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.PropArea.GetNameList(0, [])
            if isinstance(ret, tuple) and ret[0] == 0:
                names = to_python_list(ret[2]) if len(ret) > 2 else []
                return success_response(names, message=f"Found {len(names)} area section(s).")
            return success_response([], message="No area sections found.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_define_rebar(
        name: str,
        area: float,
        diameter: float,
    ) -> str:
        """Define a rebar size.

        Args:
            name: Rebar name (e.g. "#4", "#8", "T10").
            area: Cross-sectional area in current units.
            diameter: Bar diameter in current units.

        Returns:
            Confirmation of the rebar definition.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.PropRebar.SetRebar(name, area, diameter)
            if isinstance(ret, tuple):
                check_ret(ret[0], "PropRebar.SetRebar")
            else:
                check_ret(ret, "PropRebar.SetRebar")

            return success_response(
                {"name": name, "area": area, "diameter": diameter},
                message=f"Rebar '{name}' defined.",
            )
        except Exception as exc:
            return error_response(str(exc))
