"""
Main ETABS MCP Server entry point.

Uses FastMCP to expose ETABS API tools.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection

# Import tool registrars
from etabs_mcp.tools import (
    analysis,
    assignments,
    database_tables,
    design,
    generic_api,
    loads,
    model_control,
    model_geometry,
    properties,
    results,
    seismic,
    selection,
    stiffness_modifiers,
    stories_grids,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Lifespan manager for the FastMCP server.
    
    Tries to connect to an existing ETABS instance on startup.
    Cleans up the connection on shutdown.
    """
    logger.info("Starting ETABS MCP server...")
    conn = get_connection()
    try:
        # Try to attach to a running instance. We don't launch a new one automatically
        # to avoid unexpected ETABS windows popping up during server boot.
        conn.connect(attach_to_existing=True)
    except Exception as exc:
        logger.warning("Could not auto-connect to ETABS on startup: %s. "
                       "Use etabs_get_status or etabs_new_model to connect later.", exc)

    yield {}

    logger.info("Shutting down ETABS MCP server...")
    if conn.attached:
        # We don't save or close ETABS on shutdown because the user might still
        # be working in the UI. We just disconnect the COM references.
        conn.disconnect(save=False)


# Initialize the FastMCP server.
#
# NOTE: `version=` is not a FastMCP kwarg in mcp>=1.x; the package version is
#       declared in pyproject.toml and exposed via etabs_mcp.__version__.
#       `dependencies=` is honored by FastMCP and tells clients which extra
#       Python packages the server needs at runtime.
mcp = FastMCP(
    name="etabs-mcp",
    instructions=(
        "MCP server for CSI ETABS. Use etabs_get_status first to verify "
        "ETABS is running. The etabs_call_api tool is an escape hatch for "
        "any of the 1,300+ ETABS API methods not covered by the named tools."
    ),
    dependencies=["comtypes>=1.4.0"],
    lifespan=server_lifespan,
)

# Register all tool modules
model_control.register(mcp)
model_geometry.register(mcp)
stories_grids.register(mcp)
properties.register(mcp)
assignments.register(mcp)
stiffness_modifiers.register(mcp)
loads.register(mcp)
analysis.register(mcp)
results.register(mcp)
seismic.register(mcp)       # IS 1893 / ASCE 7 / EC8 modal + RSA + drift
design.register(mcp)
database_tables.register(mcp)
selection.register(mcp)
generic_api.register(mcp)


def main() -> None:
    """Entry point for the command-line script."""
    # FastMCP uses standard stdio by default when called via mcp.run()
    mcp.run()


if __name__ == "__main__":
    main()
