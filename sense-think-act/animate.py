"""Animated visualisation of the sense-think-act loop.

    python animate.py              # saves animation.gif
    python animate.py --show       # opens a live window instead
    python animate.py --frame 34   # saves frame_34.png (one still frame)

Layout (three labelled phases):
  SENSE  - noisy observation the robot just received
  THINK  - belief bars + why this action was chosen
  ACT    - kitchen (Overcooked-like colours) + speech bubble
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
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

import config as C  # noqa: E402
import theme as T  # noqa: E402
from main import run_episode  # noqa: E402

BUBBLE = {
    "Wait": "...",
    "Keep distance": "(giving space)",
    "Ask": "Do you need help?",
    "Fetch": "Fetching it for you!",
    "Chop": "Chopping that for you!",
}
BELIEF_KEYS = ["belief_cooking", "belief_needshelp", "belief_resting"]


def _think_reason(row: dict) -> str:
    """One-line explanation of how the belief led to the action."""
    peak = C.STATES[int(max(range(3), key=lambda i: row[BELIEF_KEYS[i]]))]
    if row["safety_fired"]:
        return (f"belief peaks at {peak}, but SAFETY: pot on + person "
                "near -> Ask first (no autonomous Fetch)")
    if row["action"] == "Chop":
        return f"food left on the board + belief {peak} -> Chop"
    return f"belief peaks at {peak} -> choose {row['action']}"


def draw_sense(ax, row: dict) -> None:
    """SENSE panel: raw observation (or dropout)."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("SENSE", fontsize=12, weight="bold", loc="left",
                 color=T.DARK)
    ax.text(0.02, 0.72, "Observation this step", fontsize=9, color=T.DARK)
    obs = row["observation"]
    ax.add_patch(FancyBboxPatch((0.02, 0.15), 0.96, 0.45,
                                boxstyle="round,pad=0.02",
                                facecolor=T.WHITE, edgecolor=T.STATION_EDGE,
                                linewidth=1.5))
    ax.text(0.5, 0.38, obs, ha="center", va="center", fontsize=9,
            wrap=True, color=T.DARK)
    ax.text(0.02, 0.92, "Sensors: zone + gesture + idle + verbal "
            "(15% dropout)", fontsize=8, color=T.STATION_EDGE)


def draw_think(ax, row: dict) -> None:
    """THINK panel: belief bars + action rationale."""
    values = [row[k] for k in BELIEF_KEYS]
    bars = ax.barh(C.STATES, values, color=T.STATE, edgecolor=T.DARK,
                   linewidth=0.5)
    bars[row["true_idx"]].set_linewidth(2.5)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.set_title("THINK  (black outline = true state)", fontsize=11,
                 weight="bold", loc="left", color=T.DARK)
    ax.set_xlabel("belief", fontsize=8)
    ax.text(0.5, -0.22, _think_reason(row), transform=ax.transAxes,
            ha="center", fontsize=8, color=T.DARK,
            bbox={"boxstyle": "round", "fc": T.WHITE, "ec": T.STATION_EDGE})


def draw_act(ax, row: dict) -> None:
    """ACT panel: kitchen grid with Overcooked-like stations."""
    n = C.GRID_SIZE
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")
    ax.set_facecolor(T.FLOOR)
    ax.add_patch(Rectangle((-0.5, -0.5), n, n, facecolor=T.FLOOR,
                           edgecolor="none", zorder=0))

    pot_on = row["true_idx"] in (C.COOKING, C.NEEDS_HELP)
    for name, (r, c) in C.LOCATIONS.items():
        hot = name == "Pot" and pot_on
        face = T.ORANGE if hot else T.STATION[name]
        box = "round,pad=0.02,rounding_size=0.12"
        ax.add_patch(FancyBboxPatch((c - 0.45, r - 0.45), 0.9, 0.9,
                                    boxstyle=box, facecolor=face,
                                    edgecolor=T.STATION_EDGE, linewidth=2,
                                    zorder=1))
        label = name + (" ON" if hot else "")
        ax.text(c, r - 0.28, label, ha="center", fontsize=7, color=T.WHITE,
                weight="bold", zorder=2)
        if name == "Board":
            ax.add_patch(Rectangle((c - 0.28, r - 0.08), 0.56, 0.28,
                                   facecolor=T.BOARD_TOP, zorder=2))
            if row["food_on_board"] or row["action"] == "Chop":
                ax.add_patch(Circle((c, r + 0.06), 0.10, facecolor=T.RED,
                                    zorder=3))
            if row["action"] == "Chop" and row["chop_left"]:
                done = 1 - row["chop_left"] / C.CHOP_STEPS
                ax.add_patch(Rectangle((c - 0.3, r + 0.28), 0.6 * done, 0.08,
                                       facecolor=T.YELLOW, zorder=3))

    for i in range(n + 1):
        ax.axhline(i - 0.5, color=T.GRID, lw=0.8, zorder=0.5)
        ax.axvline(i - 0.5, color=T.GRID, lw=0.8, zorder=0.5)

    hr, hc = row["human_cell"]
    rr, rc = row["robot_cell"]
    ax.add_patch(Circle((hc, hr), 0.32, facecolor=T.HUMAN,
                        edgecolor=T.DARK, linewidth=1.5, zorder=3))
    ax.text(hc, hr, "P", ha="center", va="center", color=T.WHITE,
            weight="bold", zorder=4)
    ax.add_patch(FancyBboxPatch((rc - 0.32, rr - 0.32), 0.64, 0.64,
                                boxstyle="round,pad=0.01,rounding_size=0.08",
                                facecolor=T.ROBOT, edgecolor=T.DARK,
                                linewidth=1.5, zorder=3))
    ax.text(rc, rr, "R", ha="center", va="center", weight="bold",
            zorder=4, color=T.DARK)
    ax.text(rc, rr + 0.62, BUBBLE[row["action"]], ha="center", fontsize=8,
            bbox={"boxstyle": "round", "fc": T.WHITE, "ec": T.STATION_EDGE},
            zorder=5)
    if row["safety_fired"]:
        ax.text(2, 2.0, "SAFETY: pot on + person near\n"
                "-> Ask first, do not Fetch",
                ha="center", color=T.WHITE, weight="bold", fontsize=9,
                bbox={"boxstyle": "round", "fc": T.RED}, zorder=6)
    ax.set_title(f"ACT   step {row['step']}  |  person {row['true_state']}"
                 f"  |  {row['action']}  |  reward {row['reward']:+.1f}",
                 fontsize=11, weight="bold", loc="left", color=T.DARK)


def draw_timeline(ax, rows: list, i: int) -> None:
    """Belief and hidden fatigue up to the current step."""
    steps = [r["step"] for r in rows[:i + 1]]
    for key, name, color in zip(BELIEF_KEYS, C.STATES, T.STATE):
        ax.plot(steps, [r[key] for r in rows[:i + 1]], color=color,
                label=name)
    ax.plot(steps, [r["fatigue"] for r in rows[:i + 1]], color=T.STATION_EDGE,
            linestyle=":", label="fatigue (hidden)")
    for r in rows[:i + 1]:
        ax.scatter(r["step"], 1.05, c=[T.STATE[r["true_idx"]]], s=15,
                   clip_on=False)
    ax.axvline(C.ROUTINE_CHANGE_STEP, color=T.DARK, linestyle="--")
    ax.text(C.ROUTINE_CHANGE_STEP + 0.5, 0.5, "routine\nchange",
            fontsize=8)
    ax.set_xlim(0, C.N_STEPS - 1)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("step")
    ax.set_title("Belief over time", fontsize=10)
    ax.legend(loc="upper left", fontsize=7, ncol=2)


def main() -> None:
    rows = run_episode()
    fig = plt.figure(figsize=(13, 7.5), facecolor=T.FLOOR)
    # Top row: SENSE | THINK ; bottom: ACT | timeline
    ax_sense = fig.add_subplot(2, 2, 1)
    ax_think = fig.add_subplot(2, 2, 2)
    ax_act = fig.add_subplot(2, 2, 3)
    ax_time = fig.add_subplot(2, 2, 4)

    def draw(i: int) -> None:
        for ax in (ax_sense, ax_think, ax_act, ax_time):
            ax.clear()
        draw_sense(ax_sense, rows[i])
        draw_think(ax_think, rows[i])
        draw_act(ax_act, rows[i])
        draw_timeline(ax_time, rows, i)
        fig.suptitle("Sense → Think → Act  (elderly home-care kitchen)",
                     fontsize=13, weight="bold", color=T.DARK, y=0.98)
        fig.tight_layout(rect=[0, 0, 1, 0.96])

    if args.frame is not None:
        draw(args.frame)
        out = f"frame_{args.frame}.png"
        fig.savefig(out, dpi=110, facecolor=fig.get_facecolor())
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
