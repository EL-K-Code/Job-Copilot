from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_private_beta_entrypoint_bootstraps_project_root(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    entrypoint = project_root / "app" / "ui" / "private_beta_app.py"
    probe = f"""
import importlib.util

spec = importlib.util.spec_from_file_location(
    "jobcopilot_private_beta_entrypoint",
    {str(entrypoint)!r},
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert callable(module.main)
"""

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
