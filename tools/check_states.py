"""Every combination the farm can show, several moments each: does every state of the pack answer what the simulator
knows - and say "other camera" (hidden) on the other camera's picture?   python tools/check_states.py
(run tools/teach_refs.py first: the vents, the door and the thermometer need their references)"""
import itertools
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(0, os.environ.get("INSPECTOR_DIR", r"D:\code\inspector_platform"))
import numpy as np  # noqa: E402

import farm as F  # noqa: E402
from labeler import generic  # noqa: E402

REFS = os.path.join(HERE, "..", "pack", "refs")
schema = json.load(open(os.path.join(HERE, "..", "pack", "states.json"), encoding="utf-8"))
engine = generic.Engine(schema, REFS)
GREENHOUSE = ["temperature", "vents", "bed1_dry", "bed2_dry", "bed3_dry"]
COOP = ["daylight", "door", "hens_out", "eggs", "fox"]
clock = [1000.0]
F.time = types.SimpleNamespace(time=lambda: clock[0])         # the simulator's clock only
total = bad = 0


def check(img, want, what):
    global total, bad
    values, scores, _flags = engine.label(img, {})
    for sid, w in want.items():
        total += 1
        ok = values[sid] in w if isinstance(w, tuple) else values[sid] == w
        if not ok:
            bad += 1
            print("WRONG", sid, "want", w, "got", values[sid], scores[sid], what)


n = 0
for hour, vents, temp, moist, water in itertools.product((10.0, 14.0, 18.2, 22.0), (False, True), (4, 17, 29, 38, 45),
                                                        ((10, 45, 95), (20, 70, 15), (60, 22, 40), (90, 90, 12)),
                                                        (None, 0, 2)):
    n += 1
    f = F.Farm(seed=n)
    clock[0] = 1000 + n * 0.37
    f.hour, f.vents, f.temp, f.moist = hour, vents, float(temp), [float(m) for m in moist]
    if water is not None:
        f.watering[water] = clock[0] + 5
    want = {"view_greenhouse": "yes", "view_coop": "hidden", "temperature": temp, "vents": "open" if vents else "closed",
            **{c: "hidden" for c in COOP}}
    for i, m in enumerate(moist):
        want[f"bed{i + 1}_dry"] = "dry" if m < 26 and water != i else ("ok" if m > 34 else ("dry", "ok", None))
    check(np.asarray(f.draw("greenhouse")), want, dict(hour=hour, vents=vents, temp=temp, moist=moist, water=water))

for hour, door, out, eggs, fox, alarm in itertools.product((7.0, 10.0, 15.0, 18.2, 22.0, 3.0), (True, False), (0, 1, 3, 8),
                                                          (0, 2, 3, 4, 5, 9, 12), (False, True), (False, True)):
    n += 1
    f = F.Farm(seed=n)
    clock[0] = 1000 + n * 0.37
    f.hour, f.door, f.eggs = hour, door, eggs
    for k, h in enumerate(f.hens):
        h["out"] = k < out
        if k == 0 and out:
            h["x"], h["y"] = (500, 545) if n % 3 == 0 else (h["x"], h["y"])      # sometimes waiting at the door
    if fox:
        f.come_fox(called=True)
    if alarm:
        f.alarm_until = clock[0] + 4
    want = {"view_greenhouse": "hidden", "view_coop": "yes", "door": "open" if door else "closed",
            "hens_out": "yes" if out else "no", "eggs": "many" if eggs >= 4 else "few",
            "fox": "yes" if fox else "no", "temperature": None, **{s: "hidden" for s in GREENHOUSE if s != "temperature"}}
    want["daylight"] = "day" if 9 <= hour <= 16 else ("night" if hour >= 19 or hour < 5 else ("day", "night", None))
    check(np.asarray(f.draw("coop")), want, dict(hour=hour, door=door, out=out, eggs=eggs, fox=fox, alarm=alarm))
print(f"{n} pictures, checked {total}, wrong {bad}")
