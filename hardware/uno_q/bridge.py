"""The Linux-side program that puts the bin on the backend's `/ws/bin` socket.

One process, three jobs. It reads grams from a weight source, streams them to the
backend at a fixed rate, and forwards every screen command the backend sends back to a
display sink. Nothing else. All the filtering, the step detection and the accounting
happen on the laptop, exactly as the firmware contract says.

The weight source and the display sink are adapters, so the same program runs in three
places without a line changing:

    --source bridge   the MCU on the UNO Q, reached through Arduino App Lab RPC
    --source serial   a plain serial link carrying JSON lines to and from the MCU
    --source fake     a noisy baseline with scripted tosses, for the laptop

Run it on the board once the bin exists:

    python3 bridge.py --url ws://192.168.137.1:8000/ws/bin --source bridge

Run it on the laptop today, typing tosses at it:

    python3 bridge.py --url ws://127.0.0.1:8000/ws/bin --source fake --commands stdin
    toss 95
    remove 20
    bag
    tare
    quit

Requirements: Python 3.9 or newer and the `websockets` package. Nothing else. No numpy,
no pandas, no compiler. `pyserial` is needed only for `--source serial` and the program
says so rather than failing on import.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import math
import os
import random
import ssl
import sys
import threading
import time
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

LOG = logging.getLogger("bridge")

DEFAULT_URL = "ws://localhost:8000/ws/bin"
DEFAULT_DEVICE = "bin-1"
DEFAULT_RATE_HZ = 15.0
FIRMWARE = "0.1-bridge"

# firmware_contract.md: no ping for 5 s means the bin shows offline on its own.
PING_TIMEOUT_S = 5.0

# Reconnect backoff. Fast at first so a backend restart is invisible, then patient.
BACKOFF_START_S = 0.5
BACKOFF_MAX_S = 10.0

LINE_MAX = 20
BIG_MAX = 7
TONES = ("green", "amber", "red", "neutral")

SCREEN_IDLE: Dict[str, Any] = {"type": "screen", "s": "idle"}
SCREEN_OFFLINE: Dict[str, Any] = {"type": "screen", "s": "offline"}

PYSERIAL_HINT = "pyserial is not installed. Install it with: python3 -m pip install pyserial"


class Reading(NamedTuple):
    """One sample. `t_ms` is device milliseconds, `g` is grams after calibration."""

    t_ms: int
    g: float


# Adapters -------------------------------------------------------------------
#
# A weight source hands the bridge grams. A display sink draws a screen command.
# Everything hardware-specific lives behind these two small interfaces, so the day the
# bin exists only the adapter changes, never the protocol loop below it.


class WeightSource:
    """Where grams come from.

    `read` returns the newest reading, or None when the source has nothing yet. It is
    called at the sample rate and must not block for longer than one sample period,
    unless `blocking` is True, in which case the bridge calls it on a worker thread.
    """

    name = "source"
    blocking = False

    def start(self) -> None:
        """Open whatever needs opening. Called once, before the first read."""

    def read(self) -> Optional[Reading]:
        raise NotImplementedError

    def tare(self) -> None:
        """Zero the scale. The backend asks for this with a `tare` message."""

    def command(self, line: str) -> bool:
        """Handle a typed command. True when the source understood it."""
        return False

    def stop(self) -> None:
        """Close whatever was opened."""


class Display:
    """Where screen commands go.

    `show` receives the screen message exactly as the backend sent it, plus the last
    weight the bridge read, because the idle and thinking screens draw the live mass.
    """

    name = "display"

    def show(self, screen: Dict[str, Any], weight_g: Optional[float]) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        """Close whatever was opened."""


def screen_fields(
    screen: Dict[str, Any],
    weight_g: Optional[float] = None,
) -> Tuple[str, str, str, str]:
    """Turn a screen message into line 1, the big figure, line 2 and the tone.

    The backend truncates before it sends. This truncates again, because a display
    that trusts the wire draws garbage the one time the wire is wrong, and the sketch
    on the MCU follows the same rule.
    """
    state = str(screen.get("s", "idle"))
    line1 = str(screen.get("l1", ""))
    line2 = str(screen.get("l2", ""))
    big = str(screen.get("big", ""))
    tone = str(screen.get("c", "neutral"))

    if state == "idle" and not any((line1, line2, big)):
        big = format_weight(weight_g) if weight_g is not None else ""
    elif state == "thinking":
        line1 = line1 or "Weighing"
        big = big or (format_weight(weight_g) if weight_g is not None else "")
    elif state == "offline":
        line1 = line1 or "Offline"
        line2 = line2 or "No connection"

    if tone not in TONES:
        tone = "neutral"
    return line1[:LINE_MAX], big[:BIG_MAX], line2[:LINE_MAX], tone


def format_weight(grams: Optional[float]) -> str:
    """The idle and thinking screens show the live mass as the big figure."""
    if grams is None:
        return ""
    whole = int(round(grams))
    wide = "{:,} g".format(whole)
    return wide if len(wide) <= BIG_MAX else "{} g".format(whole)[:BIG_MAX]


# The MCU on the UNO Q, through App Lab RPC ----------------------------------


RPC_READ = "read_grams"
RPC_TARE = "tare"
RPC_SCREEN = "show_screen"
RPC_TIMEOUT_S = 1.0


def app_lab_bridge() -> Any:
    """Arduino's RPC bridge between the UNO Q's Linux side and its sketch.

    The Python package on the board is `arduino.app_utils`, and `Bridge` is a
    process-wide singleton with `call(method, *params, timeout=10)` for a call that
    returns something and `notify(method, *params)` for one that does not. The sketch
    publishes the other end with `Bridge.provide(name, function)`.

    NEEDS_HARDWARE_CHECK: does this program reach the router when it is started by hand
    with `python3 bridge.py`, or must it be started as an App Lab app with
    `arduino-app-cli app start`? Arduino's docs say the `arduino-router` service owns
    the link and that nothing else may open `/dev/ttyHS1`, but they do not say whether a
    plain script may join the router. Try the plain command first. If the first
    `Bridge.call` times out, put this file in an App Lab app folder as its Python side
    and start it with the CLI, which is the documented path.
    """
    from arduino.app_utils import Bridge  # type: ignore[import-not-found]

    return Bridge


class BridgeWeightSource(WeightSource):
    """Grams from the sketch on the UNO Q's microcontroller, over App Lab RPC.

    The sketch exposes `read_grams`, which returns the last calibrated reading. The call
    blocks on the RPC round trip, so the bridge runs it on a worker thread.
    """

    name = "bridge"
    blocking = True

    def __init__(self, rpc: Optional[Any] = None) -> None:
        self.rpc = rpc
        self.failures = 0
        self._t0 = time.monotonic()

    def start(self) -> None:
        if self.rpc is None:
            self.rpc = app_lab_bridge()

    def read(self) -> Optional[Reading]:
        if self.rpc is None:
            return None
        try:
            grams = self.rpc.call(RPC_READ, timeout=RPC_TIMEOUT_S)
        except Exception as exc:
            self.failures += 1
            if self.failures <= 3 or self.failures % 100 == 0:
                LOG.warning("the sketch did not answer %s: %s", RPC_READ, _short(exc))
            return None
        if grams is None:
            return None
        try:
            return Reading(self._now_ms(), float(grams))
        except (TypeError, ValueError):
            LOG.warning("the sketch answered %s with %r, which is not a number", RPC_READ, grams)
            return None

    def tare(self) -> None:
        if self.rpc is not None:
            self.rpc.notify(RPC_TARE)

    def _now_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000.0)


class BridgeDisplay(Display):
    """Screens to the sketch on the UNO Q's microcontroller, over App Lab RPC.

    The sketch exposes `show_screen(state, line1, big, line2, tone)`, five strings. It is
    sent with `notify` rather than `call`, because nothing needs an answer and a screen
    must never be able to stall the weight stream.
    """

    name = "bridge"

    def __init__(self, rpc: Optional[Any] = None) -> None:
        self.rpc = rpc

    def show(self, screen: Dict[str, Any], weight_g: Optional[float]) -> None:
        if self.rpc is None:
            self.rpc = app_lab_bridge()
        line1, big, line2, tone = screen_fields(screen, weight_g)
        self.rpc.notify(RPC_SCREEN, str(screen.get("s", "idle")), line1, big, line2, tone)


# The MCU over a plain serial link -------------------------------------------


class SerialLink:
    """One serial port, read by a thread and written from the bridge.

    The MCU sends one JSON object per line, `{"t":123456,"g":412.3}`, at 20 Hz. The
    bridge writes one JSON object per line back, the screen command as the backend sent
    it plus `{"type":"tare"}`. Same shapes as the socket, so a teammate reading the
    firmware contract already knows this wire.
    """

    def __init__(self, port: str, baud: int = 115200) -> None:
        self.port = port
        self.baud = baud
        self.handle: Optional[Any] = None
        self.latest: Optional[Reading] = None
        self.lines = 0
        self.bad_lines = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._t0 = time.monotonic()

    def start(self) -> None:
        if self.handle is not None:
            return
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError:
            raise RuntimeError(PYSERIAL_HINT) from None
        self.handle = serial.serial_for_url(self.port, baudrate=self.baud, timeout=1)
        self._reader = threading.Thread(target=self._read_loop, name="serial-read", daemon=True)
        self._reader.start()
        LOG.info("serial link open on %s at %d baud", self.port, self.baud)

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw = self.handle.readline() if self.handle is not None else b""
            except OSError:
                LOG.exception("the serial port went away")
                return
            if not raw:
                continue
            text = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) else str(raw)
            if not text:
                continue
            reading = parse_serial_reading(text, self._now_ms())
            with self._lock:
                self.lines += 1
                if reading is None:
                    self.bad_lines += 1
                else:
                    self.latest = reading

    def read(self) -> Optional[Reading]:
        with self._lock:
            return self.latest

    def write(self, payload: Dict[str, Any]) -> None:
        if self.handle is None:
            return
        try:
            self.handle.write((json.dumps(payload) + "\n").encode("utf-8"))
            flush = getattr(self.handle, "flush", None)
            if callable(flush):
                flush()
        except OSError:
            LOG.exception("could not write to the serial link")

    def stop(self) -> None:
        self._stop.set()
        if self._reader is not None:
            self._reader.join(timeout=2.0)
        if self.handle is not None:
            with contextlib.suppress(Exception):
                self.handle.close()
            self.handle = None

    def _now_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000.0)


def parse_serial_reading(text: str, fallback_ms: int) -> Optional[Reading]:
    """One JSON line from the MCU as a reading. None when the line is not one."""
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    if not isinstance(parsed, dict) or "g" not in parsed:
        return None
    try:
        grams = float(parsed["g"])
    except (TypeError, ValueError):
        return None
    try:
        t_ms = int(parsed.get("t", fallback_ms))
    except (TypeError, ValueError):
        t_ms = fallback_ms
    return Reading(t_ms, grams)


class SerialWeightSource(WeightSource):
    """Grams from the MCU over a serial link."""

    name = "serial"
    blocking = False

    def __init__(self, link: SerialLink) -> None:
        self.link = link

    def start(self) -> None:
        self.link.start()

    def read(self) -> Optional[Reading]:
        return self.link.read()

    def tare(self) -> None:
        self.link.write({"type": "tare"})

    def stop(self) -> None:
        self.link.stop()


class SerialDisplay(Display):
    """Screens to the MCU over the same serial link the weight arrives on."""

    name = "serial"

    def __init__(self, link: SerialLink) -> None:
        self.link = link

    def show(self, screen: Dict[str, Any], weight_g: Optional[float]) -> None:
        line1, big, line2, tone = screen_fields(screen, weight_g)
        self.link.write(
            {
                "type": "screen",
                "s": str(screen.get("s", "idle")),
                "l1": line1,
                "big": big,
                "l2": line2,
                "c": tone,
            }
        )


# The laptop: a fake scale and a text box ------------------------------------


class _Impact:
    """One landing: a spike that decays into a wobble, like a real load cell."""

    def __init__(self, t0_ms: float, mass_g: float) -> None:
        self.t0_ms = t0_ms
        self.mass_g = mass_g
        self.overshoot = 2.0
        self.tau_ms = 90.0
        self.hz = 6.0

    def offset(self, t_ms: float) -> float:
        dt = t_ms - self.t0_ms
        if dt < 0:
            return 0.0
        ring = math.exp(-dt / self.tau_ms) * math.cos(2 * math.pi * self.hz * dt / 1000.0)
        return self.mass_g * self.overshoot * ring

    def done(self, t_ms: float) -> bool:
        return t_ms - self.t0_ms > 8.0 * self.tau_ms


class FakeWeightSource(WeightSource):
    """A noisy baseline plus scripted tosses, so the whole bridge runs with no hardware.

    The same impact model as the simulator in `sim/bin_sim.py`, written on the standard
    library because the board will not get numpy. Drive it with `command`: `toss 95`,
    `remove 20`, `bag`, `tare`.
    """

    name = "fake"
    blocking = False

    def __init__(self, sigma: float = 0.8, seed: Optional[int] = None) -> None:
        self.sigma = sigma
        self.level_g = 0.0
        self._rng = random.Random(seed)
        self._impacts: List[_Impact] = []
        self._t0 = time.monotonic()

    def read(self) -> Optional[Reading]:
        t_ms = (time.monotonic() - self._t0) * 1000.0
        self._impacts = [i for i in self._impacts if not i.done(t_ms)]
        wobble = sum(i.offset(t_ms) for i in self._impacts)
        noise = self._rng.gauss(0.0, self.sigma)
        return Reading(int(t_ms), round(self.level_g + wobble + noise, 2))

    def tare(self) -> None:
        self.level_g = 0.0
        self._impacts = []
        LOG.info("fake scale tared")

    def command(self, line: str) -> bool:
        parts = line.strip().split()
        if not parts:
            return False
        word = parts[0].lower()
        try:
            grams = float(parts[1]) if len(parts) > 1 else 0.0
        except ValueError:
            return False
        if word == "toss":
            return self._change(grams)
        if word in ("remove", "take"):
            return self._change(-abs(grams))
        if word in ("bag", "bag_change"):
            return self._change(-(abs(grams) if grams else self.level_g))
        if word == "tare":
            self.tare()
            return True
        return False

    def _change(self, delta: float) -> bool:
        if delta == 0.0:
            return True
        t_ms = (time.monotonic() - self._t0) * 1000.0
        self.level_g = round(self.level_g + delta, 3)
        self._impacts.append(_Impact(t_ms, delta))
        LOG.info("fake scale %+.1f g, now %.1f g", delta, self.level_g)
        return True


class PrintDisplay(Display):
    """The LCD as a text box on stdout, so the screens are provable from a log.

    It draws through `sim/lcd_box.py` when that file is next to this checkout, which is
    the same renderer the simulator uses, so the box in a bridge log and the box in a
    simulator log cannot drift. On the board, where there is no `sim` directory, it
    falls back to one compact line per screen.
    """

    name = "print"

    def __init__(self, stream: Optional[Any] = None) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.render = _load_lcd_box()
        self.shown: List[Dict[str, Any]] = []

    def show(self, screen: Dict[str, Any], weight_g: Optional[float]) -> None:
        self.shown.append(dict(screen))
        if self.render is not None:
            text = self.render(screen, weight_g)
        else:
            line1, big, line2, tone = screen_fields(screen, weight_g)
            text = "LCD {} [{}] {} | {} | {}".format(
                screen.get("s", "idle"), tone, line1, big, line2
            )
        self.stream.write(text + "\n")
        flush = getattr(self.stream, "flush", None)
        if callable(flush):
            flush()


def _load_lcd_box() -> Optional[Any]:
    """`render_screen` from the repository's simulator, when this runs inside it."""
    here = os.path.dirname(os.path.abspath(__file__))
    sim_dir = os.path.normpath(os.path.join(here, "..", "..", "sim"))
    module_path = os.path.join(sim_dir, "lcd_box.py")
    if not os.path.exists(module_path):
        return None
    if sim_dir not in sys.path:
        sys.path.insert(0, sim_dir)
    try:
        import lcd_box  # type: ignore[import-not-found]
    except ImportError:
        return None
    return lcd_box.render_screen


# The protocol loop ----------------------------------------------------------


class BridgeConfig:
    """Everything the bridge needs, from flags or the environment."""

    def __init__(
        self,
        url: str = DEFAULT_URL,
        device: str = DEFAULT_DEVICE,
        rate_hz: float = DEFAULT_RATE_HZ,
        firmware: str = FIRMWARE,
        insecure: bool = False,
    ) -> None:
        self.url = url
        self.device = device
        self.rate_hz = rate_hz
        self.firmware = firmware
        self.insecure = insecure

    @property
    def period_s(self) -> float:
        return 1.0 / self.rate_hz if self.rate_hz > 0 else 1.0 / DEFAULT_RATE_HZ


class Bridge:
    """The bin on the wire: hello, weight, pong out, screens and tare in.

    One connection at a time, reconnected with backoff. The screens are drawn on the
    display as they arrive, and the offline screen is drawn by the bridge itself when
    the socket drops or the pings stop, which is the rule in the firmware contract.
    """

    def __init__(self, config: BridgeConfig, source: WeightSource, display: Display) -> None:
        self.config = config
        self.source = source
        self.display = display
        self.last_weight: Optional[float] = None
        self.samples = 0
        self.screens = 0
        self.pongs = 0
        self.connections = 0
        self.last_ping = 0.0
        self.connected = asyncio.Event()
        self._offline_shown = False
        self._idle_pending = False

    async def run_forever(self, stop: Optional[asyncio.Event] = None) -> None:
        """Connect, run, and come back after a drop. Returns when `stop` is set."""
        stop = stop or asyncio.Event()
        self.source.start()
        backoff = BACKOFF_START_S
        self._show(SCREEN_OFFLINE)
        try:
            while not stop.is_set():
                try:
                    await self._session(stop)
                    backoff = BACKOFF_START_S
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # the wire is allowed to fail, forever
                    LOG.warning("bin socket: %s", _short(exc))
                self.connected.clear()
                self._show(SCREEN_OFFLINE)
                if stop.is_set():
                    break
                LOG.info("reconnecting in %.1f s", backoff)
                await _wait(stop, backoff)
                backoff = min(backoff * 2.0, BACKOFF_MAX_S)
        finally:
            self.source.stop()
            self.display.stop()

    async def _session(self, stop: asyncio.Event) -> None:
        import websockets

        LOG.info("connecting to %s", self.config.url)
        async with websockets.connect(
            self.config.url,
            ssl=_ssl_for(self.config.url, self.config.insecure),
            open_timeout=10,
        ) as ws:
            self.connections += 1
            self.last_ping = time.monotonic()
            self._offline_shown = False
            await ws.send(
                json.dumps(
                    {"type": "hello", "fw": self.config.firmware, "device": self.config.device}
                )
            )
            LOG.info("connected as %s", self.config.device)
            self.connected.set()
            # Idle is drawn after the first reading, not here, so the screen that
            # replaces offline already carries a weight rather than an empty figure.
            self._idle_pending = True
            reader = asyncio.ensure_future(self._read_loop(ws, stop))
            watchdog = asyncio.ensure_future(self._watch_pings(stop))
            try:
                await self._send_loop(ws, stop)
            finally:
                for task in (reader, watchdog):
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task

    async def _send_loop(self, ws: Any, stop: asyncio.Event) -> None:
        """Weight at the configured rate, on a fixed grid rather than a drifting sleep."""
        period = self.config.period_s
        next_at = time.monotonic()
        while not stop.is_set():
            reading = await self._read_source()
            if reading is not None:
                self.last_weight = reading.g
                self.samples += 1
                await ws.send(
                    json.dumps({"type": "weight", "t": reading.t_ms, "g": reading.g})
                )
                if self._idle_pending:
                    self._idle_pending = False
                    self._show(SCREEN_IDLE)
            next_at += period
            delay = next_at - time.monotonic()
            if delay < 0:
                # Behind the grid, for example after a long read. Catch up, do not
                # try to send the samples that were missed.
                next_at = time.monotonic()
                delay = 0.0
            await asyncio.sleep(delay)

    async def _read_source(self) -> Optional[Reading]:
        if self.source.blocking:
            return await _to_thread(self.source.read)
        return self.source.read()

    async def _read_loop(self, ws: Any, stop: asyncio.Event) -> None:
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            try:
                message = json.loads(raw)
            except ValueError:
                LOG.warning("the backend sent something that is not JSON")
                continue
            if not isinstance(message, dict):
                continue
            await self._handle(ws, message)
        stop_reason = "the backend closed the socket"
        LOG.info(stop_reason)
        raise ConnectionError(stop_reason)

    async def _handle(self, ws: Any, message: Dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == "ping":
            self.last_ping = time.monotonic()
            if self._offline_shown:
                self._offline_shown = False
                self._show(SCREEN_IDLE)
            self.pongs += 1
            await ws.send(json.dumps({"type": "pong", "t": self._device_ms()}))
        elif kind == "screen":
            self.screens += 1
            self._show(message)
        elif kind == "tare":
            LOG.info("the backend asked for a tare")
            self.source.tare()
        else:
            LOG.info("ignoring a %r message", kind)

    async def _watch_pings(self, stop: asyncio.Event) -> None:
        """No ping for 5 s means offline, even though the socket is still open."""
        while not stop.is_set():
            await asyncio.sleep(1.0)
            if time.monotonic() - self.last_ping >= PING_TIMEOUT_S and not self._offline_shown:
                self._offline_shown = True
                LOG.warning("no ping for %.0f s, showing offline", PING_TIMEOUT_S)
                self._show(SCREEN_OFFLINE)

    def _show(self, screen: Dict[str, Any]) -> None:
        try:
            self.display.show(screen, self.last_weight)
        except Exception as exc:  # a broken display must not take the bin off the air
            LOG.warning("the display refused a screen: %s", _short(exc))

    def _device_ms(self) -> int:
        reading = self.source.read()
        if reading is not None:
            return reading.t_ms
        return int(time.monotonic() * 1000.0)


def _short(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:200]


async def _wait(stop: asyncio.Event, seconds: float) -> None:
    """Sleep, but wake early when the bridge is asked to stop."""
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def _to_thread(call: Any) -> Any:
    """`asyncio.to_thread` where it exists, the executor where it does not."""
    to_thread = getattr(asyncio, "to_thread", None)
    if to_thread is not None:
        return await to_thread(call)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, call)


def _ssl_for(url: str, insecure: bool) -> Optional[ssl.SSLContext]:
    """Plain `ws://` needs no context. `wss://` with the demo's self-signed cert needs
    `--insecure`, which is why the bin is pointed at port 8000 and not 8443."""
    if not url.startswith("wss://"):
        return None
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


# Wiring ---------------------------------------------------------------------


def build_source(args: argparse.Namespace, link: Optional[SerialLink]) -> WeightSource:
    if args.source == "bridge":
        return BridgeWeightSource()
    if args.source == "serial":
        assert link is not None
        return SerialWeightSource(link)
    return FakeWeightSource(sigma=args.sigma, seed=args.seed)


def build_display(args: argparse.Namespace, link: Optional[SerialLink]) -> Display:
    kind = args.display or args.source
    if kind == "bridge":
        return BridgeDisplay()
    if kind == "serial":
        assert link is not None
        return SerialDisplay(link)
    return PrintDisplay()


def build_parser() -> argparse.ArgumentParser:
    """Flags first, then the environment, then the default."""
    env = os.environ.get
    parser = argparse.ArgumentParser(
        description="Put the bin on the backend's /ws/bin socket.",
    )
    parser.add_argument(
        "--url",
        default=env("BIN_URL", DEFAULT_URL),
        help="Backend bin socket. Default %(default)s. Env BIN_URL.",
    )
    parser.add_argument(
        "--device",
        default=env("BIN_DEVICE", DEFAULT_DEVICE),
        help="Device id sent in the hello. Default %(default)s. Env BIN_DEVICE.",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=float(env("BIN_RATE_HZ", str(DEFAULT_RATE_HZ))),
        help="Weight samples per second, 10 to 20. Default %(default)s. Env BIN_RATE_HZ.",
    )
    parser.add_argument(
        "--source",
        choices=("bridge", "serial", "fake"),
        default=env("BIN_SOURCE", "fake"),
        help="Where grams come from. Default %(default)s. Env BIN_SOURCE.",
    )
    parser.add_argument(
        "--display",
        choices=("bridge", "serial", "print"),
        default=env("BIN_DISPLAY", "") or None,
        help="Where screens go. Defaults to the same side as the source. Env BIN_DISPLAY.",
    )
    parser.add_argument(
        "--serial-port",
        default=env("BIN_SERIAL_PORT", ""),
        help="Serial port to the MCU, for example /dev/ttyACM0 or COM5. Env BIN_SERIAL_PORT.",
    )
    parser.add_argument(
        "--serial-baud",
        type=int,
        default=int(env("BIN_SERIAL_BAUD", "115200")),
        help="Serial speed. Default %(default)s. Env BIN_SERIAL_BAUD.",
    )
    parser.add_argument(
        "--fw",
        default=env("BIN_FW", FIRMWARE),
        help="Firmware string sent in the hello. Default %(default)s.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip certificate checking on a wss:// url.",
    )
    parser.add_argument(
        "--commands",
        choices=("none", "stdin"),
        default="none",
        help="Read toss, remove, bag and tare commands. Only useful with --source fake.",
    )
    parser.add_argument("--sigma", type=float, default=0.8, help="Fake scale noise in g.")
    parser.add_argument("--seed", type=int, default=None, help="Fake scale random seed.")
    parser.add_argument(
        "--seconds",
        type=float,
        default=0.0,
        help="Stop after this many seconds. 0 runs until interrupted.",
    )
    parser.add_argument("--quiet", action="store_true", help="Warnings only.")
    return parser


async def _read_commands(bridge: Bridge, stop: asyncio.Event) -> None:
    """Typed commands into the fake scale. `quit` stops the bridge."""
    while not stop.is_set():
        line = await _to_thread(sys.stdin.readline)
        if not line:
            stop.set()
            return
        text = line.strip()
        if text in ("quit", "exit"):
            stop.set()
            return
        if text and not bridge.source.command(text):
            LOG.info("commands: toss <grams>, remove <grams>, bag [grams], tare, quit")


async def amain(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    link: Optional[SerialLink] = None
    if "serial" in (args.source, args.display or ""):
        if not args.serial_port:
            print("--source serial needs --serial-port, for example /dev/ttyACM0")
            return 2
        link = SerialLink(args.serial_port, args.serial_baud)

    config = BridgeConfig(
        url=args.url,
        device=args.device,
        rate_hz=args.rate,
        firmware=args.fw,
        insecure=args.insecure,
    )
    bridge = Bridge(config, build_source(args, link), build_display(args, link))

    stop = asyncio.Event()
    helpers: List[Any] = []
    if args.commands == "stdin":
        helpers.append(asyncio.ensure_future(_read_commands(bridge, stop)))
    if args.seconds > 0:
        helpers.append(asyncio.ensure_future(_stop_after(stop, args.seconds)))
    try:
        await bridge.run_forever(stop)
    finally:
        for task in helpers:
            task.cancel()
    LOG.info(
        "%d samples, %d screens, %d pings answered, %d connections",
        bridge.samples,
        bridge.screens,
        bridge.pongs,
        bridge.connections,
    )
    return 0


async def _stop_after(stop: asyncio.Event, seconds: float) -> None:
    await asyncio.sleep(seconds)
    stop.set()


def main(argv: Optional[List[str]] = None) -> int:
    try:
        return asyncio.run(amain(argv))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
