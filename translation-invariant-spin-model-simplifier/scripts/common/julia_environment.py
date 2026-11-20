"""Shared Julia environment probe for environment-gated backends.

The probe never launches Julia; it resolves the command the drivers would use
and reports whether a runnable interpreter appears to exist. Callers must fail
closed (``backend-not-connected``) when the probe reports unavailability, and
must not silently fall back to a different backend.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_JULIA_WRAPPER = Path(__file__).resolve().parents[1] / "run_project_julia.sh"
WRAPPER_DEFAULT_JULIA_BIN = "/data/work/zhli/soft/julia-1.12.6/bin/julia"


def _command_looks_runnable(command):
    if not command:
        return False
    first = str(command).split()[0]
    if os.sep in first:
        return os.access(first, os.X_OK)
    return shutil.which(first) is not None


def probe_julia_environment():
    """Return {"command", "available", "source", "detail"} for the Julia route.

    Resolution priority matches the driver contract: explicit
    ``SPINFORGE_JULIA_CMD`` override, then the project wrapper (only when its
    interpreter actually exists), then ``julia`` from PATH. ``command`` is the
    command the driver should invoke even when ``available`` is False, so the
    backend fails through its explicit missing-julia error path.
    """
    override = os.environ.get("SPINFORGE_JULIA_CMD") or os.environ.get("DESIGN_MOTT_JULIA_CMD")
    if override:
        return {"command": override, "available": _command_looks_runnable(override),
                "source": "SPINFORGE_JULIA_CMD",
                "detail": "explicit override"}
    wrapper_bin = (os.environ.get("SPINFORGE_JULIA_BIN")
                   or os.environ.get("DESIGN_MOTT_JULIA_BIN", WRAPPER_DEFAULT_JULIA_BIN))
    if PROJECT_JULIA_WRAPPER.is_file():
        if os.access(wrapper_bin, os.X_OK):
            return {"command": str(PROJECT_JULIA_WRAPPER), "available": True,
                    "source": "project-wrapper",
                    "detail": "wrapper with interpreter at " + wrapper_bin}
        if shutil.which("julia"):
            return {"command": "julia", "available": True, "source": "PATH",
                    "detail": ("wrapper interpreter missing at %s; using PATH julia"
                               % wrapper_bin)}
        return {"command": str(PROJECT_JULIA_WRAPPER), "available": False,
                "source": "project-wrapper",
                "detail": "wrapper interpreter missing at %s and no julia on PATH" % wrapper_bin}
    if shutil.which("julia"):
        return {"command": "julia", "available": True, "source": "PATH",
                "detail": "julia found on PATH"}
    return {"command": "julia", "available": False, "source": None,
            "detail": "no project wrapper and no julia on PATH"}
