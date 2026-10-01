"""Hackster figures. Usage (repo root):
  python docs/hackster/sim_matrix.py OUT/sim.json      # in an env with python-dotenv
  mkdir -p OUT/figs && python docs/hackster/plots.py OUT data/homing-history.jsonl   # needs matplotlib
Run 5 = lines 85-114 of the hackathon homing-history.jsonl (data/ is not committed)."""
import json, math, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
S = sys.argv[1]; H = sys.argv[2]
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
ramp = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
cmap = LinearSegmentedColormap.from_list("blue", ramp)
norm = Normalize(-75, -50)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "figure.facecolor": SURF, "axes.facecolor": SURF,
    "savefig.facecolor": SURF})
def clean(ax):
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)

rows = [json.loads(l) for l in open(H)][84:114]  # run 5, 2026-09-20 10:08:39-10:12:24, real Go2 odometry
xs = [r["x"] for r in rows]; ys = [r["y"] for r in rows]; rs = [r["rssi"] for r in rows]

# 1. run 5 trajectory
fig, ax = plt.subplots(figsize=(7.2, 8), dpi=170)
ax.plot(xs, ys, color=MUTED, lw=2, zorder=1, solid_capstyle="round")
sc = ax.scatter(xs, ys, c=rs, cmap=cmap, norm=norm, s=90, edgecolors=SURF, linewidths=2, zorder=2)
ax.annotate("start\n−61 dBm", (xs[0], ys[0]), xytext=(-62, 6), textcoords="offset points", color=INK2, fontsize=10)
ax.annotate("operator stop\n−51.3 dBm, rising", (xs[-1], ys[-1]), xytext=(-150, -4), textcoords="offset points", color=INK, fontsize=10, fontweight="bold")
for i, lab in [(10, "plane fit:\n4.0 dB/m → −139°"), (17, "plane fit:\n4.6 dB/m → −148°")]:
    ax.annotate(lab, (xs[i], ys[i]), xytext=(-110 if i == 10 else 12, -4), textcoords="offset points", color=INK2, fontsize=9)
ax.set_aspect("equal"); clean(ax)
ax.set_xlabel("x (m, Go2 odometry)"); ax.set_ylabel("y (m, Go2 odometry)")
cb = fig.colorbar(sc, ax=ax, shrink=0.7, pad=0.02); cb.set_label("RSSI of the person's phone (dBm)", color=INK2); cb.outline.set_visible(False)
ax.set_title("Run 5 on the real Go2: 39 autonomous moves,\n~12 m, steered only by Bluetooth signal strength", loc="left", fontsize=13, pad=12)
fig.text(0.01, 0.01, "Each dot = one stop-and-measure point (median of 2–10 BLE samples from the nRF7002-DK on the dog).\nHackMIT, 2026-09-20 10:08–10:12. The person's exact position was not recorded.", fontsize=8.5, color=MUTED)
fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(f"{S}/figs/run5-trajectory.png"); plt.close(fig)

# 2. run 5 RSSI per measurement
fig, ax = plt.subplots(figsize=(9, 4.2), dpi=160)
ax.plot(range(len(rs)), rs, color=ramp[4], lw=2, marker="o", ms=6, mec=SURF, mew=1.5)
ax.axhline(-52, color=INK2, lw=1, ls=(0, (4, 3)))
ax.text(0.3, -51.3, "arrival threshold set after this run (−52 dBm)", color=INK2, fontsize=9)
ax.annotate("−51.3 dBm", (len(rs) - 1, rs[-1]), xytext=(-70, 4), textcoords="offset points", fontsize=10, fontweight="bold")
ax.annotate("−73.5: wrong way → plane fit", (10, rs[10]), xytext=(8, -6), textcoords="offset points", fontsize=9, color=INK2)
clean(ax); ax.set_ylim(-77, -48)
ax.set_xlabel("measurement point (in order)"); ax.set_ylabel("RSSI (dBm)")
ax.set_title("Run 5: signal strength at each measurement point", loc="left", fontsize=13, pad=10)
fig.tight_layout(); fig.savefig(f"{S}/figs/run5-rssi.png"); plt.close(fig)

# 3. simulator small multiples
sim = json.load(open(f"{S}/sim.json"))
fig, axs = plt.subplots(3, 4, figsize=(12, 9.4), dpi=150)
for ax, c in zip(axs.flat, sim):
    p = [q for q in c["pts"] if q[0] is not None]
    px = [q[0] for q in p]; py = [q[1] for q in p]; pr = [q[2] if q[2] is not None else -80 for q in p]
    ax.plot(px, py, color=MUTED, lw=1.2, zorder=1)
    ax.scatter(px, py, c=pr, cmap=cmap, norm=norm, s=22, edgecolors=SURF, linewidths=1, zorder=2)
    ax.scatter([0], [0], marker="s", s=40, color=INK2, zorder=3)
    ax.scatter([c["tx"]], [c["ty"]], marker="*", s=220, color=INK, edgecolors=SURF, linewidths=1.5, zorder=4)
    ax.scatter([c["x"]], [c["y"]], marker="X", s=80, color=ramp[-1], edgecolors=SURF, linewidths=1.5, zorder=5)
    verdict = "stopped" if c["state"] == "FOUND" else "budget out"
    ax.set_title(f"{verdict} · {c['dist']:.1f} m off · {c['moves']} moves", fontsize=9.5, color=INK if c["dist"] < 2.5 else INK2,
                 fontweight="bold" if c["dist"] < 2.5 else "normal")
    ax.set_xlim(-6.5, 6.5); ax.set_ylim(-6.5, 6.5); ax.set_aspect("equal"); clean(ax); ax.tick_params(labelsize=8)
fig.suptitle("Simulator: final controller, 12 targets 4 m away, 5 dB multipath ripple, 3 dB noise, 10% packet loss",
             x=0.01, ha="left", fontsize=13)
fig.text(0.01, 0.01, "■ start   ★ person   ✕ where the dog stopped   dot color = simulated RSSI (same scale as the run 5 figure).\n"
         "8/12 stopped within 2.2 m; 3 stopped 3–3.8 m away on a multipath peak; 1 used up its 80-move budget.", fontsize=9, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 0.96)); fig.savefig(f"{S}/figs/sim-matrix.png"); plt.close(fig)
print("ok")
