"""Report figures and a summary table from the recorded games.

    python analyze.py                       # logs/ -> figures/
    python analyze.py --logs logs --out figures --group robot
    python analyze.py --include-aborted --include-participant dev

Reads the per-game event files in ``logs/`` (see LOGGING.md). Runs are grouped by
robot (default) or by the free ``condition`` label. By default games that did not
reach the full time and the practice participant ``dev`` are left out.
Needs only numpy and matplotlib.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ORDER = ["reactive", "anticipatory_fixed_h", "anticipatory_dynamic_h"]
LABELS = {"reactive": "Reactive", "anticipatory_fixed_h": "Anticipatory\nfixed h",
          "anticipatory_dynamic_h": "Anticipatory\ndynamic h"}
COLORS = {"reactive": "#7f7f7f", "anticipatory_fixed_h": "#1f77b4",
          "anticipatory_dynamic_h": "#d62728"}
H_GROUPS = ("anticipatory_fixed_h", "anticipatory_dynamic_h")
PACE_KEYS = ["take:crate", "put:board", "take:board", "put:counter", "take:counter"]


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def label(group):
    return LABELS.get(group, group)


def color(group, index=0):
    return COLORS.get(group, plt.cm.tab10(index % 10))


@dataclass
class Run:
    group: str
    participant: str
    rows: list
    summary: dict

    def events(self, action):
        return [r for r in self.rows if r["action"] == action]

    def info(self, row):
        try:
            return json.loads(row["info"])
        except (json.JSONDecodeError, TypeError):
            return {}


def load_runs(logs, group_by, include_aborted, include_participants):
    summary = {}
    path = os.path.join(logs, "summary.csv")
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            summary = {r["run_id"]: r for r in csv.DictReader(f)}
    runs = []
    for path in sorted(glob.glob(os.path.join(logs, "*.csv"))):
        if os.path.basename(path).startswith("summary"):
            continue
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows or rows[-1]["action"] != "game_end":
            continue
        meta = rows[0]
        completed = rows[-1]["info"] == "completed"
        if (not completed and not include_aborted) or (
                meta["participant"] == "dev" and "dev" not in include_participants):
            continue
        for r in rows:
            r["t"] = num(r["t"])
        runs.append(Run(meta[group_by] or meta["robot"], meta["participant"], rows,
                        summary.get(meta["run_id"], {})))
    return runs


def ordered_groups(runs):
    present = {r.group for r in runs}
    return [g for g in ORDER if g in present] + sorted(present - set(ORDER))


def run_metrics(run):
    rows = run.rows
    created = {r["order_id"]: r["t"] for r in run.events("order_new")}
    done = [r["t"] - created[r["order_id"]] for r in run.events("serve") if r["order_id"] in created]
    duration = rows[-1]["t"]
    serves = len(run.events("serve"))
    s = run.summary
    waits = [num(s.get(k)) for k in ("robot_wait_s", "human_still_s", "human_distance_px")]
    robot_actions = num(s.get("robot_actions"))
    return dict(
        score=num(rows[-1]["score"]), serves=serves,
        serves_per_min=serves / (duration / 60) if duration else math.nan,
        expired=len(run.events("order_expired")),
        order_time=float(np.mean(done)) if done else math.nan,
        dwell_mean=num(s.get("dwell_mean")), late_share=num(s.get("robot_late_share")),
        h_mae=num(s.get("h_mae")), h_bias=num(s.get("h_bias")),
        robot_wait_s=waits[0], human_still_s=waits[1], human_distance_px=waits[2],
        anticipating_share=(num(s.get("robot_anticipating_actions")) / robot_actions
                            if robot_actions and not math.isnan(robot_actions) else math.nan))


def box_strip(ax, values, groups, ylabel, title=None, ylim=None):
    """Box plot with one dot per value; faint lines join a participant's group means."""
    data = [[v for _, v in values.get(g, []) if not math.isnan(v)] for g in groups]
    if not any(data):
        ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    positions = np.arange(len(groups))
    kept = [i for i, d in enumerate(data) if d]
    box = ax.boxplot([data[i] for i in kept], positions=positions[kept], widths=0.5,
                     patch_artist=True, showfliers=False)
    for patch, i in zip(box["boxes"], kept):
        patch.set(facecolor=color(groups[i], i), alpha=0.25)
    for median in box["medians"]:
        median.set_color("black")
    rng = np.random.default_rng(0)
    for i, g in enumerate(groups):
        ys = [v for _, v in values.get(g, []) if not math.isnan(v)]
        ax.scatter(i + rng.uniform(-0.12, 0.12, len(ys)), ys, s=18, alpha=0.7,
                   color=color(g, i), zorder=3)
    per_person = defaultdict(dict)
    for i, g in enumerate(groups):
        by = defaultdict(list)
        for who, v in values.get(g, []):
            if not math.isnan(v):
                by[who].append(v)
        for who, vs in by.items():
            per_person[who][i] = float(np.mean(vs))
    for means in per_person.values():
        if len(means) > 1:
            xs = sorted(means)
            ax.plot(xs, [means[x] for x in xs], color="black", alpha=0.15, lw=1, zorder=1)
    ax.set_xticks(positions)
    ax.set_xticklabels([label(g) for g in groups], fontsize=8)
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    if title:
        ax.set_title(title, fontsize=10)
    ax.grid(axis="y", alpha=0.3)


def collect(runs, metrics, key):
    out = defaultdict(list)
    for run in runs:
        out[run.group].append((run.participant, metrics[id(run)][key]))
    return out


def save(fig, out, name):
    fig.tight_layout()
    path = os.path.join(out, name)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print("wrote", path)


def fig_outcomes(runs, groups, metrics, out):
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    panels = [("score", "Final score"), ("serves_per_min", "Orders served per minute"),
              ("expired", "Expired orders"), ("order_time", "Mean order completion time (s)"),
              ("robot_wait_s", "Robot time without a task (s)"),
              ("anticipating_share", "Share of robot actions that anticipate")]
    for ax, (key, name) in zip(axes.flat, panels):
        box_strip(ax, collect(runs, metrics, key), groups, name,
                  ylim=(-0.05, 1.05) if key.endswith("share") else None)
    fig.suptitle("Task outcomes per game (dots = games, grey lines = participants)")
    save(fig, out, "fig1_outcomes.png")


def fig_handoff(runs, groups, metrics, out):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    dwell, arrival = defaultdict(list), defaultdict(list)
    for run in runs:
        for r in run.events("handoff"):
            info = run.info(r)
            dwell[run.group].append((run.participant, info["dwell"]))
            arrival[run.group].append(info["robot_arrival_minus_put"])
    box_strip(axes[0], dwell, groups, "Seconds", "Item waiting on a handoff counter")
    ax = axes[1]
    bins = np.linspace(-10, 10, 41)
    for i, g in enumerate(groups):
        if arrival[g]:
            ax.hist(np.clip(arrival[g], -10, 10), bins=bins, alpha=0.45, color=color(g, i),
                    label=label(g).replace("\n", " "))
    ax.axvline(0, color="black", lw=1)
    ax.set_xlabel("Robot arrival minus human placement (s)\n<0: robot ready first, >0: robot late")
    ax.set_ylabel("Handoffs")
    ax.legend(fontsize=8)
    ax.set_title("Was the robot ready at the handoff?", fontsize=10)
    box_strip(axes[2], collect(runs, metrics, "late_share"), groups, "Share of handoffs",
              "Handoffs where the robot arrived after the item", ylim=(-0.05, 1.05))
    save(fig, out, "fig2_handoff.png")


def h_events(run):
    return [(r["t"], run.info(r)) for r in run.events("h_outcome")]


def fig_h_accuracy(runs, out):
    h_runs = [r for r in runs if r.group in H_GROUPS]
    groups = [g for g in H_GROUPS if any(r.group == g for r in h_runs)]
    if not groups:
        return
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    mae, bias, rate = defaultdict(list), defaultdict(list), defaultdict(list)
    binned = {g: defaultdict(list) for g in groups}
    for run in h_runs:
        for t, info in h_events(run):
            if info.get("mae") is not None:
                mae[run.group].append((run.participant, info["mae"]))
                bias[run.group].append((run.participant, info["bias"]))
                binned[run.group][int(t // 20)].append(info["mae"])
            if info.get("estimates"):
                rate[run.group].append((run.participant, info["right_station"] / info["estimates"]))
    box_strip(axes[0], mae, groups, "Mean absolute error per handoff (s)", "h error")
    box_strip(axes[1], bias, groups, "Estimate minus actual (s)", "h bias (>0: too slow)")
    axes[1].axhline(0, color="black", lw=1)
    box_strip(axes[2], rate, groups, "Share of estimates", "Estimates naming the right counter",
            ylim=(-0.05, 1.05))
    ax = axes[3]
    for i, g in enumerate(groups):
        xs = sorted(binned[g])
        if xs:
            ax.plot([x * 20 + 10 for x in xs], [np.mean(binned[g][x]) for x in xs], marker="o",
                    color=color(g), label=label(g).replace("\n", " "))
    ax.set_xlabel("Game time (s)")
    ax.set_ylabel("Mean absolute error (s)")
    ax.set_title("Does h improve during the game?", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    save(fig, out, "fig3_h_accuracy.png")


def fig_pace(runs, out):
    dyn = [r for r in runs if r.group == "anticipatory_dynamic_h" and r.events("pace")]
    if not dyn:
        return
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    ax = axes[0]
    keys = [k for k in PACE_KEYS if any(k in r.info(p).get("handling", {})
                                       for r in dyn for p in r.events("pace"))]
    for i, key in enumerate(keys):
        labelled = False
        for run in dyn:
            pts = [(p["t"], run.info(p)["handling"][key]["seconds"]) for p in run.events("pace")
                   if key in run.info(p).get("handling", {})]
            if pts:
                ax.step(*zip(*pts), where="post", color=plt.cm.tab10(i), alpha=0.5,
                        label=None if labelled else key)
                labelled = True
    ax.axhline(0.2, color="black", ls=":", lw=1)
    ax.set_xlabel("Game time (s)")
    ax.set_ylabel("Learned handling time per step (s)")
    ax.set_title("What dynamic h learns about the player", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax = axes[1]
    final = defaultdict(lambda: defaultdict(list))
    for run in dyn:
        last = run.info(run.events("pace")[-1]).get("handling", {})
        for key in keys:
            if key in last:
                final[run.participant][key].append(last[key]["seconds"])
    people = sorted(final)
    width = 0.8 / max(len(people), 1)
    for j, who in enumerate(people):
        ax.bar(np.arange(len(keys)) + j * width,
               [np.mean(final[who][k]) if final[who][k] else 0 for k in keys], width,
               label=who)
    ax.set_xticks(np.arange(len(keys)) + 0.4 - width / 2)
    ax.set_xticklabels(keys, rotation=20, fontsize=8)
    ax.set_ylabel("End-of-game handling time (s)")
    ax.set_title("Pace differs between players", fontsize=10)
    ax.legend(fontsize=8)
    save(fig, out, "fig4_pace.png")


def fig_timeline(runs, groups, out, step=2.0):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for i, g in enumerate(groups):
        curves = []
        for run in (r for r in runs if r.group == g):
            end = run.rows[-1]["t"]
            grid = np.arange(0, end + step, step)
            ts = np.array([r["t"] for r in run.rows])
            sc = np.array([num(r["score"]) for r in run.rows])
            curve = sc[np.clip(np.searchsorted(ts, grid, side="right") - 1, 0, len(sc) - 1)]
            curves.append((grid, curve))
            ax.plot(grid, curve, color=color(g, i), alpha=0.15, lw=1)
        if curves:
            n = min(len(c[0]) for c in curves)
            stack = np.array([c[1][:n] for c in curves])
            ax.plot(curves[0][0][:n], stack.mean(axis=0), color=color(g, i), lw=2.5,
                    label=f"{label(g).replace(chr(10), ' ')} (n={len(curves)})")
    ax.set_xlabel("Game time (s)")
    ax.set_ylabel("Score")
    ax.set_title("Score over the game (thin = games, thick = mean)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    save(fig, out, "fig5_score_timeline.png")


def fig_behaviour(runs, groups, metrics, out):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
    for ax, (key, name) in zip(axes, [("human_distance_px", "Human distance walked (px)"),
                                      ("human_still_s", "Human time standing or chopping (s)"),
                                      ("robot_wait_s", "Robot time without a task (s)")]):
        box_strip(ax, collect(runs, metrics, key), groups, name)
    save(fig, out, "fig6_behaviour.png")


def fig_heatmap(runs, groups, out):
    try:
        import config as C
        extent = (0, C.WIDTH, C.HEIGHT, 0)
    except ImportError:
        extent = None
    fig, axes = plt.subplots(1, len(groups), figsize=(4.8 * len(groups), 4), squeeze=False)
    for ax, g in zip(axes[0], groups):
        pts = [(num(r["x"]), num(r["y"])) for run in runs if run.group == g
               for r in run.rows if r["kind"] == "pos" and r["actor"] == "human"]
        pts = [p for p in pts if not math.isnan(p[0])]
        ax.set_title(label(g).replace("\n", " "), fontsize=10)
        if not pts:
            ax.set_axis_off()
            continue
        xs, ys = zip(*pts)
        ax.hist2d(xs, ys, bins=(48, 30), cmap="magma", range=None if extent is None else
                  [[extent[0], extent[1]], [extent[3], extent[2]]])
        ax.invert_yaxis()
        ax.set_aspect("equal")
    fig.suptitle("Where the human spends time")
    save(fig, out, "fig7_human_heatmap.png")


def write_table(runs, groups, metrics, out):
    keys = ["score", "serves_per_min", "expired", "order_time", "dwell_mean", "late_share",
            "h_mae", "h_bias", "robot_wait_s", "human_still_s", "human_distance_px",
            "anticipating_share"]
    path = os.path.join(out, "summary_by_condition.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "games", "participants"] + [f"{k}_{s}" for k in keys for s in ("mean", "sd")])
        for g in groups:
            sel = [metrics[id(r)] for r in runs if r.group == g]
            row = [g, len(sel), len({r.participant for r in runs if r.group == g})]
            for k in keys:
                vals = [m[k] for m in sel if not math.isnan(m[k])]
                row += [round(float(np.mean(vals)), 3) if vals else "",
                        round(float(np.std(vals, ddof=1)), 3) if len(vals) > 1 else ""]
            w.writerow(row)
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--out", default="figures")
    ap.add_argument("--group", choices=["robot", "condition"], default="robot")
    ap.add_argument("--include-aborted", action="store_true", help="also use games that did not finish")
    ap.add_argument("--include-participant", action="append", default=[],
                    help="participant ids to keep that are hidden by default (dev)")
    args = ap.parse_args()
    runs = load_runs(args.logs, args.group, args.include_aborted, args.include_participant)
    if not runs:
        print("No finished games found in", args.logs, "(use --include-aborted for partial games).")
        return
    os.makedirs(args.out, exist_ok=True)
    groups = ordered_groups(runs)
    metrics = {id(r): run_metrics(r) for r in runs}
    print(f"{len(runs)} games, groups: {', '.join(groups)}")
    fig_outcomes(runs, groups, metrics, args.out)
    fig_handoff(runs, groups, metrics, args.out)
    fig_h_accuracy(runs, args.out)
    fig_pace(runs, args.out)
    fig_timeline(runs, groups, args.out)
    fig_behaviour(runs, groups, metrics, args.out)
    fig_heatmap(runs, groups, args.out)
    write_table(runs, groups, metrics, args.out)


if __name__ == "__main__":
    main()
