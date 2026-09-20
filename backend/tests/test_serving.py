"""What the backend listens on, and who is allowed to talk to it.

PLAN.md 21a item 20. On this laptop `localhost` resolves to `::1` first and the server was
bound to IPv4 only, so every new connection sat for 2.02 s waiting for the IPv6 attempt to
time out before falling back to 127.0.0.1, which connects in 0.04 s. A dashboard makes many
connections, so the backend looked dead. Binding both families is the fix, and these tests
are the wall around it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from app.main import CORS_ORIGIN_PATTERN  # noqa: E402
from scripts.run_backend import binds_for  # noqa: E402


def test_a_wildcard_host_listens_on_both_address_families() -> None:
    listening = binds_for("0.0.0.0", 8443)
    assert "[::]:8443" in listening
    if sys.platform == "win32":
        # Windows does not give an IPv6 socket the IPv4 addresses as well, so both are
        # bound by name. Everywhere else the IPv6 socket already covers IPv4, and binding
        # the same port twice would be refused.
        assert "0.0.0.0:8443" in listening
    assert listening[0] == "[::]:8443", "the family localhost resolves to first"


def test_a_named_host_is_left_exactly_as_it_was_asked_for() -> None:
    assert binds_for("127.0.0.1", 9000) == ["127.0.0.1:9000"]
    assert binds_for("192.168.137.1", 9000) == ["192.168.137.1:9000"]


def test_the_config_binds_both_ports_the_same_way(tmp_path: Path) -> None:
    from scripts.run_backend import build_config

    config = build_config("0.0.0.0", 8443, 8000, tmp_path)
    assert "[::]:8443" in config.bind
    assert "[::]:8000" in config.insecure_bind
    if sys.platform == "win32":
        assert "0.0.0.0:8443" in config.bind
        assert "0.0.0.0:8000" in config.insecure_bind


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://127.0.0.1:8443",
        "http://[::1]:3000",
        "https://192.168.137.1",
    ],
)
def test_every_way_of_naming_this_machine_is_allowed(origin: str) -> None:
    assert re.fullmatch(CORS_ORIGIN_PATTERN, origin), origin


@pytest.mark.parametrize("origin", ["https://example.com", "http://evil.localhost.com"])
def test_anywhere_else_is_not(origin: str) -> None:
    assert re.fullmatch(CORS_ORIGIN_PATTERN, origin) is None, origin
