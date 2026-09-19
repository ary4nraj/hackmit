"""GOLDEN PATH: python scripts/demo.py   (add --mock for a no-hardware rehearsal)

connect Nordic -> detect target -> connect Go2 -> stand -> calibrate -> ENTER -> search -> FOUND -> stop.
"""

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import sys

from scripts.homing_auto import main
import asyncio

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
