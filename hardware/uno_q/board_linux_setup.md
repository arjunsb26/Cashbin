# The UNO Q's Linux side, start to finish

The bin is two computers on one board. This page is the second one: the Debian system on
the Qualcomm side, which runs `bridge.py` and holds the socket to the laptop. The
microcontroller side is `sketch/`, and the laptop flashes it with `flash.ps1`.

Everything below was researched before the board arrived. Every command is from Arduino's
own documentation, cited at the bottom. The four marked `NEEDS_HARDWARE_CHECK` are the
ones nobody can answer from a laptop.

## 1. First boot, once

Plug the board into the laptop with USB-C and open Arduino App Lab. The first-run setup
asks for a board name and a Linux password, and it turns SSH on by itself. Write both
down. The Linux user is always `arduino`.

Until that setup is finished the factory login is `arduino` / `arduino`. After it, the
password is the one you chose.

## 2. Get a shell

Three ways in, best first.

**Over the network, once the board is on the hotspot.** `<boardname>` is the name typed
during setup.

```
ssh arduino@<boardname>.local
```

**Over the USB cable, no network needed.** `adb` came with the board core this repo
already installed, so there is nothing to download:

```
C:\Users\nisni\AppData\Local\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe devices
C:\Users\nisni\AppData\Local\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe shell
```

This is the one that works when the wifi does not, so try it first on the day.

**App Lab's own terminal**, in the single board computer view. Fine for one command, poor
for editing.

## 3. Join the laptop's hotspot

Turn the hotspot on first, on the laptop, in Settings, Network and internet, Mobile
hotspot. Then on the board:

```
sudo nmcli d wifi connect <hotspot name> password <hotspot password>
nmcli device
```

`nmcli device` shows `wlan0` as `connected` when it worked. To drop it again:

```
sudo nmcli d disconnect wlan0
```

On a Windows hotspot the laptop is almost always `192.168.137.1`. Check it with
`hardware\find_laptop_ip.ps1` on the laptop, which prints the address and the whole
command to run on the board.

## 4. Install what the bridge needs

```
sudo apt update
sudo apt install -y python3-pip
python3 -m pip install websockets
```

Debian 12 and newer refuse that last one with a message about an externally managed
environment. Two ways past it, either is fine:

```
sudo apt install -y python3-websockets
```

or a virtual environment, which is the safer of the two because it cannot disturb
anything the board already depends on:

```
python3 -m venv ~/binenv
~/binenv/bin/pip install websockets
```

With the virtual environment, every `python3 bridge.py` below becomes
`~/binenv/bin/python3 bridge.py`.

## 5. Copy the bridge over

`bridge.py` is one file and imports nothing but the standard library and `websockets`.
From the laptop, in this repository:

```
scp hardware\uno_q\bridge.py arduino@<boardname>.local:/home/arduino/bridge.py
```

Over the cable instead, when there is no network yet:

```
C:\Users\nisni\AppData\Local\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe push hardware\uno_q\bridge.py /home/arduino/bridge.py
```

## 6. Start it

```
python3 bridge.py --url ws://192.168.137.1:8000/ws/bin --source bridge
```

Port 8000 and plain `ws://`. Port 8443 is the secure one and it exists for the phone's
camera, which browsers only allow on a secure origin. The bin needs none of that.

Before the load cell is wired, the same program runs against a fake scale and you can
type tosses at it, which proves the whole path without any hardware:

```
python3 bridge.py --url ws://192.168.137.1:8000/ws/bin --source fake --commands stdin
toss 95
remove 20
bag
tare
quit
```

To have it come back after a reboot, the plain way:

```
sudo tee /etc/systemd/system/binbooks-bridge.service >/dev/null <<'EOF'
[Unit]
Description=BinBooks bin bridge
After=network-online.target

[Service]
User=arduino
WorkingDirectory=/home/arduino
ExecStart=/usr/bin/python3 /home/arduino/bridge.py --url ws://192.168.137.1:8000/ws/bin --source bridge
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now binbooks-bridge
journalctl -u binbooks-bridge -f
```

## 7. If a plain script cannot reach the sketch

`NEEDS_HARDWARE_CHECK`: this is the one real unknown. `--source bridge` needs
`from arduino.app_utils import Bridge` to find the running router. Arduino's manual says
the `arduino-router` service owns that link and that nothing else may open `/dev/ttyHS1`,
but it does not say whether a script started by hand can join it. Try it by hand first.
If the first `read_grams` times out, move the bridge into an App Lab app, which is a
folder move and not a rewrite.

An Arduino App is a folder, and Arduino's own layout is exactly the shape this repository
already uses:

```
/home/arduino/ArduinoApps/binbooks/
├── app.yaml
├── python/
│    └── main.py        is bridge.py, renamed
└── sketch/
     ├── sketch.ino     is hardware/uno_q/sketch/sketch.ino
     └── sketch.yaml
```

That is why the sketch file is named `sketch.ino` and sits in a folder called `sketch`:
it drops straight into an App with no renaming. `sketch.yaml` names the platform:

```
fqbn: arduino:zephyr:unoq
platform: arduino:zephyr
```

Then, on the board:

```
arduino-app-cli app start /home/arduino/ArduinoApps/binbooks
```

The first run compiles the sketch on the board itself and flashes the microcontroller
over SWD, so this path needs no laptop at all.

## 8. If none of that works, the escape hatch

Set `USE_APP_LAB_RPC` to 0 in `sketch/bin_config.h`, wire D0 and D1 to a USB to serial
adapter plugged into the laptop, and run the bridge on the laptop instead of the board:

```
python3 bridge.py --url ws://127.0.0.1:8000/ws/bin --source serial --serial-port COM5
```

Same protocol, same screens, no board specific call anywhere in the path. It is slower to
wire and it cannot fail in a way we have not already seen.

One thing to know before wiring: on this core `Serial` is not a wire. The board's device
tree gives it an `arduino,router-serial` node, so the core makes `Serial` the App Lab
console and pushes the first hardware UART, the one on D0 and D1, to `Serial1`. That is
read out of the core's own header, not guessed, and it is why `bin_config.h` sets
`BIN_SERIAL` to `Serial1`.

## 10. The webcam, on the board

The bin needs an eye over it and the Brio is plugged into the board's own USB, so the
camera runs on the board and there is no cable to the laptop at all. `webcam_client.py` is
the phone page rewritten as a script: it opens the camera, sends about eight JPEG frames a
second to `/ws/phone`, and prints every result and ask that comes back.

Install OpenCV. The packaged build is the one to want on this board, because it is built
for aarch64 already and pip would otherwise try to compile:

```
sudo apt install -y python3-opencv
```

If apt does not have it, the wheel instead. `-headless` is the right one here: the board
has no screen, and the headless build skips the window libraries that would fail anyway.

```
python3 -m pip install opencv-python-headless numpy
```

The same externally managed refusal from section 4 applies, so with a virtual environment
it is `~/binenv/bin/pip install opencv-python-headless numpy` and every `python3` below
becomes `~/binenv/bin/python3`.

Copy the file over the same way as `bridge.py`:

```
scp hardware\webcam_client.py arduino@<boardname>.local:/home/arduino/webcam_client.py
```

Find the Brio. Plug it in, then:

```
python3 webcam_client.py --list
```

It opens every index up to six and prints the ones that give a frame, with the resolution
of each, which is how you tell the Brio from anything else on the bus. `v4l2-ctl
--list-devices` gives the same answer with names attached if `v4l-utils` is installed.

Then point it at the bin and leave it running. `<laptop>` is the address from
`find_laptop_ip.ps1`, almost always `192.168.137.1` on the hotspot:

```
python3 webcam_client.py --url ws://192.168.137.1:8000/ws/phone --camera 0
```

Port 8000 and plain `ws://`, the same as the bridge. The certificate on 8443 exists for a
phone browser and this is not one.

Three things worth knowing.

The capture backend picks itself by operating system, Video4Linux here and DirectShow on
the laptop, so there is no flag to remember. `--api v4l2` forces it if something odd
happens.

`--preview` is a laptop feature and turns itself off here. It needs a window toolkit and a
display, the board has neither, and the script says "no window toolkit here, running
without the preview" once and carries on. That line is not an error.

Unplugging the camera is not fatal. The client says so once and retries the open every two
seconds, while the socket reconnects with backoff behind it.

## 11. Bring the whole board up with one command

`board_up.sh` starts both halves, the bridge and the webcam, each in a loop that restarts
it if it dies, with a log per program. `board_down.sh` stops them. Neither needs an
argument once `board.env` has the laptop's address in it.

```
scp hardware\uno_q\board_up.sh hardware\uno_q\board_down.sh hardware\uno_q\board.env arduino@<boardname>.local:/home/arduino/
chmod +x ~/board_up.sh ~/board_down.sh
```

Put the laptop's address in `board.env`, or pass it as the first argument, which wins:

```
./board_up.sh 192.168.137.1
./board_up.sh                 # reads LAPTOP_IP from board.env
./board_down.sh
```

Logs land in `~/binbooks/logs/`, one file each, and `board_up.sh` prints the two commands
worth knowing:

```
tail -f ~/binbooks/logs/bridge.log
tail -f ~/binbooks/logs/webcam.log
```

To have it come up on power, a user unit, which needs no root:

```
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/binbooks.service <<'EOF'
[Unit]
Description=BinBooks bin, bridge and webcam
After=network-online.target

[Service]
Type=forking
ExecStart=/home/arduino/board_up.sh
ExecStop=/home/arduino/board_down.sh
RemainAfterExit=yes

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now binbooks
sudo loginctl enable-linger arduino
```

That last line is the one people forget. Without it a user unit stops when the last login
ends, so the bin would die the moment you closed the SSH window. With it, the board runs
the service from boot with nobody logged in.

The plainer alternative, if systemd is being difficult at two in the morning:

```
crontab -e
@reboot sleep 20 && /home/arduino/board_up.sh >> /home/arduino/binbooks/logs/cron.log 2>&1
```

The `sleep 20` is there so the wifi has joined before the bridge starts looking for the
laptop. The bridge would reconnect anyway, but the log reads better.

## 12. What the board has to confirm

| Question | Where it bites |
|---|---|
| Does a hand started `python3 bridge.py` reach the router, or must it be an App Lab app | section 7 |
| The Linux password chosen at first boot, and the board name for `<boardname>.local` | sections 1 and 2 |
| Whether `arduino-cli upload` over USB-C works from the laptop, or whether flashing has to happen on the board | `flash.ps1` prints the fallback when it finds no port |
| Which index the Brio opens on, and whether `python3-opencv` is in the board's apt | section 10 |
| Whether the board can hold eight frames a second and the bridge at once, on wifi | watch `~/binbooks/logs/webcam.log` for dropped frames |
| The pins, the gauge's two calibration numbers and the panel controller | `sketch/bin_config.h` and README section 5 |

## Sources

- https://docs.arduino.cc/tutorials/uno-q/ssh, `ssh arduino@<boardname>.local`, SSH turned
  on by the first App Lab setup.
- https://forum.arduino.cc/t/what-is-linux-password/1415847, the Linux user is always
  `arduino`, and the factory password is `arduino` until the setup is finished.
- https://docs.arduino.cc/tutorials/uno-q/user-manual/, joining wifi with
  `sudo nmcli d wifi connect <SSID> password <PASSWORD>`, dropping it with
  `sudo nmcli d disconnect wlan0`, `adb shell` over USB, and the warning that
  `/dev/ttyHS1` "is exclusively locked by the `arduino-router` service".
- https://github.com/arduino/arduino-app-cli/blob/main/docs/user-documentation.md, the App
  folder layout with `app.yaml`, `python/main.py` and `sketch/sketch.ino`, and that user
  apps live under `/home/arduino/ArduinoApps`.
- https://shawnhymel.com/3074/how-to-use-the-command-line-cli-with-the-arduino-uno-q/,
  `arduino-app-cli app start`, `platform: arduino:zephyr` in `sketch.yaml`, and that the
  first run compiles on the board and flashes the microcontroller over SWD.
- https://peps.python.org/pep-0668/, the externally managed environment refusal that
  Debian 12 and newer give to `pip install`.
- `packages/arduino/hardware/zephyr/1.0.0/cores/arduino/zephyrSerial.h`, read on this
  laptop, for `Serial` becoming the router console and D0/D1 becoming `Serial1`.
