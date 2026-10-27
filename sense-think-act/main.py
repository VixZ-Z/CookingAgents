"""Run one episode of the sense-think-act loop, log it and print a trace.

    python main.py        # 60 steps -> console trace + log.csv
"""
import csv

import config as C
from environment import Environment
from human import Human, Observation
from robot import Robot

LOG_FILE = "log.csv"


def run_episode(seed: int = C.SEED, adaptive: bool = True,
                use_belief: bool = True,
                safety: bool = C.SAFETY_RULE) -> list:
    """Simulate N_STEPS time-steps; return one log row (dict) per step."""
    human = Human(seed)
    env = Environment(human)
    robot = Robot(adaptive, use_belief, safety)
    rows = []
    for step in range(C.N_STEPS):
        human.step()                         # the hidden world moves on
        obs = human.observe()                # SENSE: noisy person signals
        context = env.sense(obs)             # SENSE: pot, board, own task
        action = robot.think(obs, context)   # THINK: HMM belief -> QMDP
        reward = env.apply(action)           # ACT: move, ask, fetch, chop
        rows.append(log_row(step, human, env, robot, obs, context,
                            action, reward))
    return rows


def log_row(step, human, env, robot, obs, context, action, reward) -> dict:
    """Everything that happened in one step, for the CSV and the plots."""
    return {
        "step": step,
        "true_state": C.STATES[human.state],
        "fatigue": round(human.fatigue, 2),
        "observation": describe(obs),
        "belief_cooking": round(float(robot.belief[C.COOKING]), 3),
        "belief_needshelp": round(float(robot.belief[C.NEEDS_HELP]), 3),
        "belief_resting": round(float(robot.belief[C.RESTING]), 3),
        "action": C.ACTIONS[action],
        "continuing": int(context["task_left"] > 0),
        "confirmed": int(context["confirmed"]),
        "safety_fired": int(robot.safety_fired),
        "unsafe_fetch": int(env.unsafe),
        "reward": round(reward, 2),
        "pot_on": int(human.pot_on),
        "food_on_board": int(human.food_on_board),
        # used by the plots / compare.py only, not written to the CSV
        "true_idx": human.state,
        "action_idx": action,
        "task_left": env.task_left,
        "human_cell": human.cell,
        "robot_cell": env.robot_cell,
    }


def describe(obs: Observation) -> str:
    if obs is None:
        return "dropout"
    return (f"zone={C.ZONES[obs['zone']]} gesture={obs['gesture']} "
            f"idle={obs['idle']} verbal={obs['verbal']}")


CSV_FIELDS = ["step", "true_state", "fatigue", "observation",
              "belief_cooking", "belief_needshelp", "belief_resting",
              "action", "continuing", "confirmed", "safety_fired",
              "unsafe_fetch", "reward", "pot_on", "food_on_board"]


def write_log(rows: list, path: str = LOG_FILE) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = run_episode()
    write_log(rows)
    print(f"{'step':>4} {'true state':<10} {'belief C / H / R':<17} "
          f"{'action':<14} {'reward':>6}  notes")
    for r in rows:
        belief = (f"{r['belief_cooking']:.2f} {r['belief_needshelp']:.2f} "
                  f"{r['belief_resting']:.2f}")
        notes = [text for key, text in (
            ("continuing", "(continuing)"), ("safety_fired", "SAFETY->Ask"),
            ("pot_on", "pot on"), ("food_on_board", "food on board"))
            if r[key]]
        print(f"{r['step']:>4} {r['true_state']:<10} {belief:<17} "
              f"{r['action']:<14} {r['reward']:>6.1f}  {', '.join(notes)}")
        if r["step"] == C.ROUTINE_CHANGE_STEP - 1:
            print("---- routine change: the person now tires faster ----")
    total = sum(r["reward"] for r in rows)
    fired = sum(r["safety_fired"] for r in rows)
    print(f"\nTotal reward {total:.1f} | safety rule fired {fired}x | "
          f"log written to {LOG_FILE}")


if __name__ == "__main__":
    main()
