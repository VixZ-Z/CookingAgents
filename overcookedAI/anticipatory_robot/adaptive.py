"""Session-local collaboration preferences learned only from visible handoffs."""
from menu import RECIPES, prepared
from .robot import AnticipatoryRobot


class CollaborationPreferences:
    """Episode-level, session-local handoff preferences from observable actions.

    Placing bread is *provisional*: it counts as an ingredient collaboration
    only if the robot actually collects it. If the human later assembles a
    sandwich and hands it over, the episode contributes one `complete` sample.
    """
    styles = ("individual", "partial", "complete")

    def __init__(self):
        self.counts = {}
        self.cursor = 0
        self.revision = 0
        self.pending = {}  # station index -> (recipe, item, style)
        self.episodes = []  # lightweight diagnostics; not performance metrics
        self.complete_handoff_stations = {}  # recipe -> most recently observed shared counter

    def probabilities(self, recipe):
        counts = self.counts.get(recipe, [0., 0., 0.])
        total = sum(counts) + 3
        return {style: (count + 1) / total for style, count in zip(self.styles, counts)}

    def preferred(self, recipe):
        return max(self.probabilities(recipe), key=self.probabilities(recipe).get)

    def _record(self, recipe, style, station_index):
        row = self.counts.setdefault(recipe, [0., 0., 0.])
        row[:] = [value * .75 for value in row]
        row[self.styles.index(style)] += 1
        self.revision += 1
        self.episodes.append(dict(recipe=recipe, style=style, station=station_index))
        if style == "complete":
            self.complete_handoff_stations[recipe] = station_index

    def _recipe_for(self, state, event, item):
        # An event's explicit recipe context is stronger than a priority-order
        # guess, but still require that the ingredient belongs to that recipe.
        key = event.recipe
        if key in RECIPES and any(item in (n, prepared(n)) for n in RECIPES[key].ingredients):
            return key
        keys = {o.kind for o in state.orders if o.kind in RECIPES and
                any(item in (n, prepared(n)) for n in RECIPES[o.kind].ingredients)}
        return next(iter(keys)) if len(keys) == 1 else None

    def update(self, state):
        events = state.human_actions[self.cursor:]
        touched = set()
        for event in events:
            index = event.station_index
            station = state.stations[index]
            item = event.symbol.item
            action = event.symbol.action
            if station.owner != "shared":
                continue
            touched.add(index)
            if action == "combine":
                # The human is still working at this station: this does not
                # constitute an ingredient handoff to the robot.
                self.pending.pop(index, None)
            elif action == "take":
                # Human retrieved the ingredient rather than delivering it.
                self.pending.pop(index, None)
            elif action == "put" and item in RECIPES:
                self.pending.pop(index, None)
                self._record(item, "complete", index)
            elif action == "put":
                key = self._recipe_for(state, event, item)
                if key is not None:
                    style = "partial" if item.startswith("chopped_") else "individual"
                    self.pending[index] = (key, item, style)
                else:
                    self.pending.pop(index, None)
        self.cursor = len(state.human_actions)

        # Confirm an ingredient handoff only after the robot has actually
        # collected the staged ingredient. Merely setting it down is not proof.
        robot = getattr(state, "robot", None)
        for index, (recipe, item, style) in list(self.pending.items()):
            if index in touched:
                continue  # allow a full frame for the human's follow-up action
            station = state.stations[index]
            if station.held == item:
                continue
            if robot is not None and robot.carrying == item:
                self._record(recipe, style, index)
            # Other removals are ambiguous; do not train on them.
            self.pending.pop(index, None)

    def snapshot(self):
        return {key: self.probabilities(key) for key in self.counts}


class AdaptiveAnticipatoryRobot(AnticipatoryRobot):
    def __init__(self, state):
        super().__init__(state)
        self.preferences = CollaborationPreferences()

    def update_ai(self, dt, state):
        self.preferences.update(state)
        super().update_ai(dt, state)
