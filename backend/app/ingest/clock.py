"""One backend clock for every arrival stamp.

PLAN.md section 6 is blunt about it: the backend stamps each frame and each weight
message with its own monotonic arrival time, and the device `t` is kept only for
debugging. Everything in this package reads the time through here so a test can hand
the pipeline a clock it controls instead of waiting real seconds for a step to settle.

Timers are a different thing and stay on real time. A heartbeat that fired because a
test fast-forwarded the sample clock would prove nothing.
"""

from __future__ import annotations

import time
from collections.abc import Callable

Clock = Callable[[], float]


def monotonic_ms() -> float:
    """Milliseconds on the process monotonic clock. The default stamp for everything."""
    return time.monotonic() * 1000.0
