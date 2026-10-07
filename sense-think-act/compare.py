"""Compare three robots over many seeds.

    python compare.py

(a) observation-only rule, (b) static HMM + QMDP, (c) adaptive HMM + QMDP.
Belief accuracy is always measured on the HMM belief (the rule ignores it).
"""
import numpy as np

import config as C
from main import run_episode

N_SEEDS = 100
VARIANTS = {
    "(a) obs-only rule": {"adaptive": False, "use_belief": False},
    "(b) static HMM+QMDP": {"adaptive": False, "use_belief": True},
    "(c) adaptive HMM+QMDP": {"adaptive": True, "use_belief": True},
}


def metrics(rows: list) -> dict:
    """Per-episode metrics."""
    belief_keys = ["belief_cooking", "belief_needshelp", "belief_resting"]
    hits = [int(np.argmax([r[k] for k in belief_keys]) == r["true_idx"])
            for r in rows]
    needs = [r["true_idx"] == C.NEEDS_HELP for r in rows]
    onsets = sum(1 for i, n in enumerate(needs)
                 if n and (i == 0 or not needs[i - 1]))
    acted = [r["action_idx"] in (C.ASK, C.FETCH) for r in rows]
    return {
        "accuracy": float(np.mean(hits)),
        # mean number of steps spent in NeedsHelp per episode of need
        "latency": sum(needs) / onsets if onsets else np.nan,
        "intrusions": sum(a and not n for a, n in zip(acted, needs)),
        "asks": sum(r["action_idx"] == C.ASK for r in rows),
    }


def main() -> None:
    print(f"{'variant':<24} {'accuracy':>8} {'latency':>8} "
          f"{'intrusions':>10} {'asks':>6}")
    for name, kwargs in VARIANTS.items():
        results = [metrics(run_episode(seed, **kwargs))
                   for seed in range(N_SEEDS)]
        mean = {k: np.nanmean([m[k] for m in results]) for k in results[0]}
        print(f"{name:<24} {mean['accuracy']:>8.2f} {mean['latency']:>8.2f}"
              f" {mean['intrusions']:>10.2f} {mean['asks']:>6.2f}")
    print(f"(means over {N_SEEDS} seeds; latency = steps in NeedsHelp "
          "per need episode, lower is better)")


if __name__ == "__main__":
    main()
