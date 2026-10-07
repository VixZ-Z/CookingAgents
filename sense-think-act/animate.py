"""Animated visualisation of the sense-think-act loop.

    python animate.py              # saves animation.gif
    python animate.py --show       # opens a live window instead
    python animate.py --frame 34   # saves frame_34.png (one still frame)

Left: kitchen with person (colour = TRUE state) and robot (speech bubble =
chosen action). Right: the robot's belief now, and belief + fatigue over time.
"""
import argparse

import matplotlib

parser = argparse.ArgumentParser()
parser.add_argument("--show", action="store_true", help="live window")
parser.add_argument("--frame", type=int, help="save one frame as PNG")
parser.add_argument("--fps", type=int, default=3)
args = parser.parse_args()
if not args.show:
    matplotlib.use("Agg")  # no window needed

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

import config as C  # noqa: E402
from main import run_episode  # noqa: E402

COLORS = ["tab:green", "tab:red", "tab:blue"]
BUBBLE = {
    "Wait": "...",
    "Keep distance": "(keeping my distance)",
    "Ask": "Do you need help?",
    "Fetch": "Fetching it for you!",
}
BELIEF_KEYS = ["belief_cooking", "belief_needshelp", "belief_resting"]


def draw_grid(ax, row: dict) -> None:
    """Kitchen: locations, stove glow, person, robot, speech bubble."""
    n = C.GRID_SIZE
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")
    stove_on = row["true_idx"] in (C.COOKING, C.NEEDS_HELP)
    for name, (r, c) in C.LOCATIONS.items():
        hot = name == "Stove" and stove_on
        ax.add_patch(Rectangle((c - 0.5, r - 0.5), 1, 1,
                               color="salmon" if hot else "wheat"))
        ax.text(c, r - 0.35, name + (" (ON)" if hot else ""), ha="center",
                fontsize=8)
    for i in range(n + 1):
        ax.axhline(i - 0.5, color="lightgray", lw=0.8)
        ax.axvline(i - 0.5, color="lightgray", lw=0.8)

    hr, hc = row["human_cell"]
    rr, rc = row["robot_cell"]
    ax.scatter([hc], [hr], s=900, c=COLORS[row["true_idx"]],
               edgecolors="black", zorder=3)
    ax.text(hc, hr, "P", ha="center", va="center", color="white",
            weight="bold", zorder=4)
    ax.scatter([rc], [rr], s=900, c="tab:cyan", marker="s",
               edgecolors="black", zorder=3)
    ax.text(rc, rr, "R", ha="center", va="center", weight="bold", zorder=4)
    ax.text(rc, rr + 0.62, BUBBLE[row["action"]], ha="center", fontsize=8,
            bbox={"boxstyle": "round", "fc": "white", "ec": "gray"},
            zorder=5)
    if row["safety_fired"]:
        ax.text(2, 2.0, "SAFETY RULE: stove on + person near\n"
                "-> robot asks first, does not fetch",
                ha="center", color="white", weight="bold", fontsize=9,
                bbox={"boxstyle": "round", "fc": "tab:red"}, zorder=6)
    ax.set_title(f"Step {row['step']}  |  person is {row['true_state']}"
                 f"  |  reward {row['reward']:+.1f}", fontsize=10)
    ax.set_xlabel("sensor: " + row["observation"], fontsize=8)


def draw_bars(ax, row: dict) -> None:
    """Current belief; thick outline marks the true state."""
    values = [row[k] for k in BELIEF_KEYS]
    bars = ax.barh(C.STATES, values, color=COLORS)
    bars[row["true_idx"]].set_edgecolor("black")
    bars[row["true_idx"]].set_linewidth(3)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.set_title("Robot belief (black outline = truth)", fontsize=10)


def draw_timeline(ax, rows: list, i: int) -> None:
    """Belief and hidden fatigue up to the current step."""
    steps = [r["step"] for r in rows[:i + 1]]
    for key, name, color in zip(BELIEF_KEYS, C.STATES, COLORS):
        ax.plot(steps, [r[key] for r in rows[:i + 1]], color=color,
                label=name)
    ax.plot(steps, [r["fatigue"] for r in rows[:i + 1]], color="gray",
            linestyle=":", label="fatigue (hidden)")
    for r in rows[:i + 1]:
        ax.scatter(r["step"], 1.05, c=COLORS[r["true_idx"]], s=15,
                   clip_on=False)
    ax.axvline(C.ROUTINE_CHANGE_STEP, color="black", linestyle="--")
    ax.text(C.ROUTINE_CHANGE_STEP + 0.5, 0.5, "routine\nchange",
            fontsize=8)
    ax.set_xlim(0, C.N_STEPS - 1)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("step")
    ax.legend(loc="upper left", fontsize=7, ncol=2)


def main() -> None:
    rows = run_episode()
    fig = plt.figure(figsize=(12, 6))
    ax_grid = fig.add_subplot(1, 2, 1)
    ax_bars = fig.add_subplot(2, 2, 2)
    ax_time = fig.add_subplot(2, 2, 4)

    def draw(i: int) -> None:
        for ax in (ax_grid, ax_bars, ax_time):
            ax.clear()
        draw_grid(ax_grid, rows[i])
        draw_bars(ax_bars, rows[i])
        draw_timeline(ax_time, rows, i)
        fig.tight_layout()

    if args.frame is not None:
        draw(args.frame)
        out = f"frame_{args.frame}.png"
        fig.savefig(out, dpi=110)
        print(f"Saved {out}")
    elif args.show:
        anim = FuncAnimation(fig, draw, frames=len(rows),
                             interval=1000 // args.fps, repeat=False)
        plt.show()
        del anim
    else:
        anim = FuncAnimation(fig, draw, frames=len(rows))
        anim.save("animation.gif", writer=PillowWriter(fps=args.fps))
        print("Saved animation.gif")


if __name__ == "__main__":
    main()
