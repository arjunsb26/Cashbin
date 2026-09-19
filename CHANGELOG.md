# Changelog

Newest first inside each heading.

## Lane A

- `backend/tests/test_sim_crop.py`: the demo run's camera frames through `pick_frames`
  and `crop_item`, so the fake camera and the crop are proved to agree the way the
  fake scale and the detector already were. It also holds the `before_lead_ms` default
  in place by failing at the 300 ms PLAN.md section 7 suggests.
- Replaced the "settles inside about 500 ms" claim in the simulator docs with the
  measured range, 430 ms for a charger to 680 ms for a bag going out.
- Raised the crop `before_lead_ms` default from the 300 ms in PLAN.md section 7 to
  600 ms. The item is in camera shot for the whole flight, so a lead equal to the
  flight time picks a frame that already contains the item and the diff comes back
  empty. Every crop in the demo run went from `low` to `good` on that one change.
- Set the `stable_k` default to 2.0. A window counts as still when its standard
  deviation is under twice the noise sigma. At 3.0 the settle window could open while
  the scale was still ringing, which biased the mass by up to 2 g on a 172 g item.
- `sim/README.md`: how to run each script.
- `sim/make_assets.py` and `sim/assets/`: one bin background and twenty item sprites,
  each a flat coloured shape with its label drawn on it. The keyboard carries a real
  QR code of asset tag `BB-0002`, checked to survive compositing and JPEG.
- `sim/scenarios/demo.yaml` and `sim/scenarios/soak.yaml`: the demo run and a sixty
  toss soak with six unknown items and a bag change every twenty.
- `sim/run_scenario.py`: drives both simulators from one YAML file, posts the expected
  label to `/api/sim/expect` when that is asked for, and waits on the simulated clock
  so a run keeps its shape at any speed.
- `sim/phone_sim.py`: streams the bin background as JPEG at 8 fps and composites each
  tossed item onto it until the next bag change.
- `sim/bin_sim.py`: streams `weight` at 15 Hz on a noisy baseline, adds an impact
  spike and a damped wobble on a toss, answers `ping`, and prints every `screen`
  message as an LCD box.
- `sim/lcd_box.py`: draws the 240x320 LCD as text, with the firmware's field limits.
- `backend/app/detect/crop.py`: picks the before, after and peak frames for a step and
  cuts the new item out of the after frame, falling back to the whole frame with
  `crop_quality = "low"` when the changed area is too small or too large.
- `backend/app/detect/steps.py`: step detection on the weight stream, as a pure
  `detect()` over recorded samples and as a streaming `StepDetector`. Tosses, bag
  changes and removals, each with its mass, its error and the trace around it.
