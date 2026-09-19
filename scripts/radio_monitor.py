"""Alias for python -m signalhound.radio.monitor"""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
from signalhound.radio.monitor import main

if __name__ == "__main__":
    main()
