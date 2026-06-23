"""ETABS MCP tool registrars.

Each submodule exposes a ``register(mcp)`` function that wires a group of
related tools onto a FastMCP server instance.
"""

from __future__ import annotations

__all__ = [
    "analysis",
    "assignments",
    "database_tables",
    "design",
    "generic_api",
    "loads",
    "model_control",
    "model_geometry",
    "properties",
    "results",
    "seismic",
    "selection",
    "stiffness_modifiers",
    "stories_grids",
]
