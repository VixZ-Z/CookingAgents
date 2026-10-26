from pathlib import Path
import uuid, csv
import config as C
from game import GameState
from main import get_robot_class
from menu import RECIPES
from logger import RunRecorder
from navigation import Navigator, approach_point
root=Path('.test-tmp') / ('adaptive-validation-' + uuid.uuid4().hex[:8])
root.mkdir()
for layout in ('divided',):
    robots=['reactive','anticipatory','adaptive_anticipatory'] + (['anticipatory_fixed_h','anticipatory_dynamic_h'] if layout=='divided' else [])
    for robot in robots:
        for key, recipe in RECIPES.items():
            state=GameState(get_robot_class(robot),seed=42,layout=layout,recipe=key)
            rec=RunRecorder(dict(participant='synthetic',robot=robot,condition=robot,recipe=key,seed=42),str(root/'logs'))
            rec.start(state)
            nav=Navigator()
            def step(destination=None, use=False):
                rec.before(state)
                arrived=nav.move_to(state.player,destination,state,1/30) if destination else False
                if use: state.player_interact()
                state.update(1/30,(0,0),False)
                rec.after(state,1/30)
                return arrived
            def visit(st, dest):
                for _ in range(600):
                    if step(dest): break
                else: raise AssertionError((robot,key,st.label))
                step(use=True)
            for name, counter in zip(recipe.ingredients,[s for s in state.stations if s.owner=='shared']):
                crate=next(s for s in state.stations if s.kind=='crate_'+name)
                visit(crate,approach_point(crate))
                assert state.player.carrying==name
                visit(counter,(counter.rect.left-state.player.rect.width/2-2,counter.rect.centery))
                assert state.player.carrying is None
            for _ in range(1800):
                step()
                if state.score: break
            assert state.score,(layout,robot,key,state.robot.status)
            rec.finish(state,False)
            with open(rec.path,encoding='utf-8') as stream:
                assert any(r['action']=='serve' and r['item']==key for r in csv.DictReader(stream))
print(root)
(root/'validated.txt').write_text('30 synthetic runs: all recipes served with logged human handoffs; aborted after first serve.\n')
