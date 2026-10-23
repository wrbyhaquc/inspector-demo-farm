"""A small farm, simulated and drawn as two cartoon camera pictures - stand-ins for real farm cameras, so Inspector can
be tried without a farm.

What happens on it (time runs faster than real time, one day in a few minutes):

  the greenhouse (CAM-02)
  - the sun heats it: with the roof vents closed it gets much hotter than outside; the thermometer on the wall
    shows the temperature in red digits (whole degrees).
  - each of the three beds dries out at its own pace (faster when it is hot). Dry soil turns pale, and the plants
    turn yellow and then brown. A bed's sprinkler waters only that bed.

  the hen house (CAM-03)
  - at dawn the hens go out into the run if the door is open; at dusk they walk back in by themselves.
  - each hen lays an egg in the nest boxes in the morning; the eggs wait there until someone collects them.
  - at night a fox may come to the fence. It takes a hen that is still outside, or one from the house if the door
    was left open, unless the alarm (siren and strobe) scares it off.

Nothing in the pictures is read from this model by Inspector: it only sees the pictures, like real cameras, and acts
through the commands (vents, sprinklers, door, alarm) - the way it would drive real equipment."""
import math
import random
import threading
import time

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BEDS = [(150, 300, 440, 660), (495, 300, 785, 660), (840, 300, 1130, 660)]     # the greenhouse beds' soil, x0 y0 x1 y1
VENTS = [(150, 150, 560, 215), (720, 150, 1130, 215)]                          # roof vents (the frames)
THERMO = (515, 20, 765, 100)                                                    # the wall display
DOOR = (300, 395, 400, 555)                                                     # the hen house door
NEST = (95, 330, 280, 400)                                                      # the nest boxes' open front
RUN = (500, 300, 1130, 680)                                                     # the run, inside the fence
FOX_SPOTS = [(1205, 470), (1215, 560), (1200, 380)]                             # outside the fence, on the right
HENS = 8
TAG = {"greenhouse": (40, 200, 90), "coop": (200, 60, 200)}                     # the cameras' name tags (on screen)


def _font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT = _font(22)
FONT_S = _font(16)
FONT_D = _font(52)


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Farm:
    def __init__(self, seed=None, day_minutes=6.0):
        self.rng = random.Random(seed)
        self.lock = threading.Lock()
        self.day_minutes = day_minutes
        self.hour = 9.0
        self.day = 1
        # greenhouse
        self.temp = 22.0
        self.vents = False
        self.heat = 0.0                          # simulated hours of a heat wave left (demo)
        self.moist = [75.0, 60.0, 85.0]
        self.dry_rate = [1.0, 1.35, 0.8]
        self.watering = [0.0, 0.0, 0.0]          # real time each bed's sprinkler runs until
        # hen house
        self.door = True
        self.alarm_until = 0.0
        self.eggs = 0
        self.hens = [self._new_hen(i) for i in range(HENS)]
        self.fox = None                          # {"x", "y", "stay", "meal", "leaving"}
        self.lost = 0
        self.log = []
        self._last = time.time()

    def _new_hen(self, i):
        r = self.rng
        return {"out": True, "x": r.uniform(560, 1080), "y": r.uniform(360, 640), "tx": None, "ty": None,
                "go_out": r.uniform(6.3, 7.8), "go_in": r.uniform(17.6, 18.6), "lay": r.uniform(7.0, 11.5),
                "laid": 0, "phase": r.uniform(0, 6.28), "speed": r.uniform(70, 110)}

    def note(self, text):
        self.log.append((time.time(), text))
        self.log = self.log[-30:]

    def daylight(self):
        return max(0.0, math.sin((self.hour - 6) / 12 * math.pi)) if 6 <= self.hour <= 18 else 0.0

    def is_night(self):
        return self.hour < 6 or self.hour >= 18.5

    # ---------------- the model ----------------
    def step(self):
        now = time.time()
        dt = min(1.0, now - self._last)
        self._last = now
        hours = dt / (self.day_minutes * 60) * 24
        with self.lock:
            self.hour += hours
            if self.hour >= 24:
                self.hour -= 24
                self.day += 1
            sun = self.daylight()
            self._greenhouse(sun, hours, dt, now)
            self._coop(sun, hours, dt, now)

    def _greenhouse(self, sun, hours, dt, now):
        outside = 11 + 13 * sun + (8 if self.heat > 0 else 0)
        target = outside + (4 if self.vents else 17) * sun
        self.temp += (target - self.temp) * min(1.0, 1.4 * hours)
        self.heat = max(0.0, self.heat - hours)
        for i in range(3):
            if now < self.watering[i]:
                self.moist[i] = min(100.0, self.moist[i] + 7.0 * dt)
            else:
                self.moist[i] = max(0.0, self.moist[i] - (0.9 + 0.09 * max(0.0, self.temp - 18)) * self.dry_rate[i] * hours)

    def _coop(self, sun, hours, dt, now):
        dx0, dy0, dx1, dy1 = DOOR
        door_x, door_y = (dx0 + dx1) / 2 + 150, dy1 - 10          # just outside the door, in the run
        for h in self.hens:
            if h["laid"] != self.day and self.hour >= h["lay"] and self.hour < 14:
                h["laid"] = self.day
                self.eggs = min(12, self.eggs + 1)
            want_out = h["go_out"] <= self.hour < h["go_in"]
            if h["out"] and not want_out:
                if self.door and math.hypot(h["x"] - door_x, h["y"] - door_y) < 20:
                    h["out"] = False                               # in through the open door
                    h["tx"] = None
                    continue
                h["tx"], h["ty"] = door_x, door_y                 # to the door (and wait there if it is shut)
            elif not h["out"] and want_out and self.door:
                h["out"] = True
                h["x"], h["y"] = door_x, door_y
                h["tx"] = None
            if not h["out"]:
                continue
            if h["tx"] is None or math.hypot(h["x"] - h["tx"], h["y"] - h["ty"]) < 6:
                if want_out:                                      # peck about the run
                    h["tx"], h["ty"] = self.rng.uniform(560, 1080), self.rng.uniform(340, 650)
            if h["tx"] is not None:
                d = math.hypot(h["tx"] - h["x"], h["ty"] - h["y"])
                if d > 1:
                    s = min(d, h["speed"] * dt * (1.0 if want_out else 1.6))
                    h["x"] += (h["tx"] - h["x"]) / d * s
                    h["y"] += (h["ty"] - h["y"]) / d * s
            h["phase"] += dt * 5
        # the fox
        alarm = now < self.alarm_until
        if self.fox is None:
            if self.is_night() and not alarm and self.rng.random() < 0.25 * hours:
                self.come_fox()
        else:
            f = self.fox
            if f["leaving"] is not None:
                if now - f["leaving"] > 3:
                    self.fox = None
            elif alarm:
                f["leaving"] = now
                self.note("the fox ran off")
            else:
                f["stay"] -= hours
                f["meal"] += hours
                outside = [h for h in self.hens if h["out"]]
                if f["meal"] > 0.8 and (outside or self.door) and len(self.hens) > 2:
                    self.hens.remove(outside[0] if outside else self.hens[-1])
                    self.lost += 1
                    f["meal"] = 0.0
                    self.note("the fox took a hen" + ("" if outside else " through the open door"))
                if f["stay"] <= 0 or not (self.is_night() or f["called"]):
                    f["leaving"] = now
                    self.note("the fox went away")

    def come_fox(self, called=False):
        x, y = self.rng.choice(FOX_SPOTS)
        self.fox = {"x": x, "y": y, "stay": self.rng.uniform(1.5, 3.0), "meal": 0.0, "leaving": None, "called": called}
        self.note("a fox came to the fence")

    def command(self, cmd, value=None):
        """Equipment: vents_open / vents_close, water (value = bed 1-3; or water_1 .. water_3), door_open / door_close,
        alarm. Demo: night / day / dusk / heat / dry (value = bed) / fox / eggs (value = how many) / collect /
        restock / speed (value = real minutes per day); test: does nothing."""
        cmd = (cmd or "").strip().lower()
        with self.lock:
            if cmd in ("vents_open", "vents_close"):
                self.vents = cmd.endswith("open")
            elif cmd in ("water", "water_1", "water_2", "water_3"):
                bed = int(value if cmd == "water" else cmd[-1])
                if not 1 <= bed <= 3:
                    raise ValueError("bed must be 1, 2 or 3")
                self.watering[bed - 1] = time.time() + 10
            elif cmd in ("door_open", "door_close"):
                self.door = cmd.endswith("open")
            elif cmd == "alarm":
                self.alarm_until = time.time() + 8
            elif cmd == "night":
                self.hour = 21.0
            elif cmd == "day":
                self.hour = 9.0
            elif cmd == "dusk":
                self.hour = 17.5
            elif cmd == "heat":
                self.heat = 4.0
                self.hour = max(self.hour, 11.0) if self.hour < 15 else self.hour
            elif cmd == "dry":
                bed = int(value or 2)
                self.moist[bed - 1] = min(self.moist[bed - 1], 22.0)
            elif cmd == "fox":
                if self.fox is None:
                    self.come_fox(called=True)          # the demo's fox stays by day too
            elif cmd == "eggs":
                self.eggs = max(0, min(12, int(value if value is not None else 6)))
            elif cmd == "collect":
                self.eggs = 0
            elif cmd == "restock":
                while len(self.hens) < HENS:
                    self.hens.append(self._new_hen(len(self.hens)))
                for h in self.hens:
                    h["out"] = self.door and h["go_out"] <= self.hour < h["go_in"]
                self.moist = [75.0, 60.0, 85.0]
                self.lost = 0
            elif cmd == "speed":
                self.day_minutes = max(0.5, min(240.0, float(value)))
            elif cmd == "test":
                pass
            else:
                raise ValueError(f"unknown command: {cmd}")
            if cmd != "speed":
                self.note(f"command: {cmd}" + ("" if value is None else f" {value}"))

    def state(self):
        with self.lock:
            now = time.time()
            return {"day": self.day, "hour": round(self.hour, 2), "night": self.is_night(), "day_minutes": self.day_minutes,
                    "temp": round(self.temp, 1), "vents": self.vents, "moisture": [round(m) for m in self.moist],
                    "dry": [m < 30 for m in self.moist], "watering": [now < w for w in self.watering],
                    "door": self.door, "hens": len(self.hens), "hens_out": sum(h["out"] for h in self.hens),
                    "eggs": self.eggs, "fox": self.fox is not None and self.fox["leaving"] is None,
                    "alarm": now < self.alarm_until, "lost": self.lost, "log": [t for _, t in self.log[-8:]]}

    # ---------------- the pictures ----------------
    def draw(self, cam):
        with self.lock:
            return self._greenhouse_img() if cam == "greenhouse" else self._coop_img()

    def _sky(self, sun):
        night = self.is_night()
        sky = _mix((25, 30, 70), (130, 195, 245), 0 if night else sun)
        if 5 <= self.hour < 7 or 17.5 <= self.hour < 19:
            sky = _mix(sky, (240, 150, 90), 0.45)
        return sky

    def _overlay(self, d, label, cam, t):
        hh, mm = int(self.hour), int((self.hour % 1) * 60)
        d.rectangle((14, 12, 420, 46), fill=(0, 0, 0, 150))
        d.rectangle((20, 18, 42, 40), fill=TAG[cam])
        d.text((52, 16), f"{label}   {hh:02d}:{mm:02d}", font=FONT, fill=(255, 255, 255))
        if int(t * 2) % 2 == 0:
            d.ellipse((1222, 20, 1240, 38), fill=(230, 40, 40))
        d.text((1180, 18), "REC", font=FONT_S, fill=(255, 255, 255))

    def _greenhouse_img(self):
        t = time.time()
        sun = self.daylight()
        img = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        # the glass roof (the sky through it), the back wall, the floor; grow lights keep the inside evenly lit
        d.rectangle((0, 0, W, 240), fill=_mix(self._sky(sun), (200, 215, 220), 0.25))
        for x in range(0, W, 160):
            d.line((x, 0, x + 40, 240), fill=(235, 238, 240), width=6)
        d.rectangle((0, 238, W, 252), fill=(225, 228, 230))
        d.rectangle((0, 252, W, H), fill=(150, 152, 148))
        for x in range(0, W, 64):
            d.line((x, 252, x - 40, H), fill=(138, 140, 136), width=2)
        # roof vents: a closed one lies flat in the roof; an open one is lifted on its arm, showing a dark gap
        for vx0, vy0, vx1, vy1 in VENTS:
            d.rectangle((vx0, vy0, vx1, vy1), fill=(60, 66, 72))
            if self.vents:
                d.rectangle((vx0 + 6, vy0 + 6, vx1 - 6, vy1 - 6), fill=(28, 34, 40))
                d.polygon([(vx0 + 6, vy0 + 6), (vx1 - 6, vy0 + 6), (vx1 - 26, vy0 - 34), (vx0 + 26, vy0 - 34)],
                          fill=(205, 228, 236))
                for k in range(5):
                    x = vx0 + 40 + k * (vx1 - vx0 - 80) / 4
                    d.line((x, vy0 + 6, x + (8 if k < 2 else -8), vy0 - 34), fill=(240, 244, 246), width=4)
                mx = (vx0 + vx1) / 2
                d.line((mx, vy1 - 6, mx, vy0 - 30), fill=(70, 70, 70), width=6)
            else:
                d.rectangle((vx0 + 6, vy0 + 6, vx1 - 6, vy1 - 6), fill=(205, 228, 236))
                for k in range(5):
                    x = vx0 + 40 + k * (vx1 - vx0 - 80) / 4
                    d.line((x, vy0 + 6, x, vy1 - 6), fill=(240, 244, 246), width=4)
        # the thermometer: red digits on black, the unit in grey
        x0, y0, x1, y1 = THERMO
        d.rounded_rectangle((x0 - 8, y0 - 8, x1 + 8, y1 + 8), 8, fill=(70, 74, 80))
        d.rectangle((x0, y0, x1, y1), fill=(10, 10, 12))
        txt = f"{round(self.temp)}"
        x = x0 + 172
        for ch in reversed(txt):                    # one character at a time, right-aligned, always a gap between
            x -= int(FONT_D.getlength(ch)) + 5
            d.text((x, y0 + 12), ch, font=FONT_D, fill=(255, 55, 40))
        d.text((x0 + 186, y0 + 18), "°C", font=FONT, fill=(150, 150, 150))
        # the beds
        for i, (bx0, by0, bx1, by1) in enumerate(BEDS):
            m = self.moist[i]
            d.rectangle((bx0 - 14, by0 - 14, bx1 + 14, by1 + 14), fill=(120, 78, 48))      # the wooden frame
            d.rectangle((bx0, by0, bx1, by1), fill=_mix((198, 162, 110), (84, 54, 34), m / 70))
            rng = random.Random(i * 11)
            for _ in range(40):                    # clods of earth
                cx, cy = rng.randint(bx0 + 6, bx1 - 6), rng.randint(by0 + 6, by1 - 6)
                d.ellipse((cx - 4, cy - 2, cx + 4, cy + 2), fill=_mix((170, 138, 92), (66, 42, 26), m / 70))
            health = max(0.0, min(1.0, (m - 12) / 28))     # 1 = well watered, 0 = dried up
            leaf = _mix((150, 110, 45), (205, 190, 60), health * 2) if health < 0.5 else _mix((205, 190, 60), (55, 165, 60), health * 2 - 1)
            size = 20 + 10 * health
            for r in range(4):
                for c in range(3):
                    px = bx0 + (c + 0.5) * (bx1 - bx0) / 3
                    py = by0 + (r + 0.5) * (by1 - by0) / 4
                    sway = math.sin(t * 1.5 + r + c) * 2
                    for k in range(6):
                        a = k * math.pi / 3 + r
                        lx, ly = px + math.cos(a) * size * 0.6 + sway, py + math.sin(a) * size * 0.6 * (0.7 if health < 0.3 else 1)
                        d.ellipse((lx - size * 0.45, ly - size * 0.3, lx + size * 0.45, ly + size * 0.3), fill=leaf)
                    d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=_mix(leaf, (30, 90, 30), 0.4))
            # the sprinkler pipe above the bed, spraying while it runs
            d.line((bx0 - 10, by0 - 26, bx1 + 10, by0 - 26), fill=(60, 120, 200), width=6)
            if t < self.watering[i]:
                for k in range(70):
                    u = ((k * 0.137 + t * 1.3) % 1.0)
                    sx = bx0 + (k * 41) % (bx1 - bx0)
                    sy = by0 - 20 + u * (by1 - by0)
                    d.line((sx, sy, sx - 2, sy + 9), fill=(210, 235, 255, 220), width=3)
            d.text(((bx0 + bx1) / 2 - 30, by1 + 18), f"BED {i + 1}", font=FONT_S, fill=(40, 40, 40))
        self._overlay(d, "CAM-02  GREENHOUSE", "greenhouse", t)
        return img

    def _coop_img(self):
        t = time.time()
        sun = self.daylight()
        night = self.is_night()
        img = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        sky = self._sky(sun)
        d.rectangle((0, 0, W, 150), fill=sky)
        if sun > 0:
            sx = 100 + (self.hour - 6) / 12 * (W - 200)
            d.ellipse((sx - 30, 70 - 40 * sun - 25, sx + 30, 70 - 40 * sun + 35), fill=(255, 225, 90))
        elif night:
            d.ellipse((1050, 30, 1095, 75), fill=(235, 235, 210))
            d.ellipse((1068, 25, 1110, 67), fill=sky)
        hill = _mix((40, 70, 50), (90, 160, 90), sun)
        d.polygon([(0, 150), (220, 100), (450, 140), (700, 95), (980, 135), (1280, 105), (1280, 160), (0, 160)], fill=hill)
        grass = _mix((30, 55, 35), (110, 175, 80), max(sun, 0.15 if not night else 0.05))
        d.rectangle((0, 150, W, H), fill=grass)
        # the run: bare earth inside the fence
        rx0, ry0, rx1, ry1 = RUN
        d.rectangle((rx0, ry0, rx1, ry1), fill=_mix((120, 98, 70), (176, 150, 112), max(sun, 0.2)))
        # the hen house
        d.polygon([(50, 200), (270, 110), (490, 200)], fill=(110, 60, 45))
        d.rectangle((70, 200, 470, 560), fill=(185, 60, 50))
        for y in range(215, 560, 24):
            d.line((70, y, 470, y), fill=(160, 48, 40), width=2)
        # nest boxes: an open front with straw and the eggs waiting
        nx0, ny0, nx1, ny1 = NEST
        d.rectangle((nx0 - 8, ny0 - 14, nx1 + 8, ny1 + 8), fill=(150, 110, 70))
        d.rectangle((nx0, ny0, nx1, ny1), fill=(70, 50, 35))
        for k in range(3):
            bx = nx0 + k * (nx1 - nx0) / 3
            d.rectangle((bx + 4, ny0 + 30, bx + (nx1 - nx0) / 3 - 4, ny1), fill=(222, 182, 80))
            if k:
                d.line((bx, ny0, bx, ny1), fill=(150, 110, 70), width=6)
        for e in range(self.eggs):
            box, slot = e % 3, e // 3
            ex = nx0 + box * (nx1 - nx0) / 3 + 16 + (slot % 2) * 18
            ey = ny0 + 30 + (slot // 2) * 14
            d.ellipse((ex - 9, ey - 12, ex + 9, ey + 12), fill=(246, 236, 208))
        # the door: open = the dark inside and the door swung back; shut = planks with a Z brace
        dx0, dy0, dx1, dy1 = DOOR
        if self.door:
            d.rectangle((dx0, dy0, dx1, dy1), fill=(38, 26, 22))
            d.polygon([(dx1, dy0), (dx1 + 40, dy0 + 14), (dx1 + 40, dy1 + 6), (dx1, dy1)], fill=(140, 100, 60))
        else:
            d.rectangle((dx0, dy0, dx1, dy1), fill=(150, 108, 64))
            for x in range(dx0 + 20, dx1, 20):
                d.line((x, dy0, x, dy1), fill=(120, 84, 48), width=3)
            d.line((dx0 + 6, dy0 + 20, dx1 - 6, dy0 + 20), fill=(105, 72, 40), width=10)
            d.line((dx0 + 6, dy1 - 20, dx1 - 6, dy1 - 20), fill=(105, 72, 40), width=10)
            d.line((dx0 + 10, dy1 - 22, dx1 - 10, dy0 + 22), fill=(105, 72, 40), width=10)
        d.polygon([(dx1, dy1), (dx1 + 120, dy1 - 6), (dx1 + 120, dy1 + 8), (dx1, dy1 + 6)], fill=(140, 100, 60))   # the ramp
        # the yard lamp (lit at night)
        d.line((470, 260, 520, 260), fill=(60, 60, 60), width=6)
        d.ellipse((508, 250, 532, 272), fill=(255, 230, 150) if night else (180, 180, 170))
        # hens
        for h in self.hens:
            if not h["out"]:
                continue
            x, y = h["x"], h["y"] + math.sin(h["phase"]) * 2
            d.ellipse((x - 20, y - 15, x + 20, y + 15), fill=(250, 250, 248))
            d.ellipse((x + 10, y - 26, x + 30, y - 6), fill=(250, 250, 248))
            d.polygon([(x + 14, y - 26), (x + 20, y - 34), (x + 26, y - 26)], fill=(210, 30, 30))
            d.polygon([(x + 29, y - 18), (x + 38, y - 15), (x + 29, y - 12)], fill=(240, 170, 40))
            d.ellipse((x + 21, y - 21, x + 25, y - 17), fill=(20, 20, 20))
            d.line((x - 4, y + 14, x - 6, y + 24), fill=(240, 170, 40), width=3)
            d.line((x + 6, y + 14, x + 8, y + 24), fill=(240, 170, 40), width=3)
        # the fence
        for x in range(rx0, rx1 + 1, 45):
            d.rectangle((x - 4, ry0 - 30, x + 4, ry0 + 10), fill=(120, 90, 55))
            d.rectangle((x - 4, ry1 - 20, x + 4, ry1 + 20), fill=(120, 90, 55))
        for y in range(ry0, ry1 + 1, 45):
            d.rectangle((rx1 - 4, y - 30, rx1 + 4, y + 10), fill=(120, 90, 55))
        for yy in (ry0 - 22, ry0 - 2):
            d.line((rx0, yy, rx1, yy), fill=(140, 110, 70), width=4)
        for yy in (ry1 - 12, ry1 + 8):
            d.line((rx0, yy, rx1, yy), fill=(140, 110, 70), width=4)
        d.line((rx1, ry0 - 22, rx1, ry1 + 8), fill=(140, 110, 70), width=4)
        # the fox
        if self.fox:
            f = self.fox
            fx, fy = f["x"], f["y"]
            if f["leaving"] is not None:
                fx += (time.time() - f["leaving"]) * 260
            d.ellipse((fx - 34, fy - 16, fx + 30, fy + 16), fill=(225, 110, 35))
            d.polygon([(fx + 26, fy - 4), (fx + 70, fy - 22), (fx + 74, fy + 6), (fx + 30, fy + 10)], fill=(225, 110, 35))
            d.polygon([(fx + 62, fy - 16), (fx + 76, fy - 20), (fx + 75, fy + 4)], fill=(250, 245, 235))
            d.ellipse((fx - 56, fy - 30, fx - 22, fy - 2), fill=(225, 110, 35))
            d.polygon([(fx - 52, fy - 26), (fx - 48, fy - 46), (fx - 40, fy - 28)], fill=(225, 110, 35))
            d.polygon([(fx - 36, fy - 28), (fx - 28, fy - 46), (fx - 24, fy - 24)], fill=(225, 110, 35))
            d.polygon([(fx - 56, fy - 16), (fx - 72, fy - 12), (fx - 54, fy - 8)], fill=(40, 30, 25))
            d.ellipse((fx - 48, fy - 22, fx - 43, fy - 17), fill=(255, 240, 120) if night else (20, 20, 20))
            for lx in (-24, -10, 12, 24):
                d.line((fx + lx, fy + 12, fx + lx, fy + 32), fill=(60, 35, 20), width=5)
        # night: darker, but the lamp lights the run a little
        if night:
            d.rectangle((0, 0, W, H), fill=(5, 10, 30, 105))
            d.ellipse((380, 200, 1180, 720), fill=(255, 230, 160, 18))
        # the alarm: a blue strobe on the post and the siren's rings
        ax, ay = 1170, 230
        d.rectangle((ax - 5, ay, ax + 5, ay + 70), fill=(80, 80, 85))
        on = t < self.alarm_until
        flash = on and int(t * 6) % 2 == 0
        d.ellipse((ax - 16, ay - 26, ax + 16, ay + 4), fill=(70, 140, 255) if flash else (70, 80, 110))
        if on:
            for k in range(3):
                rr = 30 + ((t * 120 + k * 30) % 90)
                d.arc((ax - rr, ay - 11 - rr * 0.6, ax + rr, ay - 11 + rr * 0.6), 200, 340, fill=(160, 200, 255, 200), width=3)
        self._overlay(d, "CAM-03  HEN HOUSE", "coop", t)
        return img
