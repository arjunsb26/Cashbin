# Changelog

Newest first. Each lane writes under its own heading.

## 2026-09-19, lane b: tag case and the tone rule

- The tone is amber whenever a better option than the bin exists on either
  axis, not only on money. Red still means the bin is blocked. Green now means
  the bin was the best option, or the best option beats it by less than the tie
  break on money and by less than the new `tone_co2e_kg` setting on carbon
  (0.02 kg). An unknown carbon figure never gives a green tone. The bagel now
  reads amber, which is what the LCD should say when donating it is better.
- `scripts/seed_db.py` puts every asset tag through the same validator the API
  uses, so `BB-0002` in the CSV lands as `bb-0002` in the register and matches a
  tag typed into the form or read off a QR code. The CSV keeps its own spelling
  and the skipped lines still name the row the way the file does.

## 2026-09-19, lane e: phone camera page

### 2026-09-19

- Added the camera page at `/phone`: start screen, full bleed rear camera preview, a
  status pill with a dot and Live or Reconnecting, a result sheet built like the ticket
  at phone scale, and the ask with candidate buttons and a validated free text answer.
- Streams JPEG frames at 640 px wide, quality 0.7, about eight a second on a timer, over
  a secure WebSocket to `/ws/phone`, dropping frames when the send buffer holds more than
  two of them so a slow link never builds latency. Reconnects with backoff from 0.5 s to
  8 s and answers ping with pong.
- Copied the colour, type, space and motion tokens from DESIGN.md section 2 into
  `phone.css`. No other colour value appears in the page. IBM Plex Sans and Sans
  Condensed ship as local woff2 files with the OFL licence beside them.
- Product name comes from `GET /brand.json` at runtime and falls back to the page title.
- Typed answers are read into one field: trimmed, lowercased, letters, digits, spaces and
  hyphens only, 40 characters at most, with the understood value and every dropped part
  shown before it is sent.
- Screen wake lock while the camera runs, re-requested when the page becomes visible
  again. Safe area insets respected. Web app manifest for add to home screen.
- Errors read as sentences: camera refused, no camera, camera busy, connection dropped,
  and the page opened over plain HTTP.
- Added `phone/dev/`: a mock backend over HTTPS with its own certificate, a frame counter,
  a scripted result and ask, and a Playwright run that captures the six states at 390x844.
- Moved the mock backend to port 8444, because the real backend owns 8443.
- A ticket that arrives while a question is on the screen waits. It rises once the
  question has been answered and the quiet learned line has had its moment, so a question
  is never taken away under a thumb and no ticket is lost.
- The big figure on a ticket is red when the money reads as a loss, whatever the tone of
  the result. The tone stays in the band above it.
- The screenshot run turns the mock's scripted sequence off as it starts and sends every
  result and ask itself, so the same ten shots come out every time.

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

## 2026-09-19, lane b: seed script, register, catalog and books over the API

- Filled `backend/data/llm_prices.csv` with the five openai models the team
  chose and their published prices, adding a `cached_input_usd_per_million`
  column. Nothing in that file waits on a person any more.
- Added `backend/tests/test_api_assets.py`, `test_api_catalog.py`,
  `test_api_journal.py`, `test_seed_db.py` and `test_engine_food_resale.py`.
  The register, the catalog and the journal are no longer stubs, so their three
  rows moved out of the not-built-yet list in `test_health.py`.
- Added `scripts/seed_db.py`: loads `catalog.csv` and `assets_seed.csv` into the
  database, upserting by label and by tag, so running it twice changes nothing.
  An asset row whose cost, date or tax method is still `NEEDS_HUMAN` is skipped
  and named, or stored with an obvious stand in under `--allow-placeholders`.
  `seed_all(session)` is the same work for the app to call on a first start.
- Filled `GET /api/journal`: entries with their lines and account names, the
  trial balance, and whether it agrees.
- Filled `GET`, `POST` and `PATCH /api/assets` and `GET`, `POST /api/catalog`.
  Every register row carries today's book value and tax basis, computed once by
  the engine so the page cannot disagree with the ledger.
- Added `app/ledger/queries.py`: posting a balanced entry into `journal_entry`
  and `journal_line`, reading entries and the trial balance back, and voiding an
  event by reversal. An unbalanced entry never reaches the database.
- Added `EngineSettings.from_settings()`, so the engine's numbers are built from
  the one live settings object rather than kept in step by hand.
- Food in the bin can no longer be resold. `resell` is a visible blocked row
  with the reason "Food in the bin cannot be resold" and the new
  `FOOD_NO_RESALE` rule. Every food row in `catalog.csv` carries a `food` flag.
- Food cost in `catalog.csv` is now the business cost, estimated at half the
  retail listing and marked as an estimate, with the listing kept as fair market
  value. The enhanced food donation deduction is no longer zero, so donating the
  bagel ranks above binning it.

## 2026-09-19, lane c: the request builders leave the adapter

- Added `app/identify/openai_request.py` holding the prompt text, `strict_schema`, the body
  assembler and the two `build_*_request` functions. `openai_provider.py` is now 123 lines,
  89 of them code, down from 284 at the start of the day, and it does one job: send, retry
  once, validate, record what it cost.
- Moved the schema and request-shape tests into `tests/test_identify_request.py`, including
  the attack set run against the builders. One hostile catalog label test stays in
  `test_injection.py`, because that file is where the rule is claimed.

## 2026-09-19, lane c follow-ups: contracts, the estimate cache and the tone setting

- Moved the estimate cache into `app/identify/estimate_cache.py` with its own tests. The
  adapter is now 222 lines, 169 of them code, down from 284.
- Moved `CallUsage` into `app/identify/providers.py` and added
  `last_call: CallUsage | None` to both Protocols, so what a call used is part of the
  contract rather than a convention. A provider that cannot say what it used no longer
  satisfies the Protocol.
- Added `learned` to `RoundListResponse` and filled it from `what_learned()` in
  `GET /api/metrics/rounds`, so the Learning page has a carrier for the sentences.
- Added `tone_co2e_kg` (default 0.02) to `Settings`, `RUNTIME_SETTING_KEYS`, `SettingsRead`
  and `SettingsUpdate`, so the engine's tone threshold is editable live like every other
  threshold.
- Regenerated `contracts/api-types.ts` and `contracts/api-schema.json`.

## 2026-09-19, lane c: identification, the ask loop, corrections and metrics

- Added `app/identify/embed.py` `BaselineEmbedder`: an 8x8x8 HSV histogram beside
  a 16x16 grayscale thumbnail, each block L2 normalised before they are joined,
  768 wide, deterministic. The thumbnail has its own mean removed first, because
  raw brightness is the same for every crop under the same lamp.
- Added `app/identify/memory.py`: the kNN index over the exemplar table, cosine
  distance, the 4 of 5 vote rule scaled for a small table, and `add` so an answer
  counts on the very next toss.
- Added `app/identify/qr.py`: QR tags read off the after and peak frames with
  `cv2.QRCodeDetector`, every payload through `normalise_label`, then an exact
  match against the asset register.
- Added `app/identify/priors.py`: Bayesian mass fusion with a Normal likelihood
  over `prior_var + mass_err^2`, labels with fewer than three weighings skipped
  and given the average likelihood, plus the Welford update that keeps a seeded
  catalog variance instead of discarding it.
- Added `app/identify/stub.py`: the deterministic vision and estimator providers
  and the `POST /api/sim/expect` queue behind them. A catalog label answers at
  0.95 and anything else at 0.55, so the ask path is exercised without breaking
  anything.
- Added `app/identify/openai_provider.py`: the official `openai` SDK through
  Chat Completions, the crop as a base64 data URL, a strict JSON schema
  generated from `VisionResult` itself, one retry, then a low confidence answer
  so the ask opens. Catalog labels and asset tags travel in a JSON data block,
  never in the instruction text.
- Added `app/identify/cost.py`: prices read from `data/llm_prices.csv`, tokens
  turned into microdollars, and no price meaning no number rather than a zero.
- Added `app/identify/pipeline.py`: QR, memory, cloud, fusion, decide, with an
  `identification` row per stage and the ask published to the dashboard, the
  phone and the LCD. The cloud call runs in a thread under `llm_timeout_s` and
  never raises into ingest.
- Added `app/learn/corrections.py`, `rounds.py` and `metrics.py`: one answer
  settles the ticket, stores an exemplar, moves the mass prior and, when it
  overrules a confident answer, moves the event out of the first-try column.
- Filled the handlers for `POST /api/corrections`, `GET /api/metrics/rounds`,
  `POST /api/metrics/rounds/start`, `GET /api/summary`, `GET` and `PATCH
  /api/settings`, and `POST /api/sim/expect`.
- Added `llm_base_url`, `llm_agent_model`, `llm_vision_effort`, `llm_text_effort`
  and `openai_api_key` to `config.py`. None of them is readable through the API.
- Added 14 test files, 161 cases, including the full attack set against the ask
  answer, the photographed sign and the request body.

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

## 2026-09-19, lane d: the dashboard

- Next.js App Router in `/frontend`, TypeScript strict with
  `noUncheckedIndexedAccess`, Tailwind mapped onto one CSS variable file. Radix
  primitives only, styled from the tokens. No prestyled kit.
- DESIGN.md section 2 tokens live in `app/tokens.css` and nowhere else.
  `pnpm check:hex` fails the build when a colour literal appears outside it.
- IBM Plex Sans and IBM Plex Sans Condensed ship as local woff2 files with the
  OFL licence beside them, loaded through `next/font/local`, so the venue never
  needs the network.
- `lib/format.ts` is the only place a number is turned into text: accounting
  money with parentheses and the symbol under the caller's control, mass with a
  thin space and an ink-soft unit, carbon, percentages, the `est.` marker, the
  cost per toss, and the reader that turns typed free text into a validated
  label. Nineteen tests cover it.
- Pages: Live, Books, Assets, Asset tags, Learning, Close, event detail,
  `/setup` and `/kit`. The last two are not linked from the rail.
- The ticket is one component. Live, the tape, the event page and the kit all
  render it, and the phone page can copy its markup.
- Every money, mass and carbon figure opens the evidence drawer: photo and
  crop, the weight trace with the step shaded, how it was identified with both
  probability sets, the substituted formula, the rule with its citation, and
  whether a person confirmed it.
- Mock mode sits behind `NEXT_PUBLIC_API_MOCK=1` and one switch in
  `lib/api.ts`. Nothing else in the app imports from `lib/mock`. `?state=` picks
  empty, loading or error, `?ask=1` opens an ask and `?replay=1` replays the
  demo tosses on a timer.
- `pnpm screenshots` builds in mock mode, starts the app and captures every
  route at 1440x900 and 390x844 in every state.
- PWA: manifest read from the brand file, icons at 192 and 512, and a service
  worker that caches the app shell and never API or socket traffic.
