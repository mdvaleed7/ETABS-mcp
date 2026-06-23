"""
Shared helpers for the ETABS MCP server.

Provides:
  - COM call wrappers with error-code checking
  - Response formatting for MCP tool outputs
  - Array marshaling between Python lists and COM SAFEARRAY
  - Unit constants
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
#  COM call helpers
# ────────────────────────────────────────────────────────────────────

class ETABSError(Exception):
    """Raised when an ETABS API call returns a nonzero error code."""

    def __init__(self, method: str, ret: int, detail: str = ""):
        self.method = method
        self.ret = ret
        msg = f"ETABS API error in {method}(): returned code {ret}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


def check_ret(ret: int, method_name: str, *, detail: str = "") -> int:
    """Check a return value from an ETABS COM call.

    ETABS convention: 0 = success, nonzero = failure.

    Args:
        ret: The integer return code.
        method_name: Name of the method for error messages.
        detail: Optional extra context.

    Returns:
        The return code (always 0 on success).

    Raises:
        ETABSError: If ret != 0.
    """
    if ret != 0:
        raise ETABSError(method_name, ret, detail)
    return ret


# ────────────────────────────────────────────────────────────────────
#  Response formatting
# ────────────────────────────────────────────────────────────────────

def success_response(data: Any = None, message: str = "") -> str:
    """Format a successful tool response as JSON text.

    Args:
        data: The payload to return (dict, list, scalar, etc.).
        message: Optional human-readable message.

    Returns:
        JSON string for the MCP text content.
    """
    payload: dict[str, Any] = {"status": "success"}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    return json.dumps(payload, indent=2, default=str)


def error_response(error: str, suggestion: str = "") -> str:
    """Format an error tool response as JSON text.

    Args:
        error: Description of the error.
        suggestion: Actionable next step for the LLM.

    Returns:
        JSON string for the MCP text content.
    """
    payload: dict[str, Any] = {"status": "error", "error": error}
    if suggestion:
        payload["suggestion"] = suggestion
    return json.dumps(payload, indent=2, default=str)


# ────────────────────────────────────────────────────────────────────
#  Array marshaling
# ────────────────────────────────────────────────────────────────────

def to_python_list(com_array: Any) -> list:
    """Convert a COM SAFEARRAY (or tuple) to a plain Python list.

    Handles nested arrays as well.
    """
    if com_array is None:
        return []
    try:
        return [to_python_list(x) if hasattr(x, "__iter__") and not isinstance(x, str) else x for x in com_array]
    except TypeError:
        return [com_array]


def to_com_array(values: Sequence, element_type: str = "double") -> Any:
    """Build a COM-compatible array from a Python sequence.

    For comtypes, simple Python lists/tuples usually work directly,
    but this helper normalizes them.

    Args:
        values: The Python sequence.
        element_type: 'double', 'int', or 'str'.

    Returns:
        A list cast to the appropriate types.
    """
    type_map = {"double": float, "int": int, "str": str}
    cast_fn = type_map.get(element_type, float)
    return [cast_fn(v) for v in values]


# ────────────────────────────────────────────────────────────────────
#  Unit enumerations
# ────────────────────────────────────────────────────────────────────

# ETABS eUnits enumeration (subset of commonly used values)
UNITS = {
    "lb_in_F":   1,
    "lb_ft_F":   2,
    "kip_in_F":  3,
    "kip_ft_F":  4,
    "kN_mm_C":   5,
    "kN_m_C":    6,
    "kgf_mm_C":  7,
    "kgf_m_C":   8,
    "N_mm_C":    9,
    "N_m_C":    10,
    "Ton_mm_C": 11,
    "Ton_m_C":  12,
    "kN_cm_C":  13,
    "kgf_cm_C": 14,
    "N_cm_C":   15,
    "Ton_cm_C": 16,
}

UNITS_REVERSE = {v: k for k, v in UNITS.items()}


# ────────────────────────────────────────────────────────────────────
#  Load pattern type enumerations
# ────────────────────────────────────────────────────────────────────

LOAD_PATTERN_TYPES = {
    "Dead":            1,
    "SuperDead":       2,
    "Live":            3,
    "ReduceLive":      4,
    "Quake":           5,
    "Wind":            6,
    "Snow":            7,
    "Other":           8,
    "Move":            9,
    "Temperature":    10,
    "RoofLive":       11,
    "Notional":       12,
    "PatternLive":    13,
    "Wave":           14,
    "Braking":        15,
    "Centrifugal":    16,
    "Friction":       17,
    "Ice":            18,
    "WindOnLiveLoad": 19,
    "HorizPress":     20,
    "VertPress":      21,
    "Proof":          22,
    "Rain":           23,
    "Dust":           24,
    "Special":        25,
}


# ────────────────────────────────────────────────────────────────────
#  Item type enumerations
# ────────────────────────────────────────────────────────────────────

ITEM_TYPE = {
    "Object":         0,
    "Group":          1,
    "SelectedObjects": 2,
}


# ────────────────────────────────────────────────────────────────────
#  Safe COM method invocation
# ────────────────────────────────────────────────────────────────────

def safe_call(obj: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    """Call a COM method by name, catching COM errors and wrapping them.

    Args:
        obj: The COM interface object.
        method_name: Name of the method to call.
        *args: Positional arguments.
        **kwargs: Keyword arguments.

    Returns:
        The raw return value from the COM call.

    Raises:
        ETABSError: On COM failure.
    """
    method = getattr(obj, method_name, None)
    if method is None:
        raise AttributeError(
            f"Interface has no method '{method_name}'. "
            f"Available: {[m for m in dir(obj) if not m.startswith('_')]}"
        )
    try:
        result = method(*args, **kwargs)
        return result
    except Exception as exc:
        raise ETABSError(method_name, -1, str(exc)) from exc
