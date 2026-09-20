# Changelog

Newest first. Each lane writes under its own heading.

## 2026-09-20, lane v: the question that matters

- The camera may now say it cannot price what it is looking at. `needs_detail` on a vision
  answer means the figure turns on something a photograph cannot show: how many gigabytes
  a stick holds, how big a monitor is, whether a battery still works. It opens one
  question and decides nothing on its own.
- The question and its two to four answers are written by a cheap call at low effort under
  its own two second limit. Food and packaging are never asked about. The same label is
  asked about once a session. No model, a host that is down, or a reply a phone could not
  draw all mean the same thing: the ticket finishes without the detail.
- The answers are buttons at equal weight, because none of them is a guess the bin is
  making. The bin draws "Quick question" rather than "Not sure", which is the ordinary ask
  and a different thing.
- An answer to a question is a detail, not a label. It is filed beside the numbers on the
  identification row, it reaches the estimator as data, it keys the estimate cache, and
  the condition pair sets the item's condition. The label the camera gave stands.
- One toss may be asked at most two questions, ever.
- A toss now says what it meant above the figure rather than repeating the item's name,
  which the phone is already showing. Food reads "Wasted", a register asset "Written off",
  anything else "Worth about", and packaging leads with the CO2e it keeps out of the air.
  The words come from the one builder in `notify/lcd.py`; the second copy of that ladder
  in the pipeline is gone, and so is the copy the acceptance harness kept of line 2.
- The ticket carries that sentence with its figure in it, so a reloaded page says what the
  bin said at the time instead of working it out again.
- Something cheap that nothing is wrong with reads "Still usable" rather than "Fine to
  bin". The user's words: for a pencil it said resell, which is reasonable, but you could
  just use it.
- Food nobody priced is asked what the whole thing cost and how much of it went in, and
  the two answers multiply out to the cost basis: ten dollars and a quarter is $2.50.
  Food the catalog prices is asked nothing.
- Food is refused for donation only when somebody says it was opened. Nobody having said
  anything is not the same as opened, and refusing on that meant refusing every piece of
  food there was. Unknown is offered with the flag that puts it in front of a person.
- An empty drink can is a can, not six cents of wasted drink. Under a fifth of the unit
  mass of something mostly food or drink, the toss is the container: no cost basis, no
  journal entry, the material is what the container is made of, and the line says
  "Recycle, not trash".

- `scripts/acceptance.py --scenario demo` passes all fifteen checks. The bagel's donation
  now ranks, and the harness counts four result screens because it reads the bin's copy
  rather than a list of it typed out last week.

- A ticket that owes a person something now says so as it finishes rather than at the
  close: the donation to approve, the equipment to confirm. How long a ticket may stand
  waiting before it becomes a review task is a setting, at two minutes.
- Nothing a person reads carries a field name any more. The close memo said "fixed_asset",
  "book_loss_cents" and "bonus_100" at a finance lead, and the Trends paragraph said
  "Over 14.0 days" and "2.2195 kg", because the data block handed the model raw keys and
  raw floats and the figure rule then stopped it writing anything better. The block is now
  written the way the memo should read, labels in words and figures with their units, and
  the wall still matches on those same formatted figures.


## 2026-09-20, lane q: the dashboard for two audiences

- Five tabs, each with one job. Live and Trends answer what a person wasted. Review, Books
  and Close answer what it did to the accounts. The rail carries those five and nothing
  else: the thresholds moved into a Settings dialog at its foot, and `/kit` and `/setup`
  stay reachable by address only.
- A toss now says what it meant, in the words its class earns. A register asset reads
  "Written off, $65.00 book loss", food and anything else bought to be used up reads
  "Wasted $3.00", something that was never on the books reads "Worth about $12.00", and
  packaging reads the carbon it keeps out of the air, because a cardboard box's forty
  cents is noise. When the backend sends its own `headline` that sentence wins, split
  around its money so the figure stays the big condensed one.
- When the bin was already the right answer, the option table folds to the one row that
  settled it under the heading "Fine to bin", with the rest a click away. The landfill
  column drops below 640 px, which is what stopped the table clipping on a phone.
- The Live page lost the repeat of the tape. The three tickets before the current one were
  the tape's top three rows printed a second time and a size larger.
- Trends: totals and averages by day or by week, the five categories as bars drawn by hand,
  the computed suggestions under "What the numbers say", the model's paragraph under those,
  and the accuracy and cost lines that used to be the Learning page. The chart no longer
  runs off the side of a phone.
- Review: the open questions with their candidates answered inline, the amounts a person
  should stand behind approved or rejected with a note, and the equipment that was never on
  the register. Every action moves the row before the backend answers and puts it back with
  the backend's own sentence if it refuses. The rail item carries the open count.
- Books grew a Register sub-tab, so the journal, the register and the trial balance are
  three addresses under one heading. `/assets` and `/learning` redirect to their new homes.
- Close grew four blocks: the memo in prose under the title, a fixed asset rollforward that
  visibly foots, a book to tax reconciliation in the M-1 shape, and a Form 4797 schedule.
- An ask with no candidates is still an ask. It shows what the model thinks it saw, a box to
  type in and a way out, rather than a ticket that waits forever with nothing to click. A
  detail question ("How much does it hold?") renders as the same buttons with the question
  as the heading.

## 2026-09-20, lane t: estimates that hold still, priced rows, and words on the LCD

- The answer a person gives when the bin asks now travels into the estimate call, as a
  quoted value in the data block beside the crop, the description, the condition and
  whatever the camera read. "64 gb" is the difference between two flash drives. It is cut
  to 120 characters before it is sent, and a value that is not text is no answer at all.
- The estimate cache is one row in the settings table holding one JSON object, read once
  at start and written back on every store, rather than a row per label. A restart in the
  middle of a demo keeps every figure anybody has been shown. The key is still everything
  the estimator was told; a lookup by bare label finds the newest estimate for that label,
  which is what the ticket needs. The cache holds four hundred objects and drops the
  oldest, and it belongs to the database it was read from, so pointing the app at another
  file does not carry the old prices over.
- The four mid figures are cleaned to money a person would say before they leave the
  provider, using the engine's own steps, so the figure the bin drew is the figure the
  cache holds and the ticket repeats. Low and high keep every cent. A narrow range whose
  mid rounds past its own high takes the high with it rather than failing validation.
- Eighteen of the twenty everyday catalog rows carry a price read off a listing in
  September 2026, one unit at a time, with the URL in `price_source`. Food rows follow the
  file's own convention: cost is half the retail listing and fair market value per kilo is
  the listing. The sticker sheet and the lanyard badge have no price and say `NEEDS_HUMAN`,
  because no listing was found that priced one of the thing.
- The LCD says what a toss means before it says how much: "Wasted" over food, "Written
  off" over a tracked asset, "Worth about" over anything else, and "CO2e avoided" with a
  weight over packaging. The figure carries no minus sign, because a minus sign on the bin
  reads as a fault. Between tosses the bin shows what is in it since the last bag change,
  "In the bin", "$41.80", "2,412 g, 7 items", and an empty bin says it is empty instead of
  drawing a row of zeroes.

## 2026-09-20, lane s part 2: the analog gauge, the webcam on the board, one command up

- The bin's weight sensor is a load gauge that puts out an analog voltage, not an HX711,
  so the sketch now reads either one. `WEIGHT_SOURCE` in `bin_config.h` picks between
  `WEIGHT_SOURCE_ANALOG` and `WEIGHT_SOURCE_HX711`, and analog is the default because that
  is what the bin has. The HX711 path is kept whole, because it costs nothing and it is the
  commoner part if one has to be bought in a hurry.
- The analog read asks the converter for 12 bits, the widest the STM32U585 has, averages
  eight samples because there is no instrumentation amplifier smoothing the signal, and
  turns counts into grams with a two point line: `ANALOG_ZERO_COUNTS` and
  `ANALOG_COUNTS_PER_GRAM`. Both live in `bin_config.h` and both are marked as needing a
  measurement.
- A `calibrate` command takes those two points. Send `{"type":"calibrate"}` on the serial
  link, or call `calibrate` over the board's bridge, and it answers with the raw counts to
  write down. It is not part of the firmware contract and the backend never sends it.
- The README's section 5 now has both procedures side by side, the two point one first.
  It also says the three things that waste time: counts going down is fine and just makes
  the number negative, counts capped at 1023 means the converter fell back to 10 bits, and
  counts that barely move mean the gauge is not carrying the load.
- The webcam runs on the board now, not the laptop, because the Brio is plugged into the
  board and there is to be no cable. `webcam_client.py` picks its capture backend by
  operating system, Video4Linux on the board and DirectShow here, instead of trying
  Windows-only backends everywhere. Behaviour on the laptop is unchanged.
- `board_up.sh` starts the bridge and the webcam together, each under a loop that restarts
  it if it dies, logging to `~/binbooks/logs/`. It takes the laptop's address as an
  argument or from `board.env`. `board_down.sh` stops them and leaves nothing holding the
  camera. Both are documented with a systemd user unit and a cron line for coming up on
  power.
- Shell scripts and the two python files the board runs are pinned to Unix line endings.
  Git on Windows was about to check them out with carriage returns, which bash on Debian
  reads as part of the command, and the error it prints does not mention them.

## 2026-09-20, lane u: a slow camera answer is not a missing one

- The OpenAI client is built with `max_retries=0`. The SDK defaults to two silent retries,
  which sat inside our own five second budget and turned one slow call into three. Retrying
  is the pipeline's decision now, because only the pipeline knows what a person is looking
  at while it waits.
- A vision call that does not land in `LLM_TIMEOUT_S` gets one more go on the settled crop,
  thinking a little, with `VISION_RETRY_TIMEOUT_S` of ten seconds. The ticket stays in
  Identifying while that runs. The question only opens when the second go fails too.
- When the question does open because no model ever answered, it says so: "The camera
  answer did not arrive. What is it?", beside the model's own description if any attempt
  produced one. A bare "Which is it?" with nothing to pick is gone.
- A second call that lands after the question went out still settles the ticket, as long
  as nobody has answered. Both surfaces close the question, with `by` reading "camera".
  A person who has already answered beats the camera every time.
- `PhoneAsk` and `UiAskOpened` carry an optional `question`. Null keeps the wording the
  phone already has, so an ordinary ask is unchanged.

## 2026-09-20, lane u: the bin reads what it is about to say

- A sense gate sits between a finished ticket and the three surfaces. Once per finalised
  ticket, for an untracked object, a tagged asset, or a catalog item that is about to
  advertise an alternative, one cheap call reads the label, the description, the condition,
  the mass, the estimates with their rationales, the options on offer with their net, the
  options that were refused with the reason, and the two lines the bin is about to draw.
  It answers sensible, rewrite or veto.
- A rewrite is used only when its words survive the twenty columns the bin draws and it
  names an option the engine actually offered. Anything else keeps the words the code had.
- A veto turns a confident ticket into a question. Nothing is written, nothing is posted,
  anything an earlier pass posted is reversed, and the ask opens with the model's own
  description and Something else. That is what catches a usb stick labelled as a laptop
  charger before the bin claims it.
- The gate never leaves a ticket wordless. No model configured, a host that is down, a
  reply that will not validate and a timeout all leave the proposed words exactly as they
  were, with a log line. The verdict is filed on the identification row and shows on the
  ticket read as `sense_check`.
- Verdicts are remembered by label, class, condition and best option, so the same thing
  thrown twice is only asked about once.
- The identification read now keeps the distribution and the verdict apart. `posterior`
  holds numbers, which is what it always claimed to hold, and `sense_check` is its own
  field.

## 2026-09-20, lane o: the phone page can never get stuck

- The sheets on the phone are one state machine now: `idle`, `result`, `ask`, `adding`, one
  of them on the screen at a time. A ticket for the event already up fills that ticket in
  where it stands, a ticket for a newer event takes its place, an older one is dropped, a
  question wins over any ticket and shows at once, and an `idle` from the backend clears
  the screen. The held queue and the 2.8 s rising delay are gone, so nothing can wait
  behind a message that never comes. Every move is logged to the console with its event id.
- A ticket leaves after six seconds with no update. A ticket that arrives with no figure on
  it says "Working out the value" and keeps the screen until the figure lands, which fills
  it in and starts the six seconds. If no figure comes within eight seconds the line reads
  "Value not available" and the ticket leaves on its timer.
- A question never times out. After twenty seconds it says "Still waiting on you" rather
  than sitting there looking dead. It can be answered, or put away with "Not now", which
  sends nothing. A tap beside a ticket puts the ticket away; a tap beside a question leaves
  it alone.
- A dropped connection clears the ticket that belonged to it at once. A question survives a
  ten second blip, because the answer travels over its own request, and then goes too. The
  page sends its hello and picks the frames back up on reconnect with no reload.
- The camera comes back by itself. iOS ends the camera track when the page goes to the
  background; the page now reopens it on the way back with no tap. If the camera is refused
  at that point, the Start camera button comes back instead of a dead black screen.
- Focusing a field inside a sheet used to scroll the whole page out from under the camera,
  and with the page set to `overflow: hidden` there was no way to scroll it back: the
  camera sat high with a band of nothing under it for the rest of the session. Focus takes
  no scroll now, and anything that scrolls the page anyway is put straight back.
- A question with no candidates draws no buttons. It shows the picture, the heading, and
  what the camera saw in the model's own words on a "Looks like:" line above "Something
  else" and "Not now". A question that carries its own wording uses that as the heading in
  place of "Which is it?". Both are drawn as text, trimmed and capped, and neither is ever
  sent anywhere.
- `phone/dev/mock_server.py` has a chaos script: a ticket that arrives twice, a question
  landing on a ticket, a ticket landing under a question, the socket dying under an open
  question, and a ticket whose figure never comes. `--chaos` plays the lot for a run on a
  real phone, and `POST /api/dev/chaos` plays one named step so the screenshot run can check
  the screen after each one. The run asserts what is on the screen at every step, prints the
  whole state machine log, and writes shots `c1` to `c8`.

## 2026-09-20, lane s: build the bin firmware from the laptop

- The laptop can now compile and flash the bin sketch with no Arduino IDE anywhere.
  `arduino-cli` 1.5.2-rc.1 sits in `D:\codering\tools\arduino-cli\`, the board core is
  `arduino:zephyr` 1.0.0 and the board is `arduino:zephyr:unoq`. The winget package has no
  installer for this machine, so the toolchain came from Arduino's own Windows zip.
- The sketch compiles. All four builds are green on the real core: ILI9341 and ST7789,
  each over the serial link and over the App Lab router bridge. The largest of the four
  uses 15% of program storage and 19% of memory, so there is a lot of room left.
- The five argument `show_screen` handler was the open question from the hardware lane and
  the answer is yes. `Bridge.provide_safe` takes it, against Arduino_RouterBridge 0.4.3.
  The one string JSON fallback stays written down but is not needed.
- `Serial` on this board is not a wire. The core's own header shows the UNO Q's device tree
  giving `Serial` to the App Lab console and pushing D0 and D1 to `Serial1`, which is what
  `bin_config.h` already assumed. Confirmed rather than guessed now.
- The main sketch file is `sketch.ino` instead of `binbooks_bin.ino`. Arduino requires the
  file to be named after its folder, and Arduino's own App layout is a folder called
  `sketch` holding `sketch.ino`, so the file now drops into an App with no renaming.
- The Adafruit ST7735 and ST7789 library is pinned to 1.10.4. Version 1.11.0 added a file
  for a panel we do not use whose constructor names an argument `MOSI`, and the UNO Q
  variant header defines `MOSI` as a number, so that file cannot compile on this board.
- `hardware/uno_q/flash.ps1` and `flash.sh` compile, find the board, upload, then watch the
  port for ten seconds and print the first JSON lines. They say which driver and which
  host link they built for, and when no board is attached they say what to try instead of
  failing silently. `-CompileOnly` checks the sketch with no board at all.
- `hardware/uno_q/board_linux_setup.md` is the Linux side start to finish: the shell over
  SSH and over the bundled `adb`, joining the hotspot, installing `websockets` past
  Debian's externally managed refusal, copying the bridge, a systemd unit, and the App Lab
  app layout to fall back to. Every command is cited.

## 2026-09-20, lane p: the CFO workflow with depth, and the stats behind it

- A review queue. `review_item` holds one open question per ticket per kind, raised when
  the best option needs a person to sign it off, when a model estimate above the register
  limit is carrying real money, when something valuable and untracked went in the bin,
  when a ticket has waited longer than `review_after_s` for an answer, and when a person
  had to overrule a label the model was confident about. `GET /api/review?status=` lists
  them with the ticket's label, the amount and the reason.
- Approve keeps the entries that were posted and closes the question. Reject undoes it:
  for a donation the donate row is blocked and the ticket is re-ranked without it, so the
  close stops counting money the business will not get; for anything else the entries are
  reversed through `void_event`, the ticket goes void, and an asset that came off the
  register goes back on it. Nothing is ever deleted. Every decision carries who and when
  and writes a `correction` row with `field=review`.
- An unresolved ask carries the candidates the bin was asking about, and
  `POST /api/review/{id}/answer` sends a label to the same correction handler the phone
  uses, so answering from the queue is the same answer given anywhere else.
- A review agent. `POST /api/review/run` has it look at every open item with six read-only
  tools: the ticket, the estimate, the register, the rule, how the same label was decided
  before, and the policy thresholds. It comes back with a proposal, the lookups it made
  and what each one found. It never acts. Every figure in its reason has to appear in a
  tool result or the reason is replaced with the plain one. It may not approve a donation
  of food somebody opened, or an estimate more than ten times the catalog median for its
  class; either becomes ask_person. When a person decides, whether they agreed with the
  proposal is recorded.
- A fixed asset rollforward on the close: opening cost, additions, disposals, closing
  cost, the same four on accumulated depreciation, and net book value at both ends, per
  asset and in total. Closing equals opening plus movements, and the block says whether it
  ties rather than leaving anyone to add it up.
- A book to tax reconciliation in the M-1 shape: book loss on disposals, less the
  differences, equals the tax loss on disposals, with the reason for every gap in plain
  words (`bonus_100 taken in 2025`, `override`, `straight line, no difference`).
- A Form 4797 schedule: abandonments on Part II line 10 and sales on Part III with the
  recapture noted, each row carrying the dates, the cost, the depreciation allowed and the
  rule ids from `tax_rules.yaml`. Plain data, and the footer says what it is not.
- A close memo. One call to the agent model turns the computed totals, checks, rollforward
  and bridge into 150 to 250 words for a CFO. It may not add a figure: every sentence is
  checked against the data block and a sentence carrying a number that is not in there is
  dropped. With no model configured a deterministic memo says the same things.
- `GET /api/stats?bucket=day|week&from=&to=` totals a range into buckets: tickets, what
  was written off, book loss, estimated value, kilograms to landfill, carbon avoided,
  asks, first try accuracy, and a split by food, packaging, equipment, e-waste and other.
  Plus averages per day, three to five plain suggestions, and one paragraph joining them.
- The suggestions have a floor. Nothing is said unless the money is at least 200 cents or
  the count at least 3, a percentage never appears without its base, no sentence can name
  an option the engine did not offer for that item, and a comparison to the range before
  is only drawn when both ranges hold at least five tickets.
- The close investigator now records the lookups it made, and `CloseRead` carries them as
  `investigation_steps` beside the note.

## 2026-09-20, lane n: add a toss from the phone

- The phone page can make a toss by itself now, so a ticket can be raised without the
  scale and without a laptop terminal. A small "Add a toss" button sits at the foot of the
  live camera view, and tapping it opens a sheet in the same shape as the result sheet:
  the label "Weight in grams", the hint that the camera picture from right now is the
  photo, a numeric box that starts at 150, then Cancel and Add. Enter sends, Escape closes.
- The button is drawn only when the backend still answers `POST /api/sim/expect`. The page
  asks once at load with an empty body; a 404 leaves the button out of the page entirely,
  so the demo build shows nothing here, not a disabled control. Anything else, including a
  complaint about the empty body, counts as the route being there.
- Add posts `{"mass_g": <number>}` to `POST /api/sim/toss` and closes. The ticket comes
  back over the socket like any other toss. A 409 keeps the sheet open and shows the
  sentence the backend sent; any other failure says the toss did not go in.
- The weight is read into a number on the page before it is sent: digits and at most one
  point, above zero, at or below 100000. Nothing else leaves the box.
- The mock backend in `phone/dev/mock_server.py` now answers both routes, logs the posted
  body and sends back a ticket carrying the weight that was typed, so the whole path can be
  driven without the real backend. The screenshot run captures the sheet open
  (`11-add-toss.png`) and the ticket that comes back from a hand added toss
  (`12-add-toss-result.png`), and asserts the ticket reads the weight that was typed.

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

## 2026-09-20, lane j: what the first hands-on test found

- `sim/phone_sim.py` refuses to run a scenario that names a picture it cannot find, and says
  which flag is usually the reason. A missing asset used to be a log line and an empty bin,
  which meant every frame was a photograph of nothing, every ticket opened an ask, and the
  whole run read as a backend bug.
- An early vision call that answers "unknown" is not an answer. The settled crop, which is a
  better picture of the same thing, gets its own call. A QR tag is read off the settled
  frames before any vision answer is looked at, as it always was.
- Nothing pays for a call that cannot win. A step whose weight is going down is a bag change
  or a removal and starts nothing; a tag already in shot means no early call at all. In the
  demo_real run that took eight live calls down to six, because a request on the wire cannot
  be unsent when the step settles the wrong way.
- The timeout belongs to the toss, not to each call. An early call that has already been
  running for 700 ms gets 700 ms less, so a slow host cannot cost the wait twice.
- PLAN.md 21a item 31. LCD line 2 says what to do and what not to do in one clause:
  "Repair it, not trash". "No bin. Repair it" read as a bug to the first person who used it.
- PLAN.md 21a item 32, which reverses item 27. The catalog is what the model is told, not
  what it is allowed to say. Holding the label to an enum of the catalog made the bin answer
  "laptop charger" for a USB stick, because a wrong catalog label was the only thing it was
  allowed to say. `normalise_label` is the wall, as it always was, and the vision result
  carries a required `description` in plain words.
- PLAN.md 21a item 34. `POST /api/sim/toss` with a mass and no image makes a ticket out of
  whatever the camera can see, so the Add button works without a scale. With fewer than two
  frames it says "No camera frames yet. Start the camera first."
- PLAN.md 21a items 35 and 51. `llm_timeout_s` is 5.0. On a cellular link calls took ten and fourteen
  seconds and a person stood there holding something over a bin.
- PLAN.md 21a item 33(b). Twenty more catalog rows for the things a table actually holds,
  every material a WARM key and every mass prior deliberately wide. No price is filled in and
  all twenty say NEEDS_HUMAN, because there was no time to check twenty prices and nothing is
  invented. `/api/setup` lists them.
- PLAN.md 21a item 29. The estimator sees the item: the same picture the vision call saw,
  the description, and whatever was legible on it. It used to see the word alone, which is
  how a hundred and fifty dollar mouse came back at twelve dollars.
- PLAN.md 21a item 36. A picture somebody took on purpose is the item, so an added toss uses
  the whole newest frame rather than a diff. A hand-held phone diffed against a frame from
  two seconds earlier finds the table. And an ask offers only the model's own guesses at 0.3
  or better, and nothing at all when it had none: "laptop charger, power bank, pencil at 33
  percent each" was three catalog rows that weighed about the same.
- PLAN.md 21a item 37. "Fine to bin" unless there is something worth saying. `speak_up_cents`,
  default 100, is a live setting. A bin that argues about three cents is a bin nobody listens
  to the fourth time.
- PLAN.md 21a item 47. An estimate is the same figure twice: the cache key carries what is
  written on the thing, its condition and any detail answered about it. And the middle of
  each range is rounded to money a person would say, fifty cents under twenty dollars up to
  ten dollars above a thousand, while low and high keep every cent for the drawer.
- PLAN.md 21a item 49. A label the scale has never weighed is taken on the model's word. Mass
  fusion applies only when the top label has a usable catalog prior, and never adds a label
  the model did not offer. A battery named at 0.98 was opening an ask because catalog rows
  that merely weigh the same were being fused against it.
- PLAN.md 21a item 48, (a) to (f). One place, `engine/tax.makes_no_sense`, decides that an
  option is not a real answer, and a refused option stays on the ticket with its reason so
  the drawer shows what was considered. Resell wants five dollars, a working item and
  something that is not food or packaging. Repair wants the thing broken, twenty dollars to
  replace, and under sixty percent of that to fix. Donate wants food sealed. Recycle wants a
  material with somewhere to go. The live case: a battery now ends with trash blocked,
  recycle best and "Recycle, not trash", instead of "Repair it instead".
- PLAN.md 21a item 51, off Lane R's bench. A reply that describes the thing and then says
  "unknown" gets one more go at effort `low`, on the same picture: luna at low named the
  battery, the pen and the flash drive every time. The class is decided here and not by the
  model, because it flipped between identical crops and the class is which ledger account a
  toss posts to: the catalog decides for a label it knows, everything else is untracked
  unless the words used about it are food words. `llm_timeout_s` is 5.0, because p90 is
  3.1 s and five of sixty eight calls crossed four.

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
