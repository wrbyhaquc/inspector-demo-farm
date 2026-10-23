"""Make the pack's reference pictures from the simulator's own drawing, the way one would teach them on the state page:
the roof vents and the hen house door open / closed (by day, at dusk and by night), and every digit of the
thermometer.

    python tools/teach_refs.py        -> pack/refs/meta/rule_templates/<state>/  (build.py copies them into the design)"""
import json
import os
import shutil
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(0, os.environ.get("INSPECTOR_DIR", r"D:\code\inspector_platform"))
import numpy as np  # noqa: E402

import farm as F  # noqa: E402
from labeler import generic  # noqa: E402

OUT = os.path.join(HERE, "..", "pack", "refs")
STATES = {s["id"]: s for s in json.load(open(os.path.join(HERE, "..", "pack", "states.json"), encoding="utf-8"))["states"]}
clock = [1000.0]
F.time = types.SimpleNamespace(time=lambda: clock[0])         # the simulator's clock only


def frame(hour, **set_):
    f = F.Farm(seed=3)
    f.hour = hour
    for k, v in set_.items():
        setattr(f, k, v)
    return f


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    n = 0
    for sid, attr, cam in (("vents", "vents", "greenhouse"), ("door", "door", "coop")):
        box = generic._box(STATES[sid], STATES[sid]["source"]["params"]["roi"])
        for hour in (10.0, 18.2, 22.0):
            for is_open in (True, False):
                f = frame(hour, **{attr: is_open})
                for h in f.hens:
                    h["out"] = False                  # nobody in front of the door
                img = np.asarray(f.draw(cam))
                time.sleep(0.002)                     # the platform names a reference by the millisecond
                generic.tpl_add(OUT, sid, "open" if is_open else "closed", img, box, f"sim:{cam}:{hour}:{attr}={is_open}")
                n += 1
    st = STATES["temperature"]
    box = generic._box(st, st["source"]["params"]["roi"])
    seen = {}
    for temp in (10, 23, 45, 67, 89, 31, 52, 74, 96, 18, 30):
        img = np.asarray(frame(10.0, temp=temp).draw("greenhouse"))
        text = str(temp)
        gs = generic.glyphs(img, box, st["source"]["params"]["colors"])
        assert len(gs) == len(text), (temp, len(gs))
        for (b, _m), ch in zip(gs, text):
            if seen.get(ch, 0) < 2:                   # two examples of each character
                time.sleep(0.002)
                generic.glyph_add(OUT, "temperature", ch, img, b, f"sim:greenhouse:{temp}")
                seen[ch] = seen.get(ch, 0) + 1
                n += 1
    print(f"{n} references -> {os.path.abspath(OUT)}  characters: {''.join(sorted(seen))}")


if __name__ == "__main__":
    main()
