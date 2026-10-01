"""System / wiring diagram for the Hackster schematics section. Run: python diagram.py out.png"""
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

SURF, INK, INK2, MUTED, LINE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#c9c8c2"
RADIO, CTRL, POWER = "#2a78d6", "#0b0b0b", "#8a8984"
plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURF, "savefig.facecolor": SURF})
fig, ax = plt.subplots(figsize=(15, 8.6), dpi=170)
ax.set_xlim(0, 17.6); ax.set_ylim(-0.2, 10.2); ax.axis("off")

def box(x, y, w, h, title, lines, edge=INK2, fill="#ffffff", ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.18", fc=fill, ec=edge, lw=1.6, ls=ls))
    ax.text(x + 0.25, y + h - 0.32, title, fontsize=12.5, fontweight="bold", color=INK, va="top")
    ax.text(x + 0.25, y + h - 0.82, "\n".join(lines), fontsize=10, color=INK2, va="top", linespacing=1.55)

def arrow(p, q, color, label, lx, ly, ha="center", style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=16, lw=2, color=color, ls=ls, shrinkA=0, shrinkB=0))
    ax.text(lx, ly, label, fontsize=9.5, color=INK2, ha=ha, va="center", linespacing=1.4,
            bbox=dict(fc=SURF, ec="none", pad=1.5))

# carried-by-the-dog container
ax.add_patch(FancyBboxPatch((5.6, 0.45), 5.6, 8.05, boxstyle="round,pad=0,rounding_size=0.25", fc="#f3f2ee", ec=LINE, lw=1.4, ls=(0, (5, 3))))
ax.text(5.85, 8.25, "Mounted on / part of the robot dog", fontsize=10, color=MUTED, va="top", style="italic")

box(0.4, 3.9, 3.6, 2.7, "Person's phone", ["Galaxy S25 + nRF Connect", "BLE beacon, name filter target", "100 ms advertising interval"])
box(5.9, 4.55, 5.0, 3.3, "Nordic nRF7002-DK", ["App core (nRF5340): Zephyr app,", "  continuous active BLE scan,", "  RSSI of the target, batches last 16", "Net core: hci_ipc BLE controller", "Flashed over on-board J-Link"])
box(5.9, 3.05, 5.0, 0.95, "USB power bank", [], edge=POWER)
box(5.9, 0.85, 5.0, 1.75, "Unitree Go2", ["Sport mode: StandUp / Move / StopMove", "Odometry: x, y, yaw"])
box(13.4, 0.85, 4.0, 7.0, "Laptop (Python)", ["bleak BLE receiver", "decode 16-sample batches,", "  drop duplicates", "", "rolling median + EMA filter", "", "homing controller", "  climb → probe → plane-fit", "  gradient → return-to-best", "", "MotionGuard safety layer", "  speed caps, short bursts,", "  stop after every burst,", "  Ctrl+C = StopMove", "", "terminal dashboard + logs"])

arrow((4.0, 5.25), (5.9, 5.25), RADIO, "BLE adverts\n2.4 GHz", 4.95, 5.85)
arrow((8.4, 4.0), (8.4, 4.55), POWER, "USB 5 V (the only wire)", 8.7, 4.27, ha="left")
arrow((10.9, 6.2), (13.4, 6.2), RADIO, "BLE advert:\n16 RSSI samples\n+ running index", 12.15, 7.0)
arrow((13.4, 2.05), (10.9, 2.05), CTRL, "Wi-Fi / WebRTC\nmotion bursts", 12.15, 2.75)
arrow((10.9, 1.3), (13.4, 1.3), CTRL, "pose telemetry", 12.15, 0.85, ls=(0, (4, 3)))

ax.text(0.4, 10.0, "SignalHound: system and wiring", fontsize=16, fontweight="bold", color=INK, va="top")
ax.text(0.4, 9.35, "No custom circuit. The DK's only wire is USB power; every data link is wireless.", fontsize=10.5, color=INK2, va="top")
ax.plot([0.45, 0.95], [0.55, 0.55], color=RADIO, lw=2); ax.text(1.05, 0.55, "radio / sensing", fontsize=9, color=INK2, va="center")
ax.plot([0.45, 0.95], [0.2, 0.2], color=CTRL, lw=2); ax.text(1.05, 0.2, "robot control", fontsize=9, color=INK2, va="center")
ax.plot([2.6, 3.1], [0.55, 0.55], color=POWER, lw=2); ax.text(3.2, 0.55, "power", fontsize=9, color=INK2, va="center")
fig.savefig(sys.argv[1], bbox_inches="tight", pad_inches=0.25)
