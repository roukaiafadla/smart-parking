from __future__ import annotations

import runpy
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent / "european-license-plate-recognition"
sys.path.insert(0, str(PROJECT_DIR))

runpy.run_path(str(PROJECT_DIR / "rpi_entry_system.py"), run_name="__main__")
