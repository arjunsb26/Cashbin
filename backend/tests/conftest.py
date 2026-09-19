"""Shared fixtures. Every test gets its own database file and its own bus."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_DIR = Path(__file__).resolve().parent.parent.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from app.config import Settings, reset_settings  # noqa: E402

# Tests never read the repo root .env, so a real key or provider on this machine cannot
# change what a test sees. The stub is the test provider.
from app.db import dispose_db  # noqa: E402
from app.identify.pipeline import reset_identify  # noqa: E402
from app.main import create_app  # noqa: E402
from app.notify.bus import reset_bus  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_identify() -> Iterator[None]:
    """Identification keeps providers, the memory index and the sim queue in process globals.

    Every test starts with all three empty, so one case can never answer for the next.
    """
    reset_identify()
    yield
    reset_identify()


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    conf = Settings(
        _env_file=None,
        db_path=tmp_path / "binbooks.db",
        media_dir=tmp_path / "media",
        cert_dir=tmp_path / "certs",
        recordings_dir=tmp_path / "recordings",
        dev_tools=False,
    )
    reset_settings(conf)
    reset_bus()
    yield conf
    dispose_db()
    reset_settings(Settings(_env_file=None))


@pytest.fixture
def dev_settings(tmp_path: Path) -> Iterator[Settings]:
    conf = Settings(
        _env_file=None,
        db_path=tmp_path / "binbooks.db",
        media_dir=tmp_path / "media",
        cert_dir=tmp_path / "certs",
        recordings_dir=tmp_path / "recordings",
        dev_tools=True,
    )
    reset_settings(conf)
    reset_bus()
    yield conf
    dispose_db()
    reset_settings(Settings(_env_file=None))


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def dev_client(dev_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(dev_settings)) as test_client:
        yield test_client
