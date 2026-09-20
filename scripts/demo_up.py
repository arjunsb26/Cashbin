"""Bring the whole demo up with one command, and keep it up.

It starts the backend, builds and starts the dashboard, points the webcam at the bin
and runs the bin simulator, checks each one answered, then sits there watching. Type
`toss 150` and the scale takes the weight. Ctrl+C stops everything.

    uv run --project backend python scripts/demo_up.py
    scripts\\demo_up.ps1 --no-sim

Every child writes a full log under `runs/<timestamp>/`, so a crash leaves evidence.
The console only shows the lines a person needs while the demo is running.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent

HEALTH_URL = "http://localhost:8000/api/health"
DASHBOARD_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"
PHONE_SOCKET = "ws://localhost:8000/ws/phone"
BIN_SOCKET = "ws://localhost:8000/ws/bin"
HOTSPOT_PREFIX = "192.168.137."

BACKEND_TRIES = 3
HEALTH_WAIT_S = 45.0
DASHBOARD_WAIT_S = 90.0
WATCH_PERIOD_S = 5.0
WATCH_RETRY_S = 1.0
WATCH_MISSES = 3

ERROR_WORDS = re.compile(r"Traceback|ERROR|Error:|error -|FATAL|WinError", re.IGNORECASE)


def loud(line: str) -> bool:
    """Echo a line from a quiet child only when it reads like trouble."""
    return bool(ERROR_WORDS.search(line))


def not_driver_noise(line: str) -> bool:
    """Camera drivers and OpenCV both write bracketed lines. They belong in the log only."""
    return not line.lstrip().startswith("[")


def everything(line: str) -> bool:
    return True


class Child:
    """One process the launcher owns: started, teed to a log, stopped cleanly."""

    def __init__(
        self,
        name: str,
        argv: list[str],
        log_path: Path,
        cwd: Path = REPO_DIR,
        env: dict[str, str] | None = None,
        takes_typing: bool = False,
        echo: Callable[[str], bool] = loud,
    ) -> None:
        self.name = name
        self.argv = argv
        self.log_path = log_path
        self.cwd = cwd
        self.env = env
        self.takes_typing = takes_typing
        self.echo = echo
        self.process: subprocess.Popen[str] | None = None
        self._pump: threading.Thread | None = None
        self._tail: list[str] = []
        self._lock = threading.Lock()

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process is not None else None

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        environment = dict(os.environ)
        if self.env:
            environment.update(self.env)
        self.process = subprocess.Popen(
            self.argv,
            cwd=str(self.cwd),
            env=environment,
            stdin=subprocess.PIPE if self.takes_typing else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._pump = threading.Thread(target=self._drain, name=f"log-{self.name}", daemon=True)
        self._pump.start()

    def _drain(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        with self.log_path.open("a", encoding="utf-8") as handle:
            for line in process.stdout:
                text = line.rstrip("\r\n")
                handle.write(text + "\n")
                handle.flush()
                with self._lock:
                    self._tail.append(text)
                    del self._tail[:-40]
                if text and self.echo(text):
                    print(f"{self.name}: {text}", flush=True)

    def tail(self) -> str:
        with self._lock:
            return "\n".join(self._tail)

    def send(self, line: str) -> None:
        if self.process is None or self.process.stdin is None:
            return
        try:
            self.process.stdin.write(line.rstrip("\n") + "\n")
            self.process.stdin.flush()
        except OSError:
            print(f"{self.name} is not listening any more", flush=True)

    def stop(self, grace: float = 5.0) -> None:
        """Stop the child and everything it started.

        `pnpm start` is a shell that starts Next in a second process, and terminating
        the shell on Windows leaves Next holding port 3000, so the next launch cannot
        bind it. Killing the tree is the only stop that actually stops. Windows has no
        polite kill anyway: terminate() there is TerminateProcess.
        """
        process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                process.terminate()
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            process.kill()
        except OSError:
            pass


def http_ok(url: str, timeout: float = 2.0) -> str | None:
    """Fetch a URL and give back the body, or None if it did not answer."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status >= 400:
                return None
            return str(response.read(4096).decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def wait_until(url: str, what: str, limit: float, child: Child | None = None) -> str | None:
    """Poll a URL until it answers, saying how long it has been, so nobody wonders."""
    started = time.monotonic()
    said = 0.0
    while time.monotonic() - started < limit:
        body = http_ok(url)
        if body is not None:
            print(f"{what} answered after {time.monotonic() - started:.1f} s", flush=True)
            return body
        if child is not None and not child.alive():
            print(f"{what} stopped before it answered", flush=True)
            return None
        waited = time.monotonic() - started
        if waited - said >= 3.0:
            said = waited
            print(f"waiting for {what}, {waited:.0f} s", flush=True)
        time.sleep(0.4)
    print(f"{what} did not answer in {limit:.0f} s", flush=True)
    return None


def local_addresses() -> list[str]:
    """Every IPv4 this laptop holds right now. No shelling out, so it is cheap to poll."""
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(str(info[4][0]))
    except (OSError, ValueError):
        pass
    return sorted(found)


def route_address() -> str | None:
    """The address a packet to the internet would leave from, which is the Wi-Fi one."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        return None
    try:
        probe.connect(("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return None
    finally:
        probe.close()


def hotspot_address(addresses: list[str]) -> str | None:
    for address in addresses:
        if address.startswith(HOTSPOT_PREFIX):
            return address
    return None


def visible_host() -> tuple[str, bool]:
    """The address to hand the phone and the bin, and whether it is the hotspot."""
    addresses = local_addresses()
    hotspot = hotspot_address(addresses)
    if hotspot:
        return hotspot, True
    route = route_address()
    if route and not route.startswith("127."):
        return route, False
    usable = [a for a in addresses if not a.startswith(("127.", "169.254."))]
    return (usable[0] if usable else "localhost"), False


def newest_source(roots: list[Path]) -> float:
    """The most recent mtime under the dashboard's source folders."""
    newest = 0.0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                newest = max(newest, path.stat().st_mtime)
    return newest


def dashboard_needs_build(frontend: Path) -> bool:
    marker = frontend / ".next" / "BUILD_ID"
    if not marker.exists():
        return True
    sources = [frontend / "app", frontend / "components", frontend / "lib"]
    return newest_source(sources) > marker.stat().st_mtime


def pnpm() -> str | None:
    return shutil.which("pnpm") or shutil.which("pnpm.cmd")


class Launcher:
    """Owns every child, brings them up in order, and watches the backend."""

    def __init__(self, args: argparse.Namespace, run_dir: Path) -> None:
        self.args = args
        self.run_dir = run_dir
        self.backend: Child | None = None
        self.dashboard: Child | None = None
        self.webcam: Child | None = None
        self.bin_sim: Child | None = None
        self.stopping = threading.Event()
        self.had_hotspot = False
        self.restarts = 0

    # Starting

    def start_backend(self) -> bool:
        """Start the backend, retrying when Windows refuses a loopback socket."""
        for attempt in range(1, BACKEND_TRIES + 1):
            child = Child(
                "backend",
                [sys.executable, "-u", str(REPO_DIR / "scripts" / "run_backend.py")],
                self.run_dir / "backend.log",
            )
            child.start()
            print(f"backend starting, pid {child.pid}", flush=True)
            if wait_until(HEALTH_URL, "the backend", HEALTH_WAIT_S, child) is not None:
                self.backend = child
                return True
            tail = child.tail()
            child.stop()
            if "10013" in tail and attempt < BACKEND_TRIES:
                print(
                    "Windows refused the socket with error 10013. Starting the backend again.",
                    flush=True,
                )
                time.sleep(1.5)
                continue
            print("the backend would not come up, see backend.log in the run folder", flush=True)
            if tail:
                print(tail[-600:], flush=True)
            return False
        return False

    def start_dashboard(self) -> bool:
        frontend = REPO_DIR / "frontend"
        runner = pnpm()
        if runner is None:
            print("pnpm is not on the path, so the dashboard cannot start", flush=True)
            return False
        env = {"NEXT_PUBLIC_API_URL": API_URL}
        if dashboard_needs_build(frontend):
            print("building the dashboard, this takes a minute", flush=True)
            log = self.run_dir / "dashboard-build.log"
            with log.open("w", encoding="utf-8") as handle:
                built = subprocess.run(
                    [runner, "build"],
                    cwd=str(frontend),
                    env={**os.environ, **env},
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            if built.returncode != 0:
                print(f"the dashboard build failed, see {log.name} in the run folder", flush=True)
                return False
            print("dashboard built", flush=True)
        else:
            print("the dashboard build is current, not rebuilding", flush=True)
        child = Child(
            "dashboard",
            [runner, "start"],
            self.run_dir / "dashboard.log",
            cwd=frontend,
            env=env,
        )
        child.start()
        print(f"dashboard starting, pid {child.pid}", flush=True)
        if wait_until(DASHBOARD_URL, "the dashboard", DASHBOARD_WAIT_S, child) is None:
            child.stop()
            return False
        self.dashboard = child
        return True

    def start_webcam(self) -> None:
        child = Child(
            "camera",
            [
                sys.executable,
                "-u",
                str(REPO_DIR / "hardware" / "webcam_client.py"),
                "--url",
                PHONE_SOCKET,
                "--camera",
                str(self.args.camera),
            ]
            + (["--preview"] if self.args.preview else []),
            self.run_dir / "webcam.log",
            echo=not_driver_noise,
        )
        child.start()
        self.webcam = child
        print(f"camera starting, pid {child.pid}", flush=True)

    def start_bin_sim(self) -> None:
        child = Child(
            "bin",
            [sys.executable, "-u", str(REPO_DIR / "sim" / "bin_sim.py"), "--url", BIN_SOCKET],
            self.run_dir / "bin_sim.log",
            takes_typing=True,
            echo=everything,
        )
        child.start()
        self.bin_sim = child
        print(f"bin simulator starting, pid {child.pid}", flush=True)

    # Telling the person where everything is

    def banner(self) -> str:
        host, on_hotspot = visible_host()
        self.had_hotspot = on_hotspot
        camera = "off" if self.args.no_camera else f"index {self.args.camera}, 640 px, about 8 fps"
        lines = [
            "",
            "The demo is up.",
            "",
            f"  Dashboard   {DASHBOARD_URL}",
            f"  Phone       https://{host}:8443/phone",
            f"  Bin         ws://{host}:8000/ws/bin",
            f"  Camera      {camera}",
            f"  Logs        {self.run_dir}",
            "",
        ]
        if not on_hotspot:
            lines.append("  The mobile hotspot is off, so that is the Wi-Fi address.")
            lines.append("")
        lines += [
            "The phone will warn about the certificate. Tap Advanced, then continue.",
            "",
            "Type here:",
            "  toss 150     put a 150 g item on the scale",
            "  remove 150   take it back off",
            "  bag          empty the bin",
            "  tare         zero the scale",
            "  quit         stop everything",
            "",
        ]
        return "\n".join(lines)

    # Watching

    def watch(self) -> None:
        """Poll health every five seconds. Once a poll misses, look again every second,
        so three misses in a row is a verdict in seconds rather than most of a minute."""
        misses = 0
        wait = WATCH_PERIOD_S
        while not self.stopping.wait(wait):
            if http_ok(HEALTH_URL) is not None:
                misses = 0
                wait = WATCH_PERIOD_S
            else:
                misses += 1
                wait = WATCH_RETRY_S
                if misses >= WATCH_MISSES:
                    misses = 0
                    wait = WATCH_PERIOD_S
                    self.restart_backend()
            self.check_hotspot()

    def restart_backend(self) -> None:
        if self.stopping.is_set():
            return
        self.restarts += 1
        print(
            f"the backend stopped answering, starting it again (restart {self.restarts})",
            flush=True,
        )
        if self.backend is not None:
            self.backend.stop()
        if not self.start_backend():
            print("the backend would not come back. Type quit and read the log.", flush=True)
            return
        print("the backend is back. The camera reconnects on its own.", flush=True)
        if self.bin_sim is not None:
            # The bin simulator holds one socket and does not come back after it drops,
            # so the launcher gives it a new process. The real bin reconnects itself.
            self.bin_sim.stop()
            self.start_bin_sim()

    def check_hotspot(self) -> None:
        now = hotspot_address(local_addresses()) is not None
        if self.had_hotspot and not now:
            print(
                "the mobile hotspot went off, which is why the phone dropped. "
                "Turn it back on in Settings, Network and internet, Mobile hotspot.",
                flush=True,
            )
        elif now and not self.had_hotspot:
            print("the mobile hotspot is on again", flush=True)
        self.had_hotspot = now

    # Typing

    def handle(self, line: str) -> bool:
        """One typed line. False means stop."""
        word = line.strip()
        if not word:
            return True
        head = word.split()[0].lower()
        if head in {"quit", "exit", "stop"}:
            return False
        if head in {"help", "?"}:
            print(self.banner(), flush=True)
            return True
        if head == "status":
            self.print_status()
            return True
        if head in {"toss", "remove", "take", "bag", "bag_change", "tare"}:
            if self.bin_sim is None:
                print("the bin simulator is not running, so there is no scale to move", flush=True)
            else:
                self.bin_sim.send(word)
            return True
        print("commands: toss <grams>, remove <grams>, bag, tare, status, quit", flush=True)
        return True

    def print_status(self) -> None:
        rows = [
            ("backend", self.backend),
            ("dashboard", self.dashboard),
            ("camera", self.webcam),
            ("bin", self.bin_sim),
        ]
        for name, child in rows:
            if child is None:
                print(f"  {name:<10} not started", flush=True)
            else:
                state = f"running, pid {child.pid}" if child.alive() else "stopped"
                print(f"  {name:<10} {state}", flush=True)
        print(f"  health     {'ok' if http_ok(HEALTH_URL) else 'no answer'}", flush=True)

    def stop_all(self) -> None:
        self.stopping.set()
        for child in (self.webcam, self.bin_sim, self.dashboard, self.backend):
            if child is not None:
                child.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the whole demo and keep it up.")
    parser.add_argument("--camera", type=int, default=0, help="capture device index")
    parser.add_argument("--no-camera", action="store_true", help="do not start the webcam")
    parser.add_argument("--no-sim", action="store_true", help="do not start the bin simulator")
    parser.add_argument("--preview", action="store_true", help="show the camera in a window")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = REPO_DIR / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"logs under {run_dir}", flush=True)

    launcher = Launcher(args, run_dir)
    try:
        if not launcher.start_backend():
            launcher.stop_all()
            return 1
        if not launcher.start_dashboard():
            launcher.stop_all()
            return 1
        if not args.no_camera:
            launcher.start_webcam()
        if not args.no_sim:
            launcher.start_bin_sim()
        print(launcher.banner(), flush=True)
        watcher = threading.Thread(target=launcher.watch, name="watchdog", daemon=True)
        watcher.start()
        while True:
            try:
                line = input()
            except EOFError:
                while not launcher.stopping.is_set():
                    time.sleep(0.5)
                break
            if not launcher.handle(line):
                break
    except KeyboardInterrupt:
        print("", flush=True)
    finally:
        print("stopping everything", flush=True)
        launcher.stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
