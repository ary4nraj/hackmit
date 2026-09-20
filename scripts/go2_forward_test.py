"""Tiny forward burst: 0.2 m/s for 0.5 s (override: --speed --seconds)."""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import argparse, asyncio
from scripts._go2_burst_test import run

p = argparse.ArgumentParser(); p.add_argument("--speed", type=float, default=0.2); p.add_argument("--seconds", type=float, default=0.5)
p.add_argument("--yes", action="store_true", help="skip the interactive YES (operator confirmed out of band)")
a = p.parse_args(); asyncio.run(run("forward", a.speed, a.seconds))
