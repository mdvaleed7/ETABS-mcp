"""
Loads tools — defining and assigning loads.

Tools:
  - etabs_define_load_pattern
  - etabs_get_load_patterns
  - etabs_define_load_case
  - etabs_define_load_combo
  - etabs_assign_point_load
  - etabs_assign_frame_load
  - etabs_assign_area_load
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import ITEM_TYPE, LOAD_PATTERN_TYPES, check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register load-related tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_define_load_pattern(
        name: str,
        load_type: str = "Dead",
        self_weight_multiplier: float = 0.0,
    ) -> str:
        """Define a new load pattern (e.g. Dead, Live, Wind, Quake).

        Args:
            name: Name of the load pattern.
            load_type: Type of load (Dead, Live, Wind, Quake, Snow, etc.).
            self_weight_multiplier: Self-weight multiplier (typically 1.0 for Dead, 0.0 for others).

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            t = LOAD_PATTERN_TYPES.get(load_type, 8)  # 8 is Other
            ret = sm.LoadPatterns.Add(name, t, self_weight_multiplier, True)
            if isinstance(ret, tuple):
                check_ret(ret[0], "LoadPatterns.Add")
            else:
                check_ret(ret, "LoadPatterns.Add")

            return success_response(
                {"name": name, "type": load_type, "self_weight": self_weight_multiplier},
                message=f"Load pattern '{name}' defined.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_load_patterns() -> str:
        """Get all defined load patterns in the model.

        Returns:
            JSON array of load pattern names.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.LoadPatterns.GetNameList(0, [])
            if isinstance(ret, tuple) and ret[0] == 0:
                names = to_python_list(ret[2]) if len(ret) > 2 else []
                return success_response(names, message=f"Found {len(names)} load pattern(s).")
            return success_response([], message="No load patterns found.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_define_load_case(
        name: str,
        case_type: str = "LinearStatic",
        modal_case: str = "MODAL",
    ) -> str:
        """Define a new load case.

        Args:
            name:       Name of the load case.
            case_type:  One of:
                          "LinearStatic"      — standard gravity/wind/static case
                          "Modal"             — Eigenvector modal case (use
                                               etabs_define_modal_case for full control)
                          "ResponseSpectrum"  — RSA case (use etabs_define_response_spectrum
                                               for full IS 1893 / ASCE 7 setup)
                          "LinearHistory"     — linear time history
                          "NonlinearStatic"   — pushover / nonlinear static
            modal_case: For ResponseSpectrum cases only — name of the modal case
                        to source mode shapes from (default "MODAL").

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            if case_type == "LinearStatic":
                ret = sm.LoadCases.StaticLinear.SetCase(name)
                if isinstance(ret, tuple):
                    check_ret(ret[0], "LoadCases.StaticLinear.SetCase")
                else:
                    check_ret(ret, "LoadCases.StaticLinear.SetCase")
                return success_response({"name": name, "type": case_type},
                                        message=f"Linear static case '{name}' defined.")

            elif case_type == "Modal":
                ret = sm.LoadCases.ModalEigen.SetCase(name)
                if isinstance(ret, tuple):
                    check_ret(ret[0], "LoadCases.ModalEigen.SetCase")
                else:
                    check_ret(ret, "LoadCases.ModalEigen.SetCase")
                return success_response(
                    {"name": name, "type": case_type},
                    message=f"Modal (Eigenvector) case '{name}' defined. "
                            "Use etabs_define_modal_case for max/min modes control.",
                )

            elif case_type == "ResponseSpectrum":
                ret = sm.LoadCases.ResponseSpectrum.SetCase(name)
                if isinstance(ret, tuple):
                    check_ret(ret[0], "LoadCases.ResponseSpectrum.SetCase")
                else:
                    check_ret(ret, "LoadCases.ResponseSpectrum.SetCase")
                ret2 = sm.LoadCases.ResponseSpectrum.SetModalCase(name, modal_case)
                if isinstance(ret2, tuple):
                    check_ret(ret2[0], "LoadCases.ResponseSpectrum.SetModalCase")
                return success_response(
                    {"name": name, "type": case_type, "modal_case": modal_case},
                    message=f"Response spectrum case '{name}' created (modal case: '{modal_case}'). "
                            "Use etabs_define_response_spectrum for IS 1893 / ASCE 7 full setup.",
                )

            elif case_type == "NonlinearStatic":
                ret = sm.LoadCases.StaticNonlinear.SetCase(name)
                if isinstance(ret, tuple):
                    check_ret(ret[0], "LoadCases.StaticNonlinear.SetCase")
                else:
                    check_ret(ret, "LoadCases.StaticNonlinear.SetCase")
                return success_response({"name": name, "type": case_type},
                                        message=f"Nonlinear static (pushover) case '{name}' defined.")

            else:
                return error_response(
                    f"Unsupported case type '{case_type}'.",
                    suggestion="Valid types: LinearStatic, Modal, ResponseSpectrum, NonlinearStatic. "
                               "For Modal/RSA use etabs_define_modal_case / etabs_define_response_spectrum "
                               "for full parameter control.",
                )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_define_load_combo(
        name: str,
        combo_type: int = 0,
        load_names: list[str] = [],
        scale_factors: list[float] = [],
    ) -> str:
        """Define a new load combination.

        Args:
            name: Name of the load combination.
            combo_type: 0=LinearAdd, 1=Envelope, 2=AbsoluteAdd, 3=SRSS, 4=RangeAdd.
            load_names: List of load case or pattern names to include.
            scale_factors: List of scale factors corresponding to load_names.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            if len(load_names) != len(scale_factors):
                return error_response("load_names and scale_factors must have the same length.")

            ret = sm.RespCombo.Add(name, combo_type)
            if isinstance(ret, tuple):
                check_ret(ret[0], "RespCombo.Add")
            else:
                check_ret(ret, "RespCombo.Add")

            for idx, load_name in enumerate(load_names):
                # Using eCNameType.LoadCase (1) or LoadPattern (0). Assuming LoadCase (1) by default or let ETABS resolve.
                # In many ETABS versions, SetCaseList requires (ComboName, CType, CName, ScaleFactor)
                # CType: 0=Load case, 1=Load combo
                ret2 = sm.RespCombo.SetCaseList(name, 0, load_name, scale_factors[idx])
                
            return success_response(
                {"name": name, "items": len(load_names)},
                message=f"Load combo '{name}' defined.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_point_load(
        name: str,
        load_pattern: str,
        f1: float = 0.0,
        f2: float = 0.0,
        f3: float = 0.0,
        m1: float = 0.0,
        m2: float = 0.0,
        m3: float = 0.0,
        replace: bool = True,
        item_type: str = "Object",
    ) -> str:
        """Assign point loads/moments to a joint object.

        Args:
            name: Point object name.
            load_pattern: Name of the load pattern.
            f1, f2, f3: Forces in 1, 2, 3 (X, Y, Z) directions.
            m1, m2, m3: Moments about 1, 2, 3 axes.
            replace: If True, replace existing loads; if False, add to them.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            val = [f1, f2, f3, m1, m2, m3]

            ret = sm.PointObj.SetLoadForce(name, load_pattern, val, replace, "Global", it)
            if isinstance(ret, tuple):
                check_ret(ret[0], "PointObj.SetLoadForce")
            else:
                check_ret(ret, "PointObj.SetLoadForce")

            return success_response(
                {"name": name, "pattern": load_pattern, "values": val},
                message=f"Point load assigned to '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_frame_load(
        name: str,
        load_pattern: str,
        w1: float,
        w2: float,
        dir: int = 10,
        dist_1: float = 0.0,
        dist_2: float = 1.0,
        rel_dist: bool = True,
        replace: bool = True,
        item_type: str = "Object",
    ) -> str:
        """Assign a uniform or trapezoidal distributed load to a frame object.

        For uniform load, set w1 = w2, dist_1 = 0.0, dist_2 = 1.0.

        Args:
            name: Frame object name.
            load_pattern: Name of the load pattern.
            w1: Start load value.
            w2: End load value.
            dir: Load direction. 1=Local1, 2=Local2, 3=Local3, 4=X, 5=Y, 6=Z, 10=Gravity.
            dist_1: Distance to start of load.
            dist_2: Distance to end of load.
            rel_dist: If True, distances are relative (0 to 1). If False, absolute.
            replace: If True, replace existing loads.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            # 1 = Force, 2 = Moment. We assume Force (1) for this tool.
            # ETABS API SetLoadDistributed args:
            # Name, LoadPat, MyType(1=Force,2=Moment), Dir, Dist1, Dist2, Val1, Val2, CSys, RelDist, Replace, ItemType
            ret = sm.FrameObj.SetLoadDistributed(
                name, load_pattern, 1, dir, dist_1, dist_2, w1, w2, "Global", rel_dist, replace, it
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "FrameObj.SetLoadDistributed")
            else:
                check_ret(ret, "FrameObj.SetLoadDistributed")

            return success_response(
                {"name": name, "pattern": load_pattern, "w1": w1, "w2": w2},
                message=f"Distributed load assigned to frame '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_assign_area_load(
        name: str,
        load_pattern: str,
        value: float,
        dir: int = 10,
        replace: bool = True,
        item_type: str = "Object",
    ) -> str:
        """Assign a uniform surface load to an area object.

        Args:
            name: Area object name.
            load_pattern: Name of the load pattern.
            value: Load value (force per area).
            dir: Load direction. 1=Local1, 2=Local2, 3=Local3, 4=X, 5=Y, 6=Z, 10=Gravity.
            replace: If True, replace existing loads.
            item_type: "Object", "Group", or "SelectedObjects".

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            it = ITEM_TYPE.get(item_type, 0)
            ret = sm.AreaObj.SetLoadUniform(
                name, load_pattern, value, dir, replace, "Global", it
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "AreaObj.SetLoadUniform")
            else:
                check_ret(ret, "AreaObj.SetLoadUniform")

            return success_response(
                {"name": name, "pattern": load_pattern, "value": value},
                message=f"Uniform load {value} assigned to area '{name}'.",
            )
        except Exception as exc:
            return error_response(str(exc))
