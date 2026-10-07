"""One static figure: true state vs belief over time + the kitchen grid.

    python visualize.py            # saves figure.png
"""
import matplotlib
matplotlib.use("Agg")  # no window needed: write a PNG
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402
from main import run_episode  # noqa: E402

OUT_FILE = "figure.png"
COLORS = ["tab:green", "tab:red", "tab:blue"]


def draw_grid(ax, row: dict) -> None:
    """Kitchen grid with locations, robot (R) and person (H)."""
    size = C.GRID_SIZE
    ax.set_xlim(-0.5, size - 0.5)
    ax.set_ylim(size - 0.5, -0.5)          # row 0 on top
    ax.set_xticks(range(size))
    ax.set_yticks(range(size))
    ax.grid(True)
    ax.set_aspect("equal")
    for name, (r, c) in C.LOCATIONS.items():
        ax.text(c, r + 0.35, name, ha="center", fontsize=8, color="gray")
    hr, hc = row["human_cell"]
    rr, rc = row["robot_cell"]
    ax.scatter([hc], [hr], s=500, c="tab:orange", marker="o", label="Person")
    ax.scatter([rc], [rr], s=500, c="tab:cyan", marker="s", label="Robot")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2,
              fontsize=7)
    ax.set_title(f"Step {row['step']}: person {row['true_state']}, "
                 f"robot action: {row['action']}", fontsize=9)


def main() -> None:
    rows = run_episode()
    steps = [r["step"] for r in rows]
    belief_keys = ["belief_cooking", "belief_needshelp", "belief_resting"]

    # Show the first Fetch (most interesting moment); else the first step.
    shown = next((r for r in rows if r["action"] == "Fetch"), rows[0])

    fig = plt.figure(figsize=(11, 8))
    ax1 = fig.add_subplot(2, 1, 1)
    for key, name, color in zip(belief_keys, C.STATES, COLORS):
        ax1.plot(steps, [r[key] for r in rows], color=color,
                 label=f"belief: {name}")
    for r in rows:   # true state as dots along the top edge
        ax1.scatter(r["step"], 1.04, c=COLORS[r["true_idx"]], s=25,
                    clip_on=False)
    ax1.axvline(C.ROUTINE_CHANGE_STEP, color="black", linestyle="--",
                label="routine change")
    ax1.set_ylim(0, 1.05)
    ax1.set_xlabel("step")
    ax1.set_ylabel("probability")
    ax1.set_title("Belief over time (dots on top = true state)", pad=18)
    ax1.legend(loc="center right", fontsize=8)

    draw_grid(fig.add_subplot(2, 2, 3), shown)
    ax3 = fig.add_subplot(2, 2, 4)
    ax3.plot(steps, [r["reward"] for r in rows], color="tab:purple")
    ax3.axvline(C.ROUTINE_CHANGE_STEP, color="black", linestyle="--")
    ax3.set_title("Reward per step", fontsize=9)
    ax3.set_xlabel("step")

    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=120)
    print(f"Saved {OUT_FILE}")


if __name__ == "__main__":
    main()
