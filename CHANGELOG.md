# Changelog


Newest first. Each lane writes under its own heading.

## 2026-09-19, lane a part 2: ingest sockets, events, media, record and replay

- `backend/app/ingest/bin_socket.py`: `/ws/bin` for real. Validates every frame against
  `BinToBackend`, stamps each weight with the backend clock, feeds the step detector with
  tuning read from the live settings, publishes `weight` to the dashboard at 10 Hz, and
  builds the event off the read loop so the stream never stalls behind a slow pipeline.
  Sends a ping every 2 s, forwards everything on the `bin` bus channel to the device, and
  says on the dashboard when the bin connects, disconnects or goes quiet for 5 s.
- The dashboard weight downsampler advances a 100 ms slot instead of restarting the timer
  from each published sample. Restarting it lands on every second sample of a 15 Hz stream,
  which is 7.5 Hz, not the 10 Hz PLAN.md section 6 asks for. A test holds the rate.
- `backend/app/ingest/phone_socket.py`: `/ws/phone`. Binary frames into the ring, text
  frames validated, anything on the `phone` channel forwarded to the page. Several phones
  may connect and all of them feed the one ring.
- `backend/app/ingest/ui_socket.py`: `/ws/ui` forwards the `ui` channel and, on connect,
  tells the page the current status of every device the backend has heard from.
- `backend/app/ingest/events.py`: the step to event row join. Writes the row, saves before,
  after, peak and crop under `media/{event_id}/`, records the paths and the crop quality,
  publishes `event.created`, puts `thinking` on the LCD, then awaits the `on_event` hook.
  That hook is the only seam to identification and defaults to doing nothing.
- A bag change and a removal get their row and their chart line but no `thinking` screen.
  Nothing identifies them, so nothing would ever come along to clear it off the LCD.
- `backend/app/ingest/frames.py`: the 4 s camera ring, evicting by the newest stamp rather
  than by reading the clock, so a ring that stops being fed keeps what it has.
- `backend/app/ingest/media.py`: image saving and the `/media` URL. The column holds the
  relative path, so moving the media directory does not rewrite every row.
- `backend/app/ingest/serial_reader.py`: the PLAN.md section 5 fallback transport. Reads
  JSON lines off any file-like object into the same `BinSession` the socket uses. `pyserial`
  stays optional and missing it prints how to install it.
- `backend/app/ingest/recorder.py`: set `RECORD_DIR` and every bin message and camera frame
  is written with its arrival time. `scripts/record.py` runs the backend with it on and
  `scripts/replay.py` plays a recording back as an ordinary bin and phone client, reusing
  the simulator's connection code rather than copying it.
- `backend/app/api/events.py`: the event list newest first, the full detail with trace,
  frame URLs, identifications, item record, options, entries and corrections, and void.
  Every read works while the later tables are empty, because that is the state every event
  is in for its first second. Void calls `ledger.queries.void_event` if it exists yet.
- `POST /api/device/tare` publishes the tare on the `bin` channel and reports whether a bin
  was there to receive it, so the dashboard can say so instead of pretending.
- `POST /api/sim/toss` builds a synthetic step and, when an image is named, pushes it into
  the frame ring first. The image name comes off the wire, so it is resolved against
  `sim/assets` and refused if it lands anywhere else.
- A pong no longer draws a ping back. The bin answers every ping with a pong, so one
  reply per pong is a loop that runs as fast as the socket allows: a 29 second scenario
  run against the first build recorded 40787 pongs. The heartbeat is now the only thing
  that starts a ping, and a regression test holds it.
- The heartbeat waits for the hello. It used to start the moment the socket opened, so a
  client that had not greeted yet was pinged, answered, and was closed for talking before
  its hello. Replay hit that every time, because it opens its sockets before the first
  recorded message.
- `scripts/replay.py` slides both timelines so the first recorded thing happens at zero,
  keeping the gap between them. A recording of a run that began a minute into a session
  would otherwise connect and then sit silent for a minute.
- The recorder refreshes its metadata counts every hundred messages. A recording is worth
  most when the thing being recorded fell over, which is exactly when `close` never runs.
- The detection clock is a field on the ingest state rather than a call to `time.monotonic`
  in the middle of the socket, so a test drives a scripted timeline instead of spending
  twenty real seconds waiting for a staircase to settle.

## 2026-09-19, lane a part 1: step detection, crop, simulators

- Made the lane's test files pass a plain `uv run mypy`, which checks `app` and
  `tests` and was red on the simulator imports and four opencv results that can be
  None. The simulator imports carry an ignore because they are put on the path at
  runtime and mypy cannot follow that.
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

## 2026-09-19, lane b: engine, ledger, seed data

- Added `backend/data/README.md` explaining every seed file, where its numbers
  came from and how to refresh the WARM factors.
- Seeded `backend/data/catalog.csv` with 30 items across food, packaging and
  small electronics, every price carrying the listing URL it was read from, and
  `backend/data/assets_seed.csv` with twelve register rows whose cost, in service
  date and tax method are all `NEEDS_HUMAN`. Added `backend/data/llm_prices.csv`
  with three empty openai rows.
- Added `app/ledger/register.py`: `mark_disposed`, `find_ghosts` and
  `book_summary` as pure functions over the register.
- Added `app/ledger/journal.py`: the chart of accounts, balanced entry builders
  for an inventory write off, a fixed asset disposal with its gain or loss
  branch, and the tax memo that puts book and tax side by side. Added the void
  reversal, the trial balance, and the unrecorded asset flag. Every builder
  checks its own balance before returning.
- Added `app/engine/options.py`: all five options scored, ranked by net after
  tax with ties inside 50 cents broken by lower carbon, blocked options kept
  with no rank, plus the best, greenest, saved and tone summary.
- Added `app/engine/carbon.py` and `app/engine/tax.py`: EPA WARM factors
  converted from MTCO2E per short ton to kg CO2e per kg, and one pure function
  per cell of the tax table, including the enhanced food donation deduction and
  the electronics block on binning.
- Added `app/engine/depreciation.py` and `app/engine/rules.py`: straight line
  book value with salvage, tax basis for bonus and straight line methods with an
  override, and the loader for the seven cited tax rules.
- Added `app/engine/records.py`: the typed records the engine works on, the
  builder that assembles an item record from a catalog row or an asset row, and
  `list_needs_human()` for the setup checklist.
- Added `scripts/extract_warm.py` and generated `backend/data/warm_factors.csv`
  from the EPA WARM version 16 workbook. 61 materials, real numbers, blanks
  where the workbook publishes none.

## 2026-09-19, step 0: skeleton and contracts

Milestone M0, plus every cross-lane contract frozen so the lanes can run in parallel.

### Backend

- `backend/pyproject.toml` on Python 3.12, managed by `uv`. FastAPI, pydantic v2,
  pydantic-settings, SQLAlchemy 2, hypercorn, numpy, opencv-python-headless, websockets,
  cryptography. Dev group has pytest, pytest-asyncio, httpx, trio, ruff, mypy. `uv run pytest`
  runs everything, including the contract and generated-types checks.
- `app/config.py` holds every tunable from PLAN.md section 18 as a pydantic-settings model.
  Environment overrides it, and the uppercase names PLAN.md uses set the fields directly.
  Adds `DEV_TOOLS`, `HTTPS_PORT`, `HTTP_PORT`, `CERT_DIR`, and the three product name fields
  read from `brand.json`. Every string setting has its trailing carriage return stripped.
- `app/db.py` builds the SQLite engine in WAL mode with foreign keys on, creates every table
  at startup, and hands out sessions.
- `app/models.py` has all thirteen tables from PLAN.md section 8 with the exact column names,
  including `class` where the plan uses it. Money is integer cents, mass is float grams,
  timestamps are UTC ISO strings. The chart of accounts is a constant. `identification` also
  carries `provider` and `model`, because CLAUDE.md requires every identification row to say
  what served it.
- `app/schemas.py` is the contract. Every socket message from PLAN.md section 6 as
  discriminated unions on `type`, every REST body from section 14, the strict `VisionResult`
  and `ValueEstimate` from section 9, and `ValidatedLabel` for outside text.
- `app/notify/lcd.py` builds every LCD screen. `app/notify/bus.py` is the in-process pub/sub
  that fans out to `/ws/ui` and `/ws/phone`.
- `app/identify/providers.py` and `app/identify/embed.py` hold only the Protocols and
  `IdentifyContext`. Lane C writes the implementations.
- `app/api/*.py` has a route for every path in PLAN.md section 14. Each returns 501 with a
  plain body and a header naming the lane that fills it. `/api/sim/*` and the API docs only
  mount when `DEV_TOOLS` is on.
- `app/main.py` is the app factory. Health at `GET /api/health`, `GET /brand.json` with no
  caching, static mounts for `/media` and `/phone`, and the three sockets accepting a
  connection, checking the hello, and answering ping and pong.

### Contracts

- `firmware_contract.md` at the root carries PLAN.md section 6 verbatim for the hardware
  teammate. `backend/tests/test_contract.py` validates every JSON line in it against the
  models, so the document cannot drift.
- `scripts/gen_types.py` writes `contracts/api-schema.json` and `contracts/api-types.ts`.
  `scripts/check_types.py` fails when either is stale, and the test suite calls it.

### Scripts

- `scripts/make_cert.py` writes a self-signed certificate covering `localhost` and every LAN
  address this machine has, so the phone can reach it by IP. Neither file is printed.
- `scripts/run_backend.py` serves HTTPS on `:8443` and HTTP on `:8000` from one hypercorn
  process. Both binds verified by request.

### Tests

202 tests. Health and the database, every wire example round-tripping, LCD truncation, bus
fan-out, the three sockets, the firmware contract, the generated types, and the twenty-five
input attack set in `backend/tests/attack_set.py` run against all three places outside text
reaches the system.

### Decisions worth knowing

- LCD line and big fields truncate instead of refusing. PLAN.md section 6 states a hard width
  and also says the backend is responsible for truncation, and its own example second line is
  21 characters. Truncating in the type makes both statements true and means nothing wider
  than the screen can ever reach the bin.
- `memory_max_dist` has no default in PLAN.md. It starts at 0.35 and is a live setting.
