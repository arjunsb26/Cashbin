# Simulators

Everything here speaks the wire protocol in PLAN.md section 6, so the backend cannot
tell a simulator from the real bin. Nothing in the backend imports this directory.

Run from the repository root. `uv` lives in `backend/`, so either activate that
environment or prefix with `uv run --directory backend`.

## The whole demo in one command

```
uv run --directory backend python ../sim/run_scenario.py \
  --scenario demo --url wss://localhost:8443/ws/bin --insecure
```

This drives both simulators from `scenarios/demo.yaml`. The phone puts the item in
frame first, the bin feels it land 300 ms later, and the run waits `--gap` seconds
before the next one. Add `--expect-url https://localhost:8443/api/sim/expect` to tell
the backend which label is coming, which is how the stub provider gets through the
pipeline with no model. That endpoint is dev only, and a refusal is logged and
ignored.

Useful flags:

```
--gap 7          seconds between steps, enough for a real vision call to land
--lead 3         seconds of quiet baseline before the first step
--tail 3         seconds after the last step
--land-delay 0.3 seconds between the item appearing in frame and hitting the scale
--speed 1        wall clock multiplier, 0 runs flat out
--phone-url      defaults to the bin url with /ws/bin swapped for /ws/phone
```

Timing inside a run is measured on the simulated clock, not the wall clock, so the
scenario keeps its shape at any speed.

## The bin on its own

```
uv run --directory backend python ../sim/bin_sim.py --url ws://localhost:8000/ws/bin
```

Then type commands:

```
toss 95
remove 20
bag
tare
quit
```

It streams `weight` at 15 Hz on a noisy baseline (`--sigma`, default 0.8 g), answers
`ping` with `pong`, and prints every `screen` message the backend sends as an LCD box
that mirrors DESIGN.md section 7:

```
+------------------------+
|  Keyboard              |
|                        |
|          -$20          |
|                        |
|  Removed from registe  |
+------------------------+
  amber
```

Line 2 is cut at 20 characters because that is the firmware limit in PLAN.md
section 6.

A toss lands as an impact spike of three times the mass that rings down and is back
inside a gram between 430 ms (a charger) and 680 ms (a full bag going out), which is
what the detector has to see through.

## The phone on its own

```
uv run --directory backend python ../sim/phone_sim.py \
  --url wss://localhost:8443/ws/phone --insecure --show bagel.png
```

It streams the bin background as JPEG at 8 fps, 640 px wide, and composites each item
onto it from the moment that item is tossed until the next bag change. Results, asks
and idles coming back are logged one line each.

## Scenarios

`scenarios/demo.yaml` is the demo: bagel, tagged keyboard, charger, cracked phone,
then the bag goes out. `scenarios/soak.yaml` is sixty tosses with six items the
catalog has never seen, and a bag change every twenty.

The file format:

```yaml
name: demo
sigma: 0.8
steps:
  - kind: toss          # toss, bag_change or removal
    label: keyboard     # what it is, for the expect endpoint and for reading the log
    mass_g: 780         # required for toss and removal
    image: keyboard.png # required for toss, a file in sim/assets
    tag: BB-0002        # optional asset tag, for the QR path
```

`backend/tests/test_sim_scenarios.py` validates both files against that schema.

## Images

```
uv run --directory backend python ../sim/make_assets.py
```

Rewrites everything in `assets/`: one background and one sprite per catalog item, each
a flat coloured shape with its label on it. The keyboard carries a real QR code of
asset tag `BB-0002`, and a test checks that tag still decodes after the sprite has
been composited onto the background and compressed as a camera frame. Real photographs
can replace any file, same names.
