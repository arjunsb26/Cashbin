# Changelog

Newest first. Each lane writes under its own heading.

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
