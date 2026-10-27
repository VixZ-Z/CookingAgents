"""Compare robot variants over many random seeds.

    python compare.py

(a) rules on raw observations, no belief
(b) static HMM + QMDP (transition matrix never updated)
(c) adaptive HMM + QMDP (the full robot)
(d) adaptive HMM + QMDP without the safety rule
"""
import numpy as np

import config as C
from main import run_episode

N_SEEDS = 100
VARIANTS = {
    "(a) observation rules": {"adaptive": False, "use_belief": False},
    "(b) static HMM": {"adaptive": False},
    "(c) adaptive HMM": {"adaptive": True},
    "(d) (c) w/o safety": {"adaptive": True, "safety": False},
}
BELIEF_KEYS = ["belief_cooking", "belief_needshelp", "belief_resting"]


def metrics(rows: list, use_belief: bool) -> dict:
    """Per-episode metrics (see the printed legend)."""
    late = [r for r in rows if r["step"] >= C.ROUTINE_CHANGE_STEP]
    hits = [np.argmax([r[k] for k in BELIEF_KEYS]) == r["true_idx"]
            for r in late]
    needs = [r["true_idx"] == C.NEEDS_HELP for r in rows]
    onsets = sum(n and (i == 0 or not needs[i - 1])
                 for i, n in enumerate(needs))
    new = [r for r in rows if not r["continuing"]]
    intrusive = sum(
        (r["action_idx"] in (C.ASK, C.FETCH) and r["true_idx"] != C.NEEDS_HELP)
        or (r["action_idx"] == C.CHOP and r["true_idx"] == C.COOKING)
        for r in new)
    return {
        "reward": sum(r["reward"] for r in rows),
        "accuracy": np.mean(hits) if use_belief else np.nan,
        "latency": sum(needs) / max(onsets, 1),
        "intrusions": intrusive,
        "unsafe": sum(r["unsafe_fetch"] for r in rows),
    }


def main() -> None:
    cols = ["reward", "accuracy", "latency", "intrusions", "unsafe"]
    print(f"{'variant':<24}" + "".join(f"{c:>11}" for c in cols))
    for name, kwargs in VARIANTS.items():
        use_belief = kwargs.get("use_belief", True)
        results = [metrics(run_episode(seed, **kwargs), use_belief)
                   for seed in range(N_SEEDS)]
        means = [np.mean([m[c] for m in results]) for c in cols]
        print(f"{name:<24}" + "".join(
            f"{'-':>11}" if np.isnan(v) else f"{v:>11.2f}" for v in means))
    print(f"\nMeans over {N_SEEDS} seeds.\n"
          "reward     total reward per episode (higher is better)\n"
          "accuracy   belief argmax == true state, after the routine change\n"
          "latency    steps spent in NeedsHelp per need episode (lower "
          "is better)\n"
          "intrusions Ask/Fetch when no help was needed, or Chop while\n"
          "           the person was still cooking\n"
          "unsafe     autonomous Fetch next to a hot pot")


if __name__ == "__main__":
    main()
