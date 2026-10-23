"""Record the demo GIF: both cameras side by side while Inspector (already running with the pack) looks after the farm.

    python tools/record_gif.py [--out docs/demo.gif]

Nothing here acts on the equipment: it only sets the scene (a heat wave, a dry bed, a fox, dusk) the way the demo
buttons do. What Inspector does is read from the simulator's switches changing: the vents, a sprinkler, the alarm,
the door."""
import argparse
import io
import json
import os
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

SIM = "http://127.0.0.1:8810"
CW, CH = 400, 225                            # each camera in the GIF


def get(path):
    with urllib.request.urlopen(SIM + path, timeout=10) as r:
        return r.read()


def cmd(command, value=None):
    body = json.dumps({"command": command, "value": value}).encode()
    urllib.request.urlopen(urllib.request.Request(SIM + "/api/command", data=body, method="POST",
                                                  headers={"Content-Type": "application/json"}), timeout=10).read()


def font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def shot(top, bottom):
    img = Image.new("RGB", (CW * 2, CH + 70), (0, 0, 0))
    for k, cam in enumerate(("greenhouse", "coop")):
        img.paste(Image.open(io.BytesIO(get(f"/{cam}/snapshot.jpg"))).convert("RGB").resize((CW, CH)), (k * CW, 0))
    d = ImageDraw.Draw(img)
    d.text((16, CH + 8), top, font=font(22), fill=(255, 255, 255))
    if bottom:
        d.text((16, CH + 38), bottom, font=font(20), fill=(255, 205, 70))
    return img


# (what to set, the caption, Inspector has done it when, what it did, how many pictures to keep after)
SCENES = [
    (lambda: cmd("heat"), "A heat wave: the greenhouse heats up", lambda s: s["vents"],
     "Inspector: too hot -> roof vents open", 5),
    (lambda: cmd("dry", 2), "Bed 2 is drying out", lambda s: s["watering"][1],
     "Inspector: bed 2 dry -> water bed 2 only", 6),
    (lambda: cmd("fox"), "A fox at the fence", lambda s: s["alarm"],
     "Inspector: fox -> alarm, it runs off", 6),
    (lambda: (cmd("speed", 2), cmd("dusk")), "Dusk: the hens walk back in", lambda s: not s["door"],
     "Inspector: night and every hen in -> door shut", 6),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "docs", "demo.gif"))
    ap.add_argument("--settle", type=float, default=6, help="seconds to wait first (longer than the rules' cooldowns "
                                                             "when Inspector has just acted)")
    a = ap.parse_args()
    for c in ("restock", "collect", "vents_close", "door_open", "day"):
        cmd(c)
    cmd("speed", 6)
    time.sleep(a.settle)                     # let Inspector see the calm farm first
    frames = [shot("A small farm, two cameras", "")] * 4
    for setup, top, done, said, keep in SCENES:
        setup()
        t0, quiet = time.time(), 0
        while time.time() - t0 < 180:
            s = json.loads(get("/api/state"))
            if done(s):
                break
            quiet += 1
            if quiet <= 6 or quiet % 4 == 0:    # a long wait goes by fast
                frames.append(shot(top, ""))
            time.sleep(0.6)
        for _ in range(keep):
            frames.append(shot(top, said))
            time.sleep(0.6)
    cmd("speed", 6)
    cmd("day")
    frames += [frames[-1]] * 5
    pal = [f.quantize(colors=112, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pal[0].save(a.out, save_all=True, append_images=pal[1:], duration=300, loop=0, optimize=True)
    print(f"{len(pal)} frames -> {a.out} ({os.path.getsize(a.out) // 1024} KB)")


if __name__ == "__main__":
    main()
