# The bin as an Arduino App

This is the folder `arduino-app-cli app start` runs on the UNO Q. It is the documented way
to reach the sketch from Python: the app runtime provides `arduino.app_utils.Bridge`, and it
already ships `websockets`, `numpy` and `cv2`, so nothing is installed on the board.

Build it from this repository and copy it over:

```
hardware\uno_q\app\python\main.py        starts bridge.py (weights and screens) and webcam_client.py
hardware\uno_q\app\python\bin.env        the laptop address, camera index, frame rate
hardware\uno_q\app\app.yaml              the app's name, no bricks
hardware\uno_q\app\sketch\sketch.yaml    the platform and the pinned libraries the sketch compiles with
```

Before copying, put `bridge.py` and `webcam_client.py` next to `main.py`, and the three files
from `hardware/uno_q/sketch/` into `sketch/` with `USE_APP_LAB_RPC` set to 1 in `bin_config.h`.
Then, over the cable:

```
adb push <folder> /home/arduino/ArduinoApps/cashbin
adb shell arduino-app-cli app start /home/arduino/ArduinoApps/cashbin
adb shell arduino-app-cli app logs /home/arduino/ArduinoApps/cashbin
```

The first start compiles the sketch on the board, flashes the microcontroller over SWD and
starts the Python side in a container. Later starts only run the Python side unless the
sketch changed.
