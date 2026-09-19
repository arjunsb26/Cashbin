"""The fallback bin transport from PLAN.md section 5.

On the UNO Q the microcontroller talks to its own Linux side, and that Linux side is
what connects to `/ws/bin`. If the hardware ends up on a plain serial path to the
laptop instead, the same JSON lines arrive on a serial port, and this reads them into
the same `BinSession` the websocket uses. One protocol, one detector, one event
builder, whatever the wire is.

`pyserial` is not a dependency of this project. The reader works on any file-like
object that yields lines, which is what the tests use and what `sys.stdin` is.
`open_serial_port` imports pyserial if it happens to be installed and says how to
install it if not, rather than making every install carry it.

Run it against a port:

    uv run python -m app.ingest.serial_reader COM5

Or pipe a recording into it:

    type recording.jsonl | uv run python -m app.ingest.serial_reader
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sys
from typing import IO, Any, Protocol

from app.config import get_settings
from app.ingest.state import IngestState, build_state

log = logging.getLogger(__name__)

PYSERIAL_HINT = "pyserial is not installed. Install it with: uv pip install pyserial"


class LineSource(Protocol):
    """Anything that yields text lines: a file, sys.stdin, StringIO, a serial port."""

    def readline(self) -> str: ...


class LineSink(Protocol):
    def write(self, data: str) -> Any: ...


class _StreamSink:
    """Backend-to-bin messages as JSON lines, which is what a serial link carries."""

    def __init__(self, stream: LineSink | None) -> None:
        self.stream = stream
        self.sent: list[dict[str, Any]] = []

    async def send(self, payload: dict[str, Any]) -> bool:
        self.sent.append(payload)
        if self.stream is None:
            return True
        try:
            self.stream.write(json.dumps(payload) + "\n")
            flush = getattr(self.stream, "flush", None)
            if callable(flush):
                flush()
        except OSError:
            log.exception("could not write to the serial link")
            return False
        return True


async def pump(
    source: LineSource,
    deps: IngestState,
    sink: LineSink | None = None,
    max_lines: int | None = None,
) -> int:
    """Read JSON lines off `source` into a bin session. Returns how many were handled.

    Stops at end of stream, when the session asks for the link to be closed, or after
    `max_lines`. Reading is done in a worker thread so a blocking port cannot stall the
    event loop.
    """
    from app.ingest.bin_socket import BinSession

    out = _StreamSink(sink)
    session = BinSession(deps, out.send, source="bin serial")
    handled = 0
    while max_lines is None or handled < max_lines:
        line = await asyncio.to_thread(source.readline)
        if not line:
            break
        text = line.strip()
        if not text:
            continue
        handled += 1
        if not await session.handle_text(text):
            log.warning("the serial link sent something the session refused, stopping")
            break
    await session.drain()
    return handled


def open_serial_port(port: str, baud: int = 115200) -> Any:
    """Open a serial port with pyserial if it is installed, or say how to get it."""
    try:
        serial = importlib.import_module("serial")
    except ImportError:
        print(PYSERIAL_HINT)
        return None
    return serial.serial_for_url(port, baudrate=baud, timeout=1)


async def run_port(port: str, baud: int = 115200, deps: IngestState | None = None) -> int:
    """Read one serial port until it closes. Returns how many lines were handled."""
    handle = open_serial_port(port, baud)
    if handle is None:
        return 0
    state = deps or build_state(get_settings())
    try:
        return await pump(_TextPort(handle), state, _TextPort(handle))
    finally:
        handle.close()


class _TextPort:
    """A byte-oriented pyserial handle seen as a text line source and sink."""

    def __init__(self, handle: Any) -> None:
        self.handle = handle

    def readline(self) -> str:
        raw = self.handle.readline()
        if isinstance(raw, bytes):
            return raw.decode("utf-8", "replace")
        return str(raw)

    def write(self, data: str) -> int:
        written = self.handle.write(data.encode("utf-8"))
        return int(written or 0)

    def flush(self) -> None:
        flush = getattr(self.handle, "flush", None)
        if callable(flush):
            flush()


async def _main(argv: list[str] | None = None) -> int:
    """Read JSON lines off stdin. Useful for pushing a recording through by hand."""
    args = list(sys.argv[1:] if argv is None else argv)
    deps = build_state(get_settings())
    source: IO[str] = sys.stdin
    if args and args[0] not in {"-", "stdin"}:
        return await run_port(args[0])
    handled = await pump(source, deps, sys.stdout)
    print(f"handled {handled} lines")
    return 0


if __name__ == "__main__":  # pragma: no cover - a manual entry point
    raise SystemExit(asyncio.run(_main()))
