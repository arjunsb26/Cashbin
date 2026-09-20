# The bin, end to end

For whoever builds the bin. Everything here already talks to the backend. The work left
is wiring the load cell and the display, filling in the pins, and calibrating.

Two pieces of code:

| File | Runs on | Job |
|---|---|---|
| `uno_q/bridge.py` | the UNO Q's Linux side | reads grams, holds the socket to the laptop, passes screens back |
| `uno_q/sketch/sketch.ino` | the UNO Q's microcontroller | reads the load cell, draws the display |

Nothing on the bin decides anything. It reports grams and draws what it is told. The
laptop does the filtering, the detection and the accounting. That is deliberate: the bin
stays simple, and every bug is debuggable on a screen with a log.

## 1. What to install

The whole microcontroller toolchain is already on this laptop and needs no Arduino IDE.
`arduino-cli` lives in `D:\codering\tools\arduino-cli\`, and both flash scripts find it
there on their own. To set it up again on another machine:

```
arduino-cli core install arduino:zephyr
arduino-cli lib install "HX711 Arduino Library"
arduino-cli lib install "Adafruit GFX Library"
arduino-cli lib install "Adafruit ILI9341"
arduino-cli lib install "Adafruit ST7735 and ST7789 Library@1.10.4"
arduino-cli lib install "Arduino_RouterBridge"
```

The board is `arduino:zephyr:unoq`. What each library is for:

| Library | Listed as | Why |
|---|---|---|
| HX711 | HX711 Arduino Library, by Bogdan Necula | the load cell amplifier |
| Adafruit GFX | Adafruit GFX Library | the drawing calls |
| Panel driver | Adafruit ILI9341, or Adafruit ST7735 and ST7789 Library | the display |
| Adafruit BusIO | installed with the driver | SPI plumbing |
| Router bridge | Arduino_RouterBridge | the link to the board's Linux side |

The version pin on the ST7735 and ST7789 library is not fussiness, it is a real
incompatibility. Version 1.11.0 added a file for the ST7796S panel whose constructor names
an argument `MOSI`, and the UNO Q's variant header defines `MOSI` as a number, so the
argument list turns into nonsense and the build stops. The panel we use is not even the
ST7796S, but the Library Manager compiles every file in the folder. 1.10.4 predates that
file and builds clean. Nothing in this repository uses anything 1.11.0 added.

To build and upload, from the repository root:

```
powershell -ExecutionPolicy Bypass -File hardware\uno_q\flash.ps1
```

It prints the driver it is building for, compiles, finds the board, uploads, then watches
the port for ten seconds so the first JSON lines are on screen. `-CompileOnly` skips
everything that needs a board, which is how the sketch is checked without one.
`hardware/uno_q/flash.sh` is the same thing for a shell.

On the Linux side of the UNO Q, which has a page of its own in
`uno_q/board_linux_setup.md`:

```
sudo apt update
sudo apt install -y python3-pip
python3 -m pip install websockets
```

If pip refuses with a message about an externally managed environment, which Debian 12
and newer do by default, either use a virtual environment:

```
python3 -m venv ~/binenv
~/binenv/bin/pip install websockets
~/binenv/bin/python3 bridge.py --url ...
```

or install the packaged build with `sudo apt install python3-websockets`.

Copy `uno_q/bridge.py` to the board. It is one file with no imports beyond the standard
library and `websockets`.

## 2. Join the laptop's network

The demo runs on the laptop's mobile hotspot with the venue wifi off, so the bin, the
phone and the laptop are on one small network that nobody else is using. Turn the
hotspot on first, on the laptop, in Settings, Network and internet, Mobile hotspot.

On the board, either use the network icon in the top right of App Lab, or the command
line:

```
sudo nmcli d wifi connect <hotspot name> password <hotspot password>
nmcli device
```

The second command shows `wlan0` as connected when it worked.

## 3. Find the laptop and start the bridge

On the laptop:

```
powershell -ExecutionPolicy Bypass -File hardware\find_laptop_ip.ps1
```

It prints the address to use and the whole command to run. On the hotspot the laptop is
almost always `192.168.137.1`, so the command on the board is:

```
python3 bridge.py --url ws://192.168.137.1:8000/ws/bin --source bridge
```

Port 8000, plain `ws://`, no certificate. Port 8443 is the secure one and it exists for
the phone's camera, which browsers only allow on a secure origin. The bin needs none of
that.

Before the hardware is wired, the same program runs with a fake scale, on the board or
on any laptop, and you can type tosses at it:

```
python3 bridge.py --url ws://192.168.137.1:8000/ws/bin --source fake --commands stdin
toss 95
remove 20
bag
tare
quit
```

Every screen the backend sends is drawn as a text box in that terminal, which is the
quickest way to see the whole pipeline working without a display attached.

Settings, as flags or environment variables:

| Flag | Variable | Default |
|---|---|---|
| `--url` | `BIN_URL` | `ws://localhost:8000/ws/bin` |
| `--device` | `BIN_DEVICE` | `bin-1` |
| `--rate` | `BIN_RATE_HZ` | `15` |
| `--source` | `BIN_SOURCE` | `fake` |
| `--display` | `BIN_DISPLAY` | the same side as the source |
| `--serial-port` | `BIN_SERIAL_PORT` | none |
| `--serial-baud` | `BIN_SERIAL_BAUD` | `115200` |

## 4. Wiring

Every pin in `uno_q/sketch/bin_config.h` is a guess until you confirm it, and each one
is marked `NEEDS_HARDWARE_CHECK` with the question it is waiting on. Change them there
and nowhere else.

There are two kinds of weight sensor and the sketch reads either one. Set `WEIGHT_SOURCE`
in `bin_config.h` to `WEIGHT_SOURCE_ANALOG` or `WEIGHT_SOURCE_HX711`. The bin we are
building has the analog kind, which is the default, and only its row is wired.

| Signal | Setting | Placeholder | Which source |
|---|---|---|---|
| Load gauge output | `ANALOG_WEIGHT_PIN` | A0 | analog |
| Load cell amplifier data | `HX711_DT_PIN` | 2 | HX711 |
| Load cell amplifier clock | `HX711_SCK_PIN` | 3 | HX711 |
| Display chip select | `TFT_CS_PIN` | 10 | both |
| Display data or command | `TFT_DC_PIN` | 9 | both |
| Display reset | `TFT_RST_PIN` | 8 | both |
| Display backlight | `TFT_BACKLIGHT_PIN` | none | both |

The display's MOSI and SCK go to the board's hardware SPI pins, which the library finds
on its own. Set `USE_ILI9341` or `USE_ST7789` to 1 depending on which controller the
panel has, and leave the other at 0. It is printed on the back of most panels.

The analog gauge needs three wires and no breakout: power, ground, and its output into
`ANALOG_WEIGHT_PIN`. Feed it from the board's 3.3 V rail, not 5 V, because the converter
input does not want more than 3.3 V and there is no divider in the way.

One thing worth knowing if you ever swap to an HX711: most breakouts run at 10 samples
per second, because the RATE pin is tied low on the board. The protocol wants 10 to 20
Hz, so 10 is the floor and it works, but the step detection is noticeably better at 80.
If the breakout exposes a RATE pad, tie it to VCC and set `HX711_SPS` to 80.

## 5. Calibrate

Once, with the bin assembled, on a surface that is not moving. Both procedures take two
readings and turn them into two numbers. Which one you follow depends on `WEIGHT_SOURCE`.

### The analog load gauge, two points

The gauge puts out a voltage and the board counts it. Two readings give the line: what an
empty bin counts, and how much the count moves per gram.

1. Upload the sketch as it stands. The placeholders make it report nonsense, which is
   expected and does not matter, because the numbers you need are the raw counts.
2. Open a serial monitor on the bin and send one line:

   ```
   {"type":"calibrate"}
   ```

   It answers with a line like this, and the number you want is `counts`:

   ```
   {"type":"calibration","source":"analog","counts":2041.25,"zero":2040.00,"per_gram":1.0000,"g":1.25}
   ```

3. With the bin **empty and settled**, send `calibrate` and write the `counts` down. Call
   it `empty`.
4. Put a known mass in. A litre of water is 1000 g. A phone is near 200 g. Weigh it on a
   kitchen scale and write the real number down. Call it `mass`.
5. Send `calibrate` again and write that `counts` down. Call it `loaded`.
6. The two numbers are:

   ```
   ANALOG_ZERO_COUNTS     = empty
   ANALOG_COUNTS_PER_GRAM = (loaded - empty) / mass
   ```

7. Put both in `bin_config.h` and upload again.
8. Check it: the known mass now reads its real weight, within a gram or two, and the
   empty bin reads near zero.

Three things that save time here. `counts` going **down** as weight goes on is fine and
needs nothing changed; `ANALOG_COUNTS_PER_GRAM` simply comes out negative and the
arithmetic still works. If `counts` never rises above 1023 the converter is running at 10
bits rather than 12, which is also fine, but take both points again at that resolution
because the two numbers only mean anything together. And if `loaded` and `empty` are
within a few counts of each other, the gauge is not carrying the load: check the
mechanical mounting before touching any code.

If there is no serial adapter to hand, the same thing over the board's own link:

```
python3 -c "from arduino.app_utils import Bridge; print(Bridge.call('calibrate'))"
```

### The HX711 load cell

Once, with the bin assembled and empty, on a surface that is not moving.

1. Set `HX711_CALIBRATION` in `bin_config.h` to `1.0` and upload.
2. Let it settle. Note the number on the display. That is the raw reading for an empty
   bin, and the sketch has already zeroed it at start up, so it should sit near zero.
3. Put a known mass in the bin. A litre of water is 1000 g. A phone is near 200 g. Use
   something you can weigh on a kitchen scale and write the real number down.
4. Read the number on the display. Divide it by the real mass in grams. That result is
   the calibration factor.
5. Put it in `HX711_CALIBRATION` and upload again.
6. Check it: the known mass now reads its real weight, within a gram or two.

Write the factor somewhere other than the code as well. If the load cell is ever
unmounted and remounted, it changes, and the number on a sticky note saves ten minutes.

## 6. Tare

The sketch zeroes the scale at start up, so a bin that is empty when it is switched on
needs nothing. After that, the laptop can zero it at any time and the bin obeys at once.
A bag change is not a tare: the laptop wants to see the weight drop, because that drop
is the record that the bag went out.

## 7. What the display shows

Portrait, 240 wide by 320 tall. Five screens, and the bin never invents one.

| Screen | Background | Shows |
|---|---|---|
| idle | paper | the live weight, large |
| thinking | paper | "Weighing" and the live weight |
| result | the tone colour, filled | a line, a big figure, a second line |
| ask | paper | two lines, telling the person to look at the dashboard |
| offline | paper | "Offline" and "No connection" |

The tone colours, which the laptop chooses and the bin only obeys:

| Tone | Hex | Means |
|---|---|---|
| green | `#1F7A4D` | the best thing to do with it is the thing being done |
| amber | `#B7791F` | there is a better option than the bin |
| red | `#B3261E` | this should not go in the bin at all |
| neutral | `#FBFCFA` | no judgement, paper background with dark text |

Text is capped at 20 characters a line and 7 for the big figure. The laptop cuts to
those lengths before it sends, and the sketch cuts again, so a long word can never
spill off the panel.

If the laptop goes quiet for 5 seconds, the bin shows offline by itself. That is the
only decision it makes without being told.

## 8. Before the demo

- [ ] Hotspot on, venue wifi off, laptop address checked with `find_laptop_ip.ps1`
- [ ] Board joined to the hotspot, `nmcli device` shows `wlan0` connected
- [ ] Sketch uploaded with the real pins and the real calibration factor
- [ ] Bin empty and switched on, display reads near zero
- [ ] Bridge running, and the dashboard shows the bin as connected
- [ ] Toss something known, for example a 95 g item, and check the dashboard weight
      matches the real weight within a couple of grams
- [ ] Watch the display go from idle to thinking to a result
- [ ] Pull the network for five seconds, check the display says offline, put it back,
      check it recovers on its own
- [ ] Bag change: lift the bag out, check the dashboard records it and does not treat it
      as an item
- [ ] Power the board from something that will last the whole demo

## 9. What we still need from you

Short list. Each answer removes a `NEEDS_HARDWARE_CHECK` from the code.

1. Which load cell and which amplifier board. Capacity in kilograms, and whether the
   amplifier is an HX711 or something else. If it is not an HX711, say so early, the
   library changes.
2. Whether the amplifier board has a RATE pad, so it can run at 80 samples a second
   instead of 10.
3. Which display controller the panel has, ILI9341 or ST7789, and whether it needs a
   backlight pin driven.
4. The pins for the six signals in the wiring table.
5. Whether the Linux side of the UNO Q can reach the sketch when the bridge is started
   by hand with `python3 bridge.py`, or whether it has to be started as an App Lab app
   with `arduino-app-cli app start`. Arduino's manual says the router service owns that
   link, but it does not say whether a plain script can join it. Try it by hand first.
   If the first reading times out, we move the bridge into an App Lab app folder, which
   is a five minute change.
6. Whether the sketch compiles with the five argument screen function. If Arduino's
   bridge library rejects it, there is a one line fallback noted in the sketch.

If any of this lands differently to what is above, the serial path is the escape hatch.
Set `USE_APP_LAB_RPC` to 0 in `bin_config.h`, wire D0 and D1 to a USB to serial adapter
plugged into the laptop, and run the bridge on the laptop instead:

```
python3 bridge.py --url ws://127.0.0.1:8000/ws/bin --source serial --serial-port COM5
```

Same protocol, same screens, no board specific calls anywhere in the path.

## 10. A webcam instead of a phone

The bin needs an eye over it. A phone on a stand is the plan, and a webcam plugged into
the laptop does the same job with no second device and no certificate to accept.
`webcam_client.py` is the phone page rewritten as a script: it opens the camera, sends
about eight JPEG frames a second to the same `/ws/phone` socket, and prints every result
and ask the backend sends back.

See which cameras this laptop has:

```
uv run --project backend python hardware/webcam_client.py --list
```

Then point one at the bin and leave it running:

```
uv run --project backend python hardware/webcam_client.py --camera 0
uv run --project backend python hardware/webcam_client.py --camera 0 --preview
```

`--preview` opens a small window showing exactly what is being sent, captioned with the
last result, which is how you aim it. It is off by default. `scripts/demo_up.py` starts
this client itself, so during the demo you never run it by hand.

From another machine, use the secure origin and skip verification, because the
certificate is self signed:

```
python hardware/webcam_client.py --url wss://192.168.137.1:8443/ws/phone --insecure
```

Notes worth knowing:

- Capture comes from `opencv-python-headless`, which this repo already installs. That
  build has no window support, so the preview is drawn with tkinter from the standard
  library. Nothing new to install. If you would rather have the OpenCV window, swap the
  headless build for the full `opencv-python` locally; do not add it to `pyproject.toml`.
- Unplugging the camera is not fatal. The client says so once and retries the open every
  two seconds, and the socket reconnects with backoff while it waits.
- An index that opens is not always the camera you want. On this laptop index 0 is the
  built in webcam, index 1 is a virtual camera from OBS and index 2 is the infrared
  sensor, which returns a black frame. `--list` shows the resolution of each.
