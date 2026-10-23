# Inspector demo: a small farm

A simulated farm with two cameras, to try [Inspector](https://github.com/wrbyhaquc/inspector) without a real farm.
It runs on your own computer; the "cameras" are pictures the simulator draws, and the "equipment" (roof vents,
sprinklers, the hen house door, a fox alarm) are switches Inspector can turn through an HTTP output - the way it
would drive real devices.

English · [繁體中文](README.zh-TW.md)

![The greenhouse and the hen house cameras](docs/preview.png)

## What happens on the farm

Time runs fast (by default one day takes 6 minutes).

| Camera | What you see | What is going on | What should be done |
|---|---|---|---|
| Greenhouse | The red digits on the wall display | The temperature: the sun heats the greenhouse, much more with the roof vents shut | Open the vents when it gets too hot, close them when it has cooled down |
| Greenhouse | Pale soil, yellow and then brown plants in one bed | That bed is drying out (each dries at its own pace, faster when hot) | Water that bed only |
| Hen house | Hens in the run, the door open or shut | Hens go out after dawn and walk back in at dusk by themselves | Open the door in the morning; shut it at night once every hen is inside |
| Hen house | Eggs on the straw in the nest boxes | Each hen lays one a morning | Tell someone to collect them |
| Hen house | An orange fox outside the fence | At night it takes a hen still outside, or one through an open door | Sound the alarm: it runs off |

## Run it

Needs Python 3.10+ and Pillow (`pip install pillow`; Inspector already has it).

```bash
python sim/server.py            # http://127.0.0.1:8810/
```

| Address | |
|---|---|
| `http://127.0.0.1:8810/` | The control room: both cameras, the equipment switches, demo buttons (day, dusk, night, heat wave, a dry bed, a fox, eggs, speed) |
| `http://127.0.0.1:8810/greenhouse/video.mjpg` | The greenhouse camera as an MJPEG stream: in Inspector, "Sources › + Add source › Stream › HTTP" |
| `http://127.0.0.1:8810/coop/video.mjpg` | The hen house camera |
| `http://127.0.0.1:8810/<camera>/snapshot.jpg` | One picture |
| `POST http://127.0.0.1:8810/api/command` | `{"command": "vents_open"}` - also `vents_close`, `water` (with `"value": 1`, `2` or `3`: the bed), `door_open`, `door_close`, `alarm`. Exactly what an Inspector HTTP output sends |
| `http://127.0.0.1:8810/api/state` | The simulator's own numbers, for checking: Inspector itself only judges from the pictures |

Options: `--port`, `--fps` (pictures per second, default 5), `--day-minutes` (real minutes per simulated day),
`--seed` (the same events every run), `--host` (default 127.0.0.1: only this computer).

## The pack

What Inspector reads on the two pictures is in `pack/states.json`: the thermometer's digits (a "read digits" rule
with the digits taught in `pack/refs/`), the vents and the door (reference pictures), each bed's dry soil, the hens,
the eggs, the fox and the daylight (colour rules). Each camera shows its name tag in the top left corner; the states
of one camera read "Other camera" on the other's picture, so both cameras share one set of states.
`tools/check_states.py` checks every state against pictures of every situation the simulator can draw.

The complete pack (scripts, an operation panel for the farmer) comes next.

## License

Apache-2.0.
