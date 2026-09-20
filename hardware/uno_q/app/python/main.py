"""The bin's Linux side, started by Arduino App Lab.

Two programs, one app. The bridge talks to the sketch over the App Lab link and to the
laptop over a socket; the webcam client streams frames to the laptop's phone socket. The
webcam runs as a child process so a camera that is not plugged in cannot take the scale
down with it. Settings come from bin.env beside this file, so the laptop address is one
line to change.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


settings = read_env(HERE / "bin.env")
laptop_ip = settings.get("LAPTOP_IP", "192.168.137.1")
laptop_port = settings.get("LAPTOP_PORT", "8000")
camera_index = settings.get("CAMERA_INDEX", "0")
camera_fps = settings.get("CAMERA_FPS", "8")
want_webcam = settings.get("WEBCAM", "1") != "0"

bridge_url = f"ws://{laptop_ip}:{laptop_port}/ws/bin"
phone_url = f"ws://{laptop_ip}:{laptop_port}/ws/phone"


def start_webcam() -> subprocess.Popen[bytes] | None:
    if not want_webcam:
        return None
    command = [
        sys.executable,
        str(HERE / "webcam_client.py"),
        "--url",
        phone_url,
        "--camera",
        camera_index,
        "--fps",
        camera_fps,
    ]
    return subprocess.Popen(command)


def main() -> int:
    import bridge

    print(f"bin bridge to {bridge_url}, webcam to {phone_url}", flush=True)
    webcam = start_webcam()
    try:
        argv = ["--url", bridge_url, "--source", "bridge"]
        while True:
            code = bridge.main(argv)
            print(f"bridge exited {code}, starting again in 2 s", flush=True)
            time.sleep(2)
            if webcam is not None and webcam.poll() is not None:
                print("webcam exited, starting it again", flush=True)
                webcam = start_webcam()
    finally:
        if webcam is not None and webcam.poll() is None:
            webcam.terminate()


if __name__ == "__main__":
    sys.exit(main())
