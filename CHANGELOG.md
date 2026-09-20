# Changelog

Newest first. Each lane writes under its own heading.

## 2026-09-20, lane m: the UX pass after the first real use

- The laptop layout reads a step larger. Body 16, secondary 14, section titles 17, header
  totals 36 Condensed, the ticket figure 72 Condensed, the ticket sheet 640 px and the
  ruled row 44 px, all from `app/tokens.css` under a 1024 px breakpoint. The 390 px layout
  is untouched, so the phone still carries DESIGN.md section 2 as written.
- The Live page fills its height. Under the current ticket the three tosses before it print
  as compact tickets, the tape column ends in a round total with a hand drawn accuracy bar
  when the tape is shorter than the column, and the scale strip is 120 px tall with a time
  axis reading thirty seconds back to now and the mass written over every detected step.
- Colour carries a little more meaning. The ticket takes a 4 px top band in the engine's
  tone, the two totals that are money and mass kept out of the ground carry a tone dot, the
  best option row is filled with a kept tint rather than marked with a rule, and a question
  tints the ticket header in caution. Two tint tokens were added; no new hues, no gradients.
- Every ticket says which of the three classes it is and why, in one line under the label.
  "book loss" and "tax basis" and their neighbours explain themselves on hover, from one
  copy file that the ticket, the drawer, the register and the kit all read.
- A first run opens on a three step card with the simulator command in a box that copies,
  and wraps rather than hiding its own second half.
- Connecting, not answering and bin offline are three different states with three different
  sentences, and skeletons never stand for more than ten seconds without one.
- The evidence drawer reads the rule in plain words with its citation, the tape reads what
  was actually posted, and the option table's carbon column reads CO2e avoided.
- Window shortcuts stand aside for anything typed into an input, textarea, select or
  contenteditable, the "Something else" box takes focus when it appears, and a half typed
  label survives the panel being taken off the screen and put back.
- An ask has a way out. "Not now" and Escape wave the question off without posting
  anything: the ticket stays in the tape marked asking, so the close still counts it.
  When the payload carries the model's own sentence, the ask prints it as "Looks like".
- "Add a toss" on the Live page opens a dialog asking for a weight and posts it to the
  simulator, for a demo with no bin on the desk. It is not rendered at all unless the
  backend answers the simulator route, so the demo build never shows it.
- An empty scale reads 0 g rather than -0 g, and the trace stays inside its own column
  when the layout settles.

## 2026-09-19, lane l: a webcam camera and a one-command launcher

- `hardware/webcam_client.py` makes any webcam the eye over the bin. It speaks the same
  `/ws/phone` protocol the phone page does: a `hello` with `ua = "webcam-client"`, about
  eight JPEG frames a second at 640 px and quality 70, `pong` for every `ping`, and one
  readable line for every result and ask that comes back. `--list` prints the camera
  indices that open with their resolution. `--preview` opens a small window showing what
  is being sent, captioned with the last result, so the camera can be aimed; it is off by
  default and is drawn with tkinter, because the headless OpenCV build this repo installs
  has no window support. Capture runs in its own thread, so the camera keeps running while
  the socket is away, the socket reconnects with backoff, and an unplugged camera is
  reopened every two seconds. No new dependency.
- `scripts/demo_up.py` and `scripts/demo_up.ps1` bring the whole demo up with one command
  and keep it up. It starts the backend and waits for `/api/health`, retrying the start up
  to three times when Windows refuses a loopback socket with error 10013. It rebuilds the
  dashboard only when `.next` is older than the newest file under `frontend/app`,
  `components` or `lib`, starts it on 3000 with `NEXT_PUBLIC_API_URL` set for the laptop,
  and waits for it too. It then starts the webcam client and the bin simulator, and prints
  one block with the three URLs, the laptop's address, which camera is in use and the
  commands you can type. Typing `toss 150` in the launcher's terminal moves the scale.
- The launcher watches. It polls health every five seconds, looks again every second once
  a poll misses, and after three misses in a row restarts the backend and says so in one
  line. The camera reconnects itself; the bin simulator holds one socket and does not, so
  the launcher gives it a new process. It also says when the mobile hotspot goes off,
  which is the real reason the phone drops.
- Every child's full output is teed to `runs/<timestamp>/`, gitignored, so a crash leaves
  evidence. The console shows only what a person needs: the camera's results, the bin's
  LCD boxes, and anything from the backend or the dashboard that reads like trouble.
- Two things found while proving it, both fixed in the launcher. `localhost` costs two
  seconds a connection on this laptop, every time: the backend binds IPv4 only, the name
  resolves to `::1` first, and that attempt sits there until it times out. Every check and
  every local socket the launcher opens now dials `127.0.0.1`, which costs forty
  milliseconds. The URLs printed for people keep the word, because a browser tries both at
  once. And `pnpm start` is a shell that starts Next in a second process, so terminating
  the shell left Next holding port 3000 and the next launch could not bind it; stopping a
  child now kills its whole tree.

## 2026-09-19, lane k: realistic testing with real photographs

- `sim/assets/real/` holds 42 freely licensed photographs of the seventeen things the
  demo throws, plus three bin backgrounds, each with its author, licence and page URL
  in `SOURCES.md`. No person is in frame. Every file is at most 800 px on the long
  side and under 150 kB. `sprites/` holds each item at 220 px, which is the size the
  phone simulator composites at inside a 640 px frame.
- `scripts/vision_bench.py` runs the real model over those photographs the way the bin
  will see them: composited onto a bin background, cut out by `detect.crop.crop_item`
  against the empty-bin frame, sent through the shipped request builder and the
  shipped reply validation. The confident-or-ask decision is imported from
  `identify.pipeline`, so a threshold change on main changes the table. It takes
  `--effort`, `--service-tier`, `--max-px`, `--detail`, `--repeat`, `--per-item` and
  `--sprite-px`, writes a CSV and a markdown table per run, and saves every crop.
  Nothing under `/backend` was edited: the three knobs the adapter does not expose yet
  are set on the request body inside the bench.
- `sim/scenarios/demo_real.yaml` is `demo.yaml` step for step on photographs.
  `sim/scenarios/bench.yaml` is thirty tosses in five blocks, built so that one run
  measures the cold case, the same photograph again, and a different photograph of the
  same object.
- `sim/assets/real/keyboard_1_tagged.jpg` and its sprite are `keyboard_1.jpg` with the
  BB-0002 QR label pasted on, built the way `sim/make_assets.py` builds the drawn
  keyboard's: a 104 px code on a 10 px white quiet zone, at the same module size, on a
  380 px sprite. `demo_real.yaml` uses it, so the keyboard resolves by QR in 87 ms with
  the asset disposal behind it instead of costing a model call and coming back as an
  untracked object. The tag decodes through `identify.qr.read_tags` off a frame
  composited at 640 px and encoded at the phone's JPEG quality, on all three bin
  backgrounds. `keyboard_1.jpg` is untouched and `SOURCES.md` still describes it.
- Findings, with the numbers behind them, are in
  `briefs/reports/lane-k-realistic-vision-test.md`. In short: 86.8 percent accuracy at
  effort `low` over 68 live calls, a 2.9 to 6.1 second wait from scale to LCD with the
  value estimate rather than the vision call as the bigger half of it, service tier
  `fast` cutting the vision call from 1310 ms to 854 ms, and exemplar memory unable to
  match two photographs of the same object at any threshold. Every change those point
  at is a proposal for the coordinator; none was made.

## 2026-09-19, lane j: the backend follow-ups the first real run exposed

- `GET /api/rules` serves every rule in `tax_rules.yaml` as `RuleRead(id, title,
  plain_text, citation_url, needs_human_review)`. The evidence drawer was printing rule
  codes because the text and the citation lived only in the engine's data file and no
  route read them out. The words are still written once.
- `GET /api/events/{id}` fills `account_name` on every journal line, from the same chart
  of accounts `/api/journal` uses. The event page was borrowing the names from a second
  request to the journal.
- `scripts/gen_types.py` no longer eats a field whose name collides with a JSON Schema
  keyword. The flattening step dropped every key called `title` wherever it appeared,
  including inside `properties`, which cost `CloseCheck.title` and `PhoneResult.title`
  their place in `contracts/api-types.ts` while every drift check stayed green.
  `scripts/check_types.py` now compares fields and not only type names, so the whole
  class of bug fails the suite.
- `OptionScoreRead.kg_co2e_avoided` and the close's `kg_co2e_avoided` are positive
  numbers: what this option avoids against the bin, never below zero. WARM's source
  reduction factors are negative because they are avoided emissions, so the close read
  "emissions if the best option had been followed: -6.04 kg". `kg_co2e` is untouched, so
  the audit trail still carries the signed figure.
- `EventSummary.posted_cents` is what the journal actually posted for the ticket, as an
  income statement amount: negative for a loss, positive for a gain, null when no entry
  was written. `net_book_cents` is a book value and is zero for everything that is not a
  tagged asset, which is why the tape had to read one ticket per row to print an amount.
- `EventSummary.flags` carries `possible_unrecorded_asset` on the ticket, off the same
  rule the close uses (`ledger/journal.looks_unrecorded`). An untracked item whose
  replacement cost is over the capitalization threshold also carries "Looks like
  equipment. Confirm on the Assets page." on its bin option.
- `POST /api/device/tare` writes a `last_tare` settings row with the time, the bin's new
  zero and what was on the scale a moment before, but only when a bin was there to
  receive the command. The close's mass check names the tare and its time instead of
  falling back to the first weight sample of the period.
- The estimator's data block carries the EPA WARM material names as its vocabulary, so a
  model cannot name a material the carbon table has no factor for. Two tests hold the
  data honest: every material in `catalog.csv` is in `warm_factors.csv`, and every
  catalog item gets a carbon figure for every option.
- `GET /` sends the laptop to the dashboard and anything else on the network to the
  phone page, and an address with nothing at it says where both of them are instead of
  answering "Not Found". A route that answers 404 with its own sentence keeps it.
- Speed, in three parts. The vision call now starts when the step opens rather than when
  the weight settles: `app/identify/early.py` holds the call, ingest claims it for the
  event once the row exists, and identification awaits it instead of making its own. A
  step that turns out to be a bag change or a removal cancels it. `identify_at_step_open`
  switches it off in one place.
- The request asks for the host's fast queue (`llm_service_tier`, default `fast`) and for
  no reasoning on either call (`llm_vision_effort` and `llm_text_effort`, both `none`).
  All three are runtime settings, validated against the installed SDK's own literals, so a
  value the host would refuse with a 400 cannot be set.
- The picture sent to the model is re-encoded to 384 px on its longest side at quality 80
  (`vision_image_max_px`, `vision_image_quality`), which Lane K's bench found worth 57 ms
  and 14 percent of the input tokens. The full size crop stays on disk for the evidence
  drawer. The image part already asked for `detail: "low"`.
- `scripts/run_backend.py` binds both address families, IPv6 first. On this laptop
  `localhost` resolves to `::1` before 127.0.0.1, and a server listening on IPv4 alone made
  every new connection wait for the IPv6 attempt to time out. Measured on spare ports: 0.21
  s per connection bound to IPv4 only, 0.0017 s bound to both. A dashboard opens many
  connections, which is why a backend that was answering perfectly looked dead.
- PLAN.md 21a item 23. Memory no longer answers on its own. Lane K measured the embedder on
  real photographs: two pictures of the same object are further apart than the two closest
  pictures of different objects, so no threshold separates them, and in a thirty toss run
  memory fired twice and was wrong both times, posting an HDMI cable to the books as a
  USB-C charger in 84 ms for nothing. The model is now always asked, and exemplars that
  agree with its answer halve the doubt left in it, once per neighbour, capped at 0.99.
  Exemplars that disagree are a log line. The single vote rule and the `method = memory`
  final path are gone, the identification row still records the neighbours and their
  distances for the evidence drawer, and `local_share` now counts QR tags only, which is a
  smaller number and an honest one.
- PLAN.md 21a item 24. Every seeded row in `catalog.csv` carries `mass_prior_n = 3`, so the
  scale counts from the first toss instead of never. `MassPrior.usable` needs three
  weighings and every row shipped with one. Lane K re-decided 68 live calls with nothing
  changed but this number: 83.8 percent to 92.6 at effort `none`. The means and the
  variances are untouched. A round's cost is now summed across the event's stages rather
  than read off the last identification row, because the fusion stage writes a row of its
  own and it costs nothing.
- PLAN.md 21a item 25. The value estimate is off the critical path. The ticket is priced,
  posted and published as soon as identification is final, with "Working out value" where
  the figure goes, and the estimator then runs and a second pass publishes the figure to
  all three surfaces. A catalog item with a price is answered once, as before. An estimate
  that lands after the label changed is dropped.
- PLAN.md 21a item 26. A call on the fast or priority queue is billed at twice the standard
  rate, so `cost_microusd` multiplies by two and the usage row records which queue served
  it. Every fast call before this read at about half what it really cost.
- PLAN.md 21a item 27. The vision request's `label` is an enum of the catalog plus
  "unknown", built at request time, and so is every candidate's. The model cannot name
  something the books have no row for, and it can say it does not know, which opens the
  ask. The adapter checks the reply against the same list and asks once more before giving
  up, because a wall that only exists in somebody else's process is not a wall.
- PLAN.md 21a item 28. The decision reads what being wrong would cost. When the top two
  candidates have the same class, the same regulatory flags and the same material mix, the
  entry, the tax and the carbon come out identical either way, so the top one is taken on
  confidence alone and nobody is asked to tell a cable from a cable. When they differ in
  any of the three, the margin rule stands and it asks. The branch is logged and marked in
  `posterior_json` under `same_treatment`, a key no validated label could ever be.

## 2026-09-19, lane i: the M1 to M5 acceptance pass and hardening

- PLAN.md 21a item 17. Repair is offered when the condition is `broken`, or when it
  is `unknown` and the repair estimate comes in under half the replacement cost
  (`backend/app/engine/tax.py`). Before this a nine dollar charger's best option was
  "repair it", which is the rule as section 10 wrote it but reads as nonsense on the
  bin.
- PLAN.md 21a item 18. `EventSummary` carries `is_estimate`, true when the item
  record's fair market value came from a model estimate. One flag on the row the tape
  already reads, so an estimate is marked without a second request.
- PLAN.md 21a item 19. `sim/run_scenario.py` waits 7 seconds between tosses by
  default, because a real vision call takes about 2 and the result has to land on the
  bin before the next item does.
- `scripts/acceptance.py` runs a scenario against its own backend on ports 9443 and
  9000, with its own database and the stub provider forced on whatever the .env says,
  and prints fifteen checks covering M1, the readable parts of M3, and M5. It reads
  the LCD boxes back out of the bin simulator's own log rather than trusting the
  backend to say it published them. The one register row the tagged keyboard needs is
  written through `POST /api/assets` and printed as a fixture, because
  `assets_seed.csv` is still waiting on the team's real prices.
- Eight test files under `backend/tests/test_acceptance_*.py`: M2 on three live
  sockets, M3 through the bin socket, the M4 soak with scripted corrections in two
  configurations, a clean close and two ways of losing a ticket, the three PLAN.md
  rule 6 degradation cases, the attack set posted at the running API, the memory
  accept rule, and every line the bin can draw.
- `backend/app/api/sim.py` puts an empty bin in the frame ring behind an injected
  toss. One frame is not a crop, so before this every ticket made from the dashboard's
  demo button had an empty crop file, no exemplar was ever stored from that path, and
  memory could not recognise anything tossed twice.
- `backend/app/identify/memory.py` accepts a neighbour within 0.005 cosine distance on
  its own. The four of five vote needs four confirmed exemplars of a label before it
  will answer, which made PLAN.md section 20 M2 false the moment the table held five
  rows. The vote still governs everything further away, and `memory_max_dist` is
  unchanged.
- `backend/app/main.py` answers a refused request with one sentence instead of
  FastAPI's default body, which repeated every rejected field verbatim and handed a
  hostile string back to whatever draws the error. The full reason goes to the log.
- `backend/app/pipeline.py` draws USB, USB-C, HDMI and the rest in capitals. The bin
  was showing "Usb-c charger".

## 2026-09-19, lane h: hardware readiness for the bin

- `hardware/uno_q/bridge.py` is the Linux-side program for the UNO Q. It holds the
  socket to the backend with reconnect and backoff, sends `hello` then `weight` at
  15 Hz with device milliseconds, answers every `ping` with a `pong`, and passes
  `screen` and `tare` straight through to a display. Plain Python 3.9 or newer, the
  standard library and `websockets`, one file to copy to the board.
- The weight source and the display are adapters, so the same program runs three
  ways. `BridgeWeightSource` and `BridgeDisplay` call the sketch through Arduino's
  router bridge (`from arduino.app_utils import Bridge`, then `Bridge.call` for a
  reading and `Bridge.notify` for a screen). `SerialWeightSource` and `SerialDisplay`
  carry the same JSON over a serial port, for the case where the board ends up on a
  plain serial link. `FakeWeightSource` and `PrintDisplay` are a noisy baseline with
  scripted tosses and the simulator's own LCD text box, so the whole program runs on
  the laptop today.
- `hardware/uno_q/sketch/binbooks_bin.ino` is the microcontroller side. It reads an
  HX711 load cell amplifier with a calibration factor and a tare offset, exposes
  `read_grams`, `tare` and `show_screen` to the Linux side, and draws the five screens
  of DESIGN.md section 7 on a 240x320 portrait panel through Adafruit GFX. The driver
  is a compile-time choice between ILI9341 and ST7789, the tone colours are the
  DESIGN.md hex values converted to RGB565 with the source hex in a comment, and the
  bin shows offline on its own after five seconds of silence, which is the only
  decision it makes without being told.
- Every pin, the calibration factor and the amplifier's sample rate sit in
  `hardware/uno_q/sketch/bin_config.h`, each marked `NEEDS_HARDWARE_CHECK` with the
  question it waits on. Nothing else in the sketch names a pin.
- `hardware/uno_q/test_bridge_on_laptop.py` is the proof. It starts a backend on free
  ports with its own database, runs the bridge with the fake scale, types two tosses
  and a bag change, and checks that the backend created the three events and that the
  display drew the offline, idle and thinking screens.
- `hardware/README.md` is the build guide: what to install, how to join the laptop's
  hotspot, the exact command, the wiring table, the calibration procedure, what each
  screen shows, a checklist for before the demo, and the six questions still open.
- `hardware/find_laptop_ip.ps1` prints the address to point the bin at, preferring the
  mobile hotspot adapter over Wi-Fi, and says so when the hotspot is off.
- `firmware_contract.md` gains a "How to connect" section: the URL, why the bin uses
  plain HTTP on port 8000 rather than the self-signed 8443, hello first, and the five
  second ping timeout. Every JSON example above it is untouched.

## 2026-09-19, lane d part 2: the dashboard on the real backend

- `frontend/lib/types.ts` no longer restates a backend field. Every wire type is
  re-exported from `contracts/api-types.ts`, and the socket union is built from the
  generated `Ui*` interfaces so `message.type` narrows.
- New `frontend/lib/derive.ts`: the shapes the screens make out of the contract,
  as pure functions with 25 unit tests. The ticket figure, the estimate lines and
  their sources, the weight trace and its shaded step, the evidence bundle, the
  close report out of its open totals map, and the check names.
- The product name now comes from the root `brand.json`. `frontend/brand.json` is
  gone, and `pnpm check:brand` fails the build if the name is written out anywhere
  under `/frontend`.
- Every hook points at a real route: `/api/summary`, `/api/events`,
  `/api/events/{id}`, `/api/journal` (entries and the trial balance in one read),
  `/api/assets`, `/api/metrics/rounds` (rounds and what it learned),
  `/api/settings`, `/api/close/latest`, `/api/setup`.
- Writes are wired: answering an ask and correcting a label post `CorrectionCreate`,
  "Void ticket" posts to `/api/events/{id}/void`, thresholds patch `/api/settings`
  with `tone_co2e_kg` alongside them, "Run close" posts a `CloseRequest` over the
  period the tickets cover, and "Start new round" is back on Learning.
- `lib/live.ts` consumes `UiMessage` exactly. The scale strip draws `UiWeight`, a
  ticket arrives on `event.created` with mass only and completes on `event.updated`,
  asks open and resolve, the header totals are written straight from
  `metrics.updated`, and the bin and phone lines come from `device.status`.
- Tags display uppercase through `formatTag`, and the stored value stays lowercase.
- The evidence drawer names the provider and model that served an identification,
  and every estimate says where it came from.
- Recharts is gone from the dependencies.

## 2026-09-19, lane f: period close and the investigator

- `backend/app/ledger/close.py` runs a period close over the tables: write-offs by
  item, asset disposals on both bases with the Form 4797 Part II line 10 subtotal
  for abandonments, missed money split by the option that would have been best,
  the "Scope 3, Category 5 (waste generated in operations) inputs" block, and
  ghost assets with the `possible_unrecorded_asset` flags. Every figure is
  computed in Python over rows that already exist. Nothing in this module calls a
  model.
- Five self-checks, each returning pass, warn or fail with its numbers.
  `mass_conservation` draws the literal balance DESIGN.md 4.5 shows: what the
  scale lost since the last tare, adjusted for bag changes and removals, against
  the sum of the tickets, inside three sigma on the combined measurement error.
  The band never drops below `step_min_g`, because a gap smaller than the
  smallest step the scale can see cannot be a ticket anyone missed. With no tare
  row the first weight sample of the period is the tare and the check says so.
  The other four are `ledger_balance`, `register_consistency`, `unresolved_asks`
  and `low_confidence_share`.
- `backend/app/agent/` adds the investigator. It runs only when a check warns or
  fails, and it can produce two things: a short markdown note and a list of
  tickets for a person to look at. It cannot change a figure. Four read-only
  tools (`get_events`, `get_trace`, `get_bag_changes`, `get_identifications`)
  return JSON this code built, the loop is capped at eight tool calls and four
  timeouts of wall clock, and the reply is validated to 2000 characters with HTML
  stripped and every ticket id that does not exist in the period taken out.
- The instruction text is fixed and built by code. Labels, tags and check details
  travel in one JSON data block, and a stored label is put through the label
  validator again on its way out, so a record edited by hand cannot inject. With
  no agent model configured, a deterministic note is written from the check
  numbers, so the Close page is never blank under a failed check.
- `POST /api/close` runs the close and the investigation in one request and
  returns `CloseRead`. `GET /api/close/{id}` and `GET /api/close/latest` read it
  back; with no close yet, `latest` answers 404 with a plain sentence.
- Tokens, latency and cost per investigation go through the same price table the
  identification rows use, and land in `report_json.investigation` with the
  provider and model that served the call.

## 2026-09-19, lane g: the pipeline glue and the M1 run

- `backend/app/pipeline.py` is new and is the only place the lanes meet. It builds the
  providers, the embedder and the memory index, hangs identification off the ingest
  `on_event` seam, and hangs the engine, the ledger and the three surfaces off the
  identification `on_final` seam. One toss now goes from a settled step to a posted,
  balanced journal entry with a result on the LCD, the phone and the dashboard, and every
  stage logs one line. A stage that fails is named in the log and the event keeps the last
  status it honestly earned.
- `finalise_event` loads the register row by tag or the catalog row by label, prices
  untracked objects through the estimator with the cache in front of it, builds the item
  record with the condition the vision call saw, scores and ranks every option, writes
  `item_record` and `option_score`, posts the inventory write off or the fixed asset
  disposal plus its tax memo, flags an untracked object worth more than the
  capitalisation limit, takes the asset off the register, and publishes the result.
- Answering an ask re-prices the same event. The entries already posted are reversed
  rather than deleted, so the ticket carries the first posting, its reversal and the
  corrected posting.
- The app seeds the catalog and the register on a first start when both tables are empty.
  `seed_on_start` is a new setting, on by default, so a test can start from nothing.
- `GET /api/setup` returns the `NEEDS_HUMAN` checklist from the seed files, with
  `SetupResponse` in `schemas.py` and the generated contract types regenerated.
- `backend/tests/test_pipeline_e2e.py` plays the demo scenario through the app's own
  three sockets with the stub provider and a QR tag read out of a real composited frame,
  and asserts the events, the statuses, the fixed asset disposal, the bagel ranking, the
  blocked electronics, the balanced books and the messages on every channel.
- The QR reader now only reads the after and peak frames, and only matches an asset that
  is still on the register, so a tag left lying in the bin cannot claim every later toss.
- The header count on `/api/summary` counts tosses, which is what the dashboard calls it.
  A bag going out is not something anyone threw away.
- The scenario files name catalog items, so the stub provider can answer them. A tagged
  step no longer queues an expectation, because its tag decides before any provider runs.

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
