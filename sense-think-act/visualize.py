"""One static figure: belief over time + Overcooked-like kitchen.

    python visualize.py            # saves figure.png

Annotated with Sense / Think / Act so the PNG supports the report.
"""
import matplotlib
matplotlib.use("Agg")  # no window needed: write a PNG
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

import config as C  # noqa: E402
import theme as T  # noqa: E402
from main import run_episode  # noqa: E402

OUT_FILE = "figure.png"


def draw_grid(ax, row: dict) -> None:
    """Kitchen grid with Pot/Fridge stations, robot (R) and person (P)."""
    n = C.GRID_SIZE
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
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
        ax.text(c, r - 0.28, name + (" ON" if hot else ""), ha="center",
                fontsize=7, color=T.WHITE, weight="bold", zorder=2)
        if name == "Board":
            ax.add_patch(Rectangle((c - 0.28, r - 0.08), 0.56, 0.28,
                                   facecolor=T.BOARD_TOP, zorder=2))
            if row.get("food_on_board") or row["action"] == "Chop":
                ax.add_patch(Circle((c, r + 0.06), 0.10, facecolor=T.RED,
                                    zorder=3))
    for i in range(n + 1):
        ax.axhline(i - 0.5, color=T.GRID, lw=0.8, zorder=0.5)
        ax.axvline(i - 0.5, color=T.GRID, lw=0.8, zorder=0.5)

    hr, hc = row["human_cell"]
    rr, rc = row["robot_cell"]
    ax.add_patch(Circle((hc, hr), 0.32, facecolor=T.HUMAN,
                        edgecolor=T.DARK, linewidth=1.5, zorder=3,
                        label="Person"))
    ax.text(hc, hr, "P", ha="center", va="center", color=T.WHITE,
            weight="bold", zorder=4)
    ax.add_patch(FancyBboxPatch((rc - 0.32, rr - 0.32), 0.64, 0.64,
                                boxstyle="round,pad=0.01,rounding_size=0.08",
                                facecolor=T.ROBOT, edgecolor=T.DARK,
                                linewidth=1.5, zorder=3))
    ax.text(rc, rr, "R", ha="center", va="center", weight="bold",
            zorder=4, color=T.DARK)
    ax.legend(handles=[
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=T.HUMAN,
                   markersize=10, label="Person"),
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=T.ROBOT,
                   markersize=10, label="Robot"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, fontsize=7)
    ax.set_title(
        f"ACT @ step {row['step']}: {row['true_state']} -> {row['action']}\n"
        f"SENSE: {row['observation']}",
        fontsize=9)


def main() -> None:
    rows = run_episode()
    steps = [r["step"] for r in rows]
    belief_keys = ["belief_cooking", "belief_needshelp", "belief_resting"]

    # Prefer a Fetch frame; else first Ask; else first step.
    shown = next((r for r in rows if r["action"] == "Chop"), None)
    if shown is None:
        shown = next((r for r in rows if r["action"] == "Fetch"), rows[0])

    fig = plt.figure(figsize=(11, 8), facecolor=T.FLOOR)
    ax1 = fig.add_subplot(2, 1, 1)
    for key, name, color in zip(belief_keys, C.STATES, T.STATE):
        ax1.plot(steps, [r[key] for r in rows], color=color,
                 label=f"belief: {name}")
    for r in rows:
        ax1.scatter(r["step"], 1.04, c=[T.STATE[r["true_idx"]]], s=25,
                    clip_on=False)
    ax1.axvline(C.ROUTINE_CHANGE_STEP, color=T.DARK, linestyle="--",
                label="routine change")
    ax1.set_ylim(0, 1.05)
    ax1.set_xlabel("step")
    ax1.set_ylabel("probability")
    ax1.set_title("THINK: belief over time (dots on top = true state)",
                  pad=18)
    ax1.legend(loc="center right", fontsize=8)
    ax1.set_facecolor(T.WHITE)

    draw_grid(fig.add_subplot(2, 2, 3), shown)
    ax3 = fig.add_subplot(2, 2, 4)
    ax3.plot(steps, [r["reward"] for r in rows], color=T.ORANGE)
    ax3.axvline(C.ROUTINE_CHANGE_STEP, color=T.DARK, linestyle="--")
    ax3.set_title("Reward per step (ACT outcomes)", fontsize=9)
    ax3.set_xlabel("step")
    ax3.set_facecolor(T.WHITE)

    fig.suptitle("Sense → Think → Act  |  elderly home-care kitchen",
                 fontsize=12, weight="bold", color=T.DARK)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_FILE, dpi=120, facecolor=fig.get_facecolor())
    print(f"Saved {OUT_FILE}")


if __name__ == "__main__":
    main()
