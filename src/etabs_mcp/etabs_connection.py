"""
ETABS COM Connection Manager.

Manages the lifecycle of a connection to a running ETABS instance via COM.
Uses comtypes to interface with the ETABSv1 COM API.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ETABSConnection:
    """Singleton-style manager for the ETABS COM connection.

    Attributes:
        etabs_object: The cOAPI COM object (top-level ETABS application handle).
        sap_model: The cSapModel COM object (main modeling interface).
        program_path: Optional path to the ETABS executable for launching.
        attached: Whether we are currently connected to ETABS.
    """

    etabs_object: Any = field(default=None, repr=False)
    sap_model: Any = field(default=None, repr=False)
    program_path: Optional[str] = None
    attached: bool = False

    # ------------------------------------------------------------------ #
    #  Connection helpers
    # ------------------------------------------------------------------ #

    def connect(
        self,
        *,
        attach_to_existing: bool = True,
        program_path: Optional[str] = None,
    ) -> None:
        """Connect to ETABS — either attach to a running instance or launch a new one.

        Args:
            attach_to_existing: If True, try to attach to a running ETABS first.
            program_path: Full path to ETABS.exe. Only needed when launching.

        Raises:
            ConnectionError: If ETABS cannot be reached.
        """
        if self.attached and self.etabs_object is not None:
            logger.info("Already connected to ETABS.")
            return

        try:
            import comtypes.client  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "The 'comtypes' package is required. Install it with: pip install comtypes"
            ) from exc

        if program_path:
            self.program_path = program_path

        # Strategy 1: Attach to a running instance --------------------------------
        if attach_to_existing:
            try:
                self.etabs_object = comtypes.client.GetActiveObject(
                    "CSI.ETABS.API.ETABSObject"
                )
                self.sap_model = self.etabs_object.SapModel
                self.attached = True
                logger.info("Attached to running ETABS instance.")
                return
            except OSError:
                logger.info("No running ETABS instance found; will try to launch.")

        # Strategy 2: Launch a new instance via the Helper COM object ---------------
        resolved_path = self._resolve_program_path()
        if not resolved_path:
            raise ConnectionError(
                "Cannot launch ETABS: no program path provided and ETABS is not "
                "already running.  Either start ETABS manually or set "
                "'program_path' in the configuration."
            )

        try:
            helper = comtypes.client.CreateObject("CSI.ETABS.API.Helper")
            self.etabs_object = helper.CreateObjectProgID(
                "CSI.ETABS.API.ETABSObject"
            )
        except Exception:
            # Fallback: try CreateObject directly
            try:
                self.etabs_object = comtypes.client.CreateObject(
                    "CSI.ETABS.API.ETABSObject"
                )
            except OSError as exc:
                raise ConnectionError(
                    f"Failed to create ETABS COM object. Is ETABS installed? Error: {exc}"
                ) from exc

        ret = self.etabs_object.ApplicationStart()
        if ret != 0:
            raise ConnectionError(
                f"ETABS ApplicationStart() returned error code {ret}."
            )

        self.sap_model = self.etabs_object.SapModel
        self.attached = True
        logger.info("Launched and connected to a new ETABS instance.")

    def disconnect(self, *, save: bool = False) -> None:
        """Disconnect from ETABS.

        Args:
            save: If True, save the model before closing.
        """
        if not self.attached:
            return

        try:
            if self.etabs_object is not None:
                self.etabs_object.ApplicationExit(save)
        except Exception as exc:
            logger.warning("Error during ETABS disconnect: %s", exc)
        finally:
            self.etabs_object = None
            self.sap_model = None
            self.attached = False
            logger.info("Disconnected from ETABS.")

    def ensure_connected(self) -> None:
        """Raise if not connected to ETABS."""
        if not self.attached or self.sap_model is None:
            raise ConnectionError(
                "Not connected to ETABS. Call connect() first or start ETABS."
            )

    # ------------------------------------------------------------------ #
    #  Convenience accessors for sub-interfaces
    # ------------------------------------------------------------------ #

    def get_interface(self, path: str) -> Any:
        """Navigate the SapModel object hierarchy using a dot-separated path.

        Examples:
            get_interface("Analyze")           → SapModel.Analyze
            get_interface("AreaObj")            → SapModel.AreaObj
            get_interface("DesignSteel")        → SapModel.DesignSteel
            get_interface("Results.Setup")      → SapModel.Results.Setup

        Args:
            path: Dot-separated interface path relative to SapModel.

        Returns:
            The resolved COM interface object.

        Raises:
            AttributeError: If the path does not exist on the model.
        """
        self.ensure_connected()
        obj = self.sap_model
        for part in path.split("."):
            obj = getattr(obj, part)
        return obj

    # ------------------------------------------------------------------ #
    #  Status
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict[str, Any]:
        """Return current connection status and basic model info."""
        info: dict[str, Any] = {
            "connected": self.attached,
            "program_path": self.program_path,
        }
        if self.attached and self.sap_model is not None:
            try:
                file_name = self.sap_model.GetModelFilename()
                info["model_file"] = file_name if file_name else "(unsaved)"
                info["model_is_locked"] = bool(self.sap_model.GetModelIsLocked())
            except Exception:
                info["model_file"] = "(unable to query)"
        return info

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _resolve_program_path(self) -> Optional[str]:
        """Try to find the ETABS executable."""
        if self.program_path and os.path.isfile(self.program_path):
            return self.program_path

        # Common install locations
        candidates = [
            r"C:\Program Files\Computers and Structures\ETABS 22\ETABS.exe",
            r"C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe",
            r"C:\Program Files\Computers and Structures\ETABS 20\ETABS.exe",
            r"C:\Program Files\Computers and Structures\ETABS 19\ETABS.exe",
        ]
        for path in candidates:
            if os.path.isfile(path):
                self.program_path = path
                return path

        return None


# Module-level singleton
_connection = ETABSConnection()


def get_connection() -> ETABSConnection:
    """Return the module-level ETABS connection singleton."""
    return _connection
