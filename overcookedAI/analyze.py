"""Report figures and a summary table from the recorded games.

    python analyze.py                       # logs/ -> figures/
    python analyze.py --logs logs --out figures
    python analyze.py --include-aborted

Reads the per-game event files in ``logs/`` (see LOGGING.md) and compares the robots
on the divided kitchen. Games are always grouped by robot; the free ``condition``
label is ignored. By default games that did not reach the full time are left out.

The figures follow the argument of the report:

1. fig1_team_performance  Did the team serve more with an anticipating robot?
2. fig2_handoff_timing    Was the robot already at the counter when the human
                          handed something over? (the mechanism)
3. fig3_h_accuracy        How well did fixed and dynamic h predict that moment?
4. fig4_idle_time         Who waited: robot idle time and human time standing still.
5. fig5_score_over_time   When in the game the difference appears.

Needs only numpy and matplotlib.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ORDER = ["reactive", "anticipatory_fixed_h", "anticipatory_dynamic_h"]
LABELS = {"reactive": "Reactive", "anticipatory_fixed_h": "Fixed h",
          "anticipatory_dynamic_h": "Dynamic h"}
COLORS = {"reactive": "#8c8c8c", "anticipatory_fixed_h": "#1f77b4",
          "anticipatory_dynamic_h": "#e6550d"}
H_GROUPS = ("anticipatory_fixed_h", "anticipatory_dynamic_h")
H_WINDOW = 15.0         # same window as the logger's h_outcome rows

plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.spines.top": False,
                     "axes.spines.right": False})


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def label(group):
    return LABELS.get(group, group)


def color(group):
    return COLORS.get(group, "#2ca02c")


def info(row):
    try:
        return json.loads(row["info"])
    except (json.JSONDecodeError, TypeError):
        return {}


def station_index(name):
    try:
        return int(name.rsplit("#", 1)[1])
    except (IndexError, ValueError):
        return None


@dataclass
class Run:
    group: str
    rows: list
    summary: dict
    m: dict = field(default_factory=dict)

    def events(self, action):
        return [r for r in self.rows if r["action"] == action]

    @property
    def duration(self):
        return self.rows[-1]["t"]


def load_runs(logs, include_aborted):
    summary = {}
    path = os.path.join(logs, "summary.csv")
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            summary = {r["run_id"]: r for r in csv.DictReader(f)}
    runs = []
    skipped = defaultdict(int)
    for path in sorted(glob.glob(os.path.join(logs, "*.csv"))):
        if os.path.basename(path).startswith("summary"):
            continue
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows or rows[-1]["action"] != "game_end":
            skipped["never closed (crash or killed program)"] += 1
            continue
        if rows[-1]["info"] != "completed" and not include_aborted:
            skipped["aborted (use --include-aborted)"] += 1
            continue
        for r in rows:
            r["t"] = num(r["t"])
        runs.append(Run(rows[0]["robot"], rows, summary.get(rows[0]["run_id"], {})))
    for reason, count in skipped.items():
        print(f"skipped {count} game(s): {reason}")
    return runs


def ordered_groups(runs):
    present = {r.group for r in runs}
    return [g for g in ORDER if g in present] + sorted(present - set(ORDER))


# ----------------------------------------------------------------------
# Measures
# ----------------------------------------------------------------------
def handoffs(run):
    """(robot arrival minus human put, dwell, robot ready) for every completed handoff."""
    out = []
    for r in run.events("handoff"):
        i = info(r)
        out.append((i["robot_arrival_minus_put"], i["dwell"], bool(i["robot_ready"])))
    return out


def h_pairs(run):
    """Pair every h estimate with the real time until the human's next handoff action.

    Returns (predicted, actual, right_counter) for estimates made at most H_WINDOW
    seconds before that action. ``right_counter`` is whether the estimate named the
    counter the human actually used.
    """
    actions = [(r["t"], station_index(r["station"])) for r in run.rows
               if r["actor"] == "human" and r["action"] in ("put", "take")
               and r["station"].startswith("Handoff")]
    times = [t for t, _ in actions]
    out = []
    for r in run.events("horizon"):
        i = info(r)
        if i.get("remaining") is None or i.get("target") is None:
            continue
        k = bisect.bisect_right(times, r["t"])
        if k == len(actions):
            continue
        t_next, station = actions[k]
        actual = t_next - r["t"]
        if actual <= H_WINDOW:
            out.append((i["remaining"], actual, station == i["target"]))
    return out


def run_metrics(run):
    created = {r["order_id"]: r["t"] for r in run.events("order_new")}
    serves = run.events("serve")
    done = [r["t"] - created[r["order_id"]] for r in serves if r["order_id"] in created]
    ho = handoffs(run)
    pairs = [(p, a) for p, a, right in h_pairs(run) if right]
    errors = [p - a for p, a in pairs]
    s = run.summary
    minutes = run.duration / 60 if run.duration else math.nan
    return dict(
        score=num(run.rows[-1]["score"]),
        serves=len(serves),
        serves_per_min=len(serves) / minutes,
        expired=len(run.events("order_expired")),
        order_time=float(np.mean(done)) if done else math.nan,
        handoffs=len(ho),
        robot_ready_share=float(np.mean([r for _, _, r in ho])) if ho else math.nan,
        arrival_minus_put=float(np.mean([a for a, _, _ in ho])) if ho else math.nan,
        dwell_mean=float(np.mean([d for _, d, _ in ho])) if ho else math.nan,
        h_mae=float(np.mean(np.abs(errors))) if errors else math.nan,
        h_bias=float(np.mean(errors)) if errors else math.nan,
        robot_idle_s=num(s.get("robot_wait_s")),
        human_still_s=num(s.get("human_still_s")),
    )


# ----------------------------------------------------------------------
# Plot helpers
# ----------------------------------------------------------------------
def save(fig, out, name):
    path = os.path.join(out, name)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def group_legend(fig, groups, runs, extra=(), **kw):
    n = {g: sum(r.group == g for r in runs) for g in groups}
    handles = [Patch(color=color(g), label=f"{label(g)} ({n[g]} game{'s' if n[g] != 1 else ''})")
               for g in groups] + list(extra)
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False,
               bbox_to_anchor=(0.5, -0.02), **kw)


def dot_mean(ax, runs, groups, key, ylabel, title, fmt="{:.0f}", ylim=None):
    """One dot per game, a black bar at the group mean with its value printed above."""
    rng = np.random.default_rng(0)
    for x, g in enumerate(groups):
        ys = [r.m[key] for r in runs if r.group == g and not math.isnan(r.m[key])]
        if not ys:
            continue
        ax.scatter(x + rng.uniform(-0.1, 0.1, len(ys)), ys, s=40, color=color(g),
                   edgecolor="white", linewidth=0.6, zorder=3)
        mean = float(np.mean(ys))
        ax.plot([x - 0.25, x + 0.25], [mean, mean], color="black", lw=2, zorder=4)
        ax.annotate(fmt.format(mean), (x, mean), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([label(g) for g in groups])
    ax.set_xlim(-0.6, len(groups) - 0.4)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if ylim:
        ax.set_ylim(*ylim)
    else:
        ax.margins(y=0.2)
    ax.grid(axis="y", alpha=0.3)


MEAN_HANDLE = Line2D([], [], color="black", lw=2, label="mean (dots = games)")


# ----------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------
def fig_team_performance(runs, groups, out):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    dot_mean(axes[0], runs, groups, "score", "Points", "Final score")
    dot_mean(axes[1], runs, groups, "serves_per_min", "Orders per minute",
             "Orders served per minute", fmt="{:.2f}")
    dot_mean(axes[2], runs, groups, "order_time", "Seconds",
             "Time from order to serve\n(lower is better)", fmt="{:.1f}")
    fig.suptitle("Team performance", fontweight="bold")
    group_legend(fig, groups, runs, [MEAN_HANDLE])
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, out, "fig1_team_performance.png")


def fig_handoff_timing(runs, groups, out):
    ho = {g: [h for r in runs if r.group == g for h in handoffs(r)] for g in groups}
    groups = [g for g in groups if ho[g]]
    if not groups:
        return
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"width_ratios": [2.2, 1]})

    lim = 6.0
    ax.axvspan(-lim, 0, color="#2ca02c", alpha=0.08)
    ax.axvspan(0, lim, color="#d62728", alpha=0.08)
    ax.text(-lim + 0.15, len(groups) - 0.45, "robot was already waiting", color="#2ca02c",
            fontsize=9, va="top")
    ax.text(lim - 0.15, len(groups) - 0.45, "item waited for the robot", color="#d62728",
            fontsize=9, va="top", ha="right")
    rng = np.random.default_rng(0)
    for y, g in enumerate(groups):
        xs = np.clip([a for a, _, _ in ho[g]], -lim, lim)
        ax.scatter(xs, y + rng.uniform(-0.15, 0.15, len(xs)), s=28, color=color(g),
                   edgecolor="white", linewidth=0.5, zorder=3)
        median = float(np.median(xs))
        ax.plot([median, median], [y - 0.3, y + 0.3], color="black", lw=2, zorder=4)
        ax.annotate(f"median {median:+.1f} s", (median, y + 0.3), xytext=(0, 2),
                    textcoords="offset points", ha="center", fontsize=8)
    ax.axvline(0, color="black", lw=1)
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([label(g) for g in groups])
    ax.set_ylim(-0.6, len(groups) - 0.3)
    ax.set_xlim(-lim, lim)
    ax.set_xlabel("Robot arrival at the counter minus human placement (s)")
    ax.set_title("When did the robot reach the handoff counter? (one dot per handoff)")
    ax.grid(axis="x", alpha=0.3)

    ready = [100 * np.mean([r for _, _, r in ho[g]]) for g in groups]
    bars = bx.bar(range(len(groups)), ready, color=[color(g) for g in groups], width=0.6)
    for b, v, g in zip(bars, ready, groups):
        bx.annotate(f"{v:.0f}%\n({len(ho[g])})", (b.get_x() + b.get_width() / 2, v),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)
    bx.set_xticks(range(len(groups)))
    bx.set_xticklabels([label(g) for g in groups])
    bx.set_ylim(0, 115)
    bx.set_ylabel("% of handoffs")
    bx.set_title("Robot ready before the item arrived\n(number of handoffs in brackets)")
    bx.grid(axis="y", alpha=0.3)

    fig.suptitle("Handoff timing", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig2_handoff_timing.png")


def fig_h_accuracy(runs, out):
    pairs = {g: [p for r in runs if r.group == g for p in h_pairs(r)] for g in H_GROUPS}
    groups = [g for g in H_GROUPS if pairs[g]]
    if not groups:
        print("fig3 skipped: no fixed/dynamic h games with horizon estimates")
        return
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11, 4.4))

    top = 10.0
    ax.plot([0, top], [0, top], color="black", lw=1, ls="--", label="perfect prediction")
    for g in groups:
        pts = np.array([(a, p) for p, a, right in pairs[g] if right])
        if len(pts):
            ax.scatter(np.minimum(pts[:, 0], top), np.minimum(pts[:, 1], top), s=12,
                       alpha=0.45, color=color(g), label=label(g))
    ax.text(top * 0.97, top * 0.05, "below the line:\npredicted too early", ha="right",
            fontsize=8, color="0.35")
    ax.text(top * 0.03, top * 0.93, "above the line:\npredicted too late", fontsize=8,
            color="0.35", va="top")
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_aspect("equal")
    ax.set_xlabel("Actual time until the human's handoff (s)")
    ax.set_ylabel("Predicted time h (s)")
    ax.set_title("Predicted vs actual time to the next handoff")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.82), fontsize=8, frameon=False)
    ax.grid(alpha=0.3)

    data = [[abs(p - a) for p, a, right in pairs[g] if right] for g in groups]
    box = bx.boxplot(data, widths=0.5, patch_artist=True, showfliers=False)
    for patch, g in zip(box["boxes"], groups):
        patch.set(facecolor=color(g), alpha=0.35)
    for median in box["medians"]:
        median.set_color("black")
    for x, (g, errs) in enumerate(zip(groups, data), start=1):
        right = np.mean([r for _, _, r in pairs[g]]) * 100
        bias = np.mean([p - a for p, a, r in pairs[g] if r]) if errs else math.nan
        bx.annotate(f"mean error {np.mean(errs):.2f} s\nbias {bias:+.2f} s\nright counter {right:.0f}%",
                    (x, 1.0), xycoords=("data", "axes fraction"), xytext=(0, -4),
                    textcoords="offset points", ha="center", va="top", fontsize=8)
    bx.set_xticks(range(1, len(groups) + 1))
    bx.set_xticklabels([label(g) for g in groups])
    bx.set_ylim(0, None)
    ymax = max((np.percentile(d, 95) for d in data if d), default=1)
    bx.set_ylim(0, ymax * 1.6)
    bx.set_ylabel("|predicted - actual| (s)")
    bx.set_title("Prediction error per estimate")
    bx.grid(axis="y", alpha=0.3)

    fig.suptitle(f"Accuracy of the handoff-time estimate h (estimates up to {H_WINDOW:.0f} s "
                 "before the handoff, right counter only)", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig3_h_accuracy.png")


def fig_idle_time(runs, groups, out):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    dot_mean(axes[0], runs, groups, "robot_idle_s", "Seconds", "Robot time with no task",
             fmt="{:.1f}")
    dot_mean(axes[1], runs, groups, "human_still_s", "Seconds",
             "Human time standing still\n(includes chopping in place)", fmt="{:.1f}")
    fig.suptitle("Idle time per game (lower is better)", fontweight="bold")
    group_legend(fig, groups, runs, [MEAN_HANDLE])
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save(fig, out, "fig4_idle_time.png")


def fig_score_over_time(runs, groups, out, step=1.0):
    end = min(r.duration for r in runs)
    grid = np.arange(0, end + step / 2, step)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for g in groups:
        curves = []
        for run in (r for r in runs if r.group == g):
            ts = np.array([r["t"] for r in run.rows])
            sc = np.array([num(r["score"]) for r in run.rows])
            curves.append(sc[np.clip(np.searchsorted(ts, grid, side="right") - 1, 0, len(sc) - 1)])
        stack = np.array(curves)
        ax.step(grid, stack.mean(axis=0), where="post", color=color(g), lw=2.2,
                label=f"{label(g)} ({len(curves)} game{'s' if len(curves) != 1 else ''})")
        if len(curves) > 1:
            ax.fill_between(grid, stack.min(axis=0), stack.max(axis=0), step="post",
                            color=color(g), alpha=0.15, lw=0)
    ax.set_xlabel("Game time (s)")
    ax.set_ylabel("Score")
    ax.set_xlim(0, end)
    ax.set_title("Score over the game (line = mean, band = range across games)",
                 fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    save(fig, out, "fig5_score_over_time.png")


TABLE = [("score", "Final score", 0), ("serves_per_min", "Orders / min", 2),
         ("order_time", "Order to serve (s)", 1), ("expired", "Expired orders", 1),
         ("handoffs", "Handoffs", 1), ("robot_ready_share", "Robot ready share", 2),
         ("arrival_minus_put", "Arrival - put (s)", 2), ("dwell_mean", "Item dwell (s)", 2),
         ("h_mae", "h error (s)", 2), ("h_bias", "h bias (s)", 2),
         ("robot_idle_s", "Robot idle (s)", 1), ("human_still_s", "Human still (s)", 1)]


def write_table(runs, groups, out):
    """CSV with mean and SD per robot, and the same as a Markdown table on stdout."""
    stats = {}
    for g in groups:
        sel = [r.m for r in runs if r.group == g]
        for key, _, _ in TABLE:
            vals = [m[key] for m in sel if not math.isnan(m[key])]
            stats[g, key] = (float(np.mean(vals)) if vals else math.nan,
                             float(np.std(vals, ddof=1)) if len(vals) > 1 else math.nan)
    path = os.path.join(out, "summary_by_robot.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["robot", "games"] + [f"{k}_{s}" for k, _, _ in TABLE for s in ("mean", "sd")])
        for g in groups:
            row = [g, sum(r.group == g for r in runs)]
            for key, _, _ in TABLE:
                row += ["" if math.isnan(v) else round(v, 3) for v in stats[g, key]]
            w.writerow(row)
    print("wrote", path)

    def cell(g, key, digits):
        mean, sd = stats[g, key]
        if math.isnan(mean):
            return "-"
        return f"{mean:.{digits}f}" + ("" if math.isnan(sd) else f" ± {sd:.{digits}f}")

    print("\n| Measure | " + " | ".join(label(g) for g in groups) + " |")
    print("| --- |" + " --- |" * len(groups))
    print("| Games | " + " | ".join(str(sum(r.group == g for r in runs)) for g in groups) + " |")
    for key, name, digits in TABLE:
        print(f"| {name} | " + " | ".join(cell(g, key, digits) for g in groups) + " |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--out", default="figures")
    ap.add_argument("--include-aborted", action="store_true", help="also use games that did not finish")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    runs = load_runs(args.logs, args.include_aborted)
    if not runs:
        print("No games to plot in", args.logs, "- see the skipped lines above.")
        return
    lengths = sorted({round(r.duration) for r in runs})
    if len(lengths) > 1:
        print(f"warning: games have different lengths {lengths} s; compare per-minute measures")
    os.makedirs(args.out, exist_ok=True)
    groups = ordered_groups(runs)
    for run in runs:
        run.m = run_metrics(run)
    print(f"{len(runs)} games: " + ", ".join(f"{label(g)} {sum(r.group == g for r in runs)}"
                                             for g in groups))
    fig_team_performance(runs, groups, args.out)
    fig_handoff_timing(runs, groups, args.out)
    fig_h_accuracy(runs, args.out)
    fig_idle_time(runs, groups, args.out)
    fig_score_over_time(runs, groups, args.out)
    write_table(runs, groups, args.out)


if __name__ == "__main__":
    main()
