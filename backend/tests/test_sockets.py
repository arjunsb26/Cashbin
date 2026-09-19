"""The three sockets accept a connection, check the hello, and answer ping and pong."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_bin_socket_greets_then_answers_ping(client: TestClient) -> None:
    with client.websocket_connect("/ws/bin") as socket:
        socket.send_json({"type": "hello", "fw": "0.1", "device": "bin-1"})
        assert socket.receive_json() == {"type": "ping"}
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
        socket.send_json({"type": "pong", "t": 123999})
        assert socket.receive_json() == {"type": "ping"}


def test_bin_socket_refuses_a_bad_hello(client: TestClient) -> None:
    with client.websocket_connect("/ws/bin") as socket, pytest.raises(WebSocketDisconnect):
        socket.send_json({"type": "hello"})
        socket.receive_json()


def test_bin_socket_refuses_traffic_before_hello(client: TestClient) -> None:
    with client.websocket_connect("/ws/bin") as socket, pytest.raises(WebSocketDisconnect):
        socket.send_json({"type": "weight", "t": 1, "g": 2.0})
        socket.receive_json()


def test_bin_socket_survives_junk(client: TestClient) -> None:
    with client.websocket_connect("/ws/bin") as socket:
        socket.send_text("not json at all")
        assert socket.receive_json() == {"type": "error", "detail": "not json"}


def test_phone_socket_greets_then_answers_ping(client: TestClient) -> None:
    with client.websocket_connect("/ws/phone") as socket:
        socket.send_json({"type": "hello", "ua": "Mozilla/5.0 (iPhone)"})
        assert socket.receive_json() == {"type": "ping"}
        socket.send_json({"type": "pong"})
        assert socket.receive_json() == {"type": "ping"}


def test_phone_socket_accepts_binary_frames_quietly(client: TestClient) -> None:
    """Binary frames are JPEG bytes. Step 0 drops them, lane A gives them a ring buffer."""
    with client.websocket_connect("/ws/phone") as socket:
        socket.send_json({"type": "hello", "ua": "test"})
        assert socket.receive_json() == {"type": "ping"}
        socket.send_bytes(b"\xff\xd8\xff\xe0 not really a jpeg")
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_ui_socket_answers_ping(client: TestClient) -> None:
    with client.websocket_connect("/ws/ui") as socket:
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_ui_socket_subscribes_to_the_bus(client: TestClient) -> None:
    from app.notify.bus import CHANNEL_UI, get_bus

    with client.websocket_connect("/ws/ui") as socket:
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
        assert get_bus().subscriber_count(CHANNEL_UI) == 1
    # The subscription is dropped when the socket goes away.
