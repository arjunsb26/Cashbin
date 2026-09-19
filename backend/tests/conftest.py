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
from app.db import dispose_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.notify.bus import reset_bus  # noqa: E402


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    conf = Settings(
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
    reset_settings(Settings())


@pytest.fixture
def dev_settings(tmp_path: Path) -> Iterator[Settings]:
    conf = Settings(
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
    reset_settings(Settings())


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
