"""Run one simulation, write log.csv and print a console trace.

    python main.py
"""
import csv

import config as C
from environment import Environment
from hmm import HMM
from human import Human
from policy import Policy
from robot import Robot

LOG_FILE = "log.csv"
FIELDS = ["step", "true_state", "observation", "belief_cooking",
          "belief_needshelp", "belief_resting", "action", "reward",
          "safety_fired"]


def describe(obs) -> str:
    """Readable text for an observation."""
    if obs is None:
        return "dropout"
    return (f"zone={C.ZONES[obs['zone']]} gesture={obs['gesture']} "
            f"idle={obs['idle']} verbal={obs['verbal']}")


def run_episode(seed: int = C.SEED, adaptive: bool = True,
                use_belief: bool = True) -> list:
    """Run N_STEPS of sense-think-act; return one dict per step."""
    human = Human(seed)
    env = Environment(human)
    robot = Robot(env, HMM(adaptive), Policy(), use_belief)
    rows = []
    for step in range(C.N_STEPS):
        state, obs = human.step()                       # SENSE (simulated)
        human_cell = human.cell
        belief, action, reward, fired = robot.step(obs)  # THINK + ACT
        rows.append({
            "step": step,
            "true_state": C.STATES[state],
            "observation": describe(obs),
            "belief_cooking": round(float(belief[0]), 3),
            "belief_needshelp": round(float(belief[1]), 3),
            "belief_resting": round(float(belief[2]), 3),
            "action": C.ACTIONS[action],
            "reward": round(reward, 2),
            "safety_fired": int(fired),
            # extras for visualize.py / compare.py (not written to the CSV)
            "true_idx": state,
            "action_idx": action,
            "fatigue": round(human.fatigue, 2),
            "human_cell": human_cell,
            "robot_cell": env.robot_cell,
        })
    return rows


def write_log(rows: list, path: str = LOG_FILE) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = run_episode()
    write_log(rows)
    print(f"{'step':>4} {'true':<10} {'belief (C, H, R)':<20} "
          f"{'action':<14} {'reward':>6}  safety")
    for r in rows:
        belief = (f"{r['belief_cooking']:.2f} {r['belief_needshelp']:.2f} "
                  f"{r['belief_resting']:.2f}")
        mark = "FIRED" if r["safety_fired"] else ""
        print(f"{r['step']:>4} {r['true_state']:<10} {belief:<20} "
              f"{r['action']:<14} {r['reward']:>6.1f}  {mark}")
        if r["step"] == C.ROUTINE_CHANGE_STEP - 1:
            print("---- routine change: person now tires faster ----")
    total = sum(r["reward"] for r in rows)
    fired = sum(r["safety_fired"] for r in rows)
    print(f"\nTotal reward: {total:.1f} | safety rule fired {fired}x | "
          f"log written to {LOG_FILE}")


if __name__ == "__main__":
    main()
