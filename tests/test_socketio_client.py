"""Tests for the dependency-free Socket.IO client."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from custom_components.mcz_maestro.socketio_client import SocketIOClient, SocketIOError


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.closed = asyncio.Event()
        self.got_event = asyncio.Event()

    def on_event(self, name: str, data: object) -> None:
        self.events.append((name, data))
        self.got_event.set()

    def on_close(self) -> None:
        self.closed.set()


async def _client(url: str, rec: Recorder) -> tuple[aiohttp.ClientSession, SocketIOClient]:
    session = aiohttp.ClientSession()
    return session, SocketIOClient(session, url, rec.on_event, rec.on_close)


async def _roundtrip(client: SocketIOClient, rec: Recorder) -> None:
    await client.emit("join", {"serialNumber": "1", "macAddress": "A"})
    await client.emit(
        "chiedo",
        {"serialNumber": "1", "macAddress": "A", "tipoChiamata": 1, "richiesta": "C|RecuperoInfo"},
    )
    await asyncio.wait_for(rec.got_event.wait(), 5)


async def test_websocket_eio3_default(fake_cloud) -> None:
    rec = Recorder()
    session, client = await _client(fake_cloud.url, rec)
    try:
        await client.connect()
        assert client.connected
        assert (client.transport, client.eio) == ("websocket", 3)
        await _roundtrip(client, rec)
        assert fake_cloud.joins == [{"serialNumber": "1", "macAddress": "A"}]
        assert fake_cloud.requests[0]["richiesta"] == "C|RecuperoInfo"
        name, data = rec.events[0]
        assert name == "rispondo"
        assert data["stringaRicevuta"].startswith("01|")
        assert fake_cloud.handshakes == [("websocket", 3)]
    finally:
        await client.close()
        await session.close()


async def test_falls_back_to_eio4(fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(accept_eio=frozenset({4}))
    rec = Recorder()
    session, client = await _client(cloud.url, rec)
    try:
        await client.connect()
        assert (client.transport, client.eio) == ("websocket", 4)
        await _roundtrip(client, rec)
        assert rec.events[0][0] == "rispondo"
    finally:
        await client.close()
        await session.close()


async def test_falls_back_to_polling(fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(allow_websocket=False, accept_eio=frozenset({3, 4}))
    rec = Recorder()
    session, client = await _client(cloud.url, rec)
    try:
        await client.connect()
        assert (client.transport, client.eio) == ("polling", 3)
        await _roundtrip(client, rec)
        assert rec.events[0][0] == "rispondo"
        assert cloud.joins[0]["serialNumber"] == "1"
    finally:
        await client.close()
        await session.close()


async def test_eio3_client_pings_keep_session_alive(fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(ping_interval=0.2, ping_timeout=0.2)
    rec = Recorder()
    session, client = await _client(cloud.url, rec)
    try:
        await client.connect()
        await asyncio.sleep(1.2)
        assert client.connected
        assert not rec.closed.is_set()
        await _roundtrip(client, rec)
    finally:
        await client.close()
        await session.close()


async def test_eio4_client_answers_server_pings(fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(accept_eio=frozenset({4}), ping_interval=0.2, ping_timeout=0.2)
    rec = Recorder()
    session, client = await _client(cloud.url, rec)
    try:
        await client.connect()
        await asyncio.sleep(1.2)
        assert client.connected
        await _roundtrip(client, rec)
    finally:
        await client.close()
        await session.close()


async def test_polling_keeps_alive(fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(allow_websocket=False, ping_interval=0.3, ping_timeout=0.3)
    rec = Recorder()
    session, client = await _client(cloud.url, rec)
    try:
        await client.connect()
        await asyncio.sleep(1.5)
        assert client.connected
        await _roundtrip(client, rec)
    finally:
        await client.close()
        await session.close()


async def test_event_with_ack_id(fake_cloud) -> None:
    rec = Recorder()
    session, client = await _client(fake_cloud.url, rec)
    try:
        await client.connect()
        await fake_cloud.push_event("rispondo", {"stringaRicevuta": "PING"}, ack_id=12)
        await asyncio.wait_for(rec.got_event.wait(), 5)
        assert rec.events == [("rispondo", {"stringaRicevuta": "PING"})]
    finally:
        await client.close()
        await session.close()


async def test_garbage_packets_are_ignored(fake_cloud) -> None:
    rec = Recorder()
    session, client = await _client(fake_cloud.url, rec)
    try:
        await client.connect()
        await fake_cloud.push_raw("42not json")
        await fake_cloud.push_raw("9???")
        await fake_cloud.push_event("rispondo", {"stringaRicevuta": "PING"})
        await asyncio.wait_for(rec.got_event.wait(), 5)
        assert client.connected
        assert rec.events == [("rispondo", {"stringaRicevuta": "PING"})]
    finally:
        await client.close()
        await session.close()


async def test_server_drop_calls_on_close(fake_cloud) -> None:
    rec = Recorder()
    session, client = await _client(fake_cloud.url, rec)
    try:
        await client.connect()
        await fake_cloud.drop_all()
        await asyncio.wait_for(rec.closed.wait(), 5)
        assert not client.connected
        with pytest.raises(SocketIOError):
            await client.emit("join", {})
    finally:
        await client.close()
        await session.close()


async def test_polling_server_drop_calls_on_close(fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(allow_websocket=False)
    rec = Recorder()
    session, client = await _client(cloud.url, rec)
    try:
        await client.connect()
        await cloud.drop_all()
        await asyncio.wait_for(rec.closed.wait(), 5)
        assert not client.connected
    finally:
        await client.close()
        await session.close()


async def test_dead_server_raises(dead_url) -> None:
    rec = Recorder()
    session, client = await _client(dead_url, rec)
    try:
        with pytest.raises(SocketIOError):
            await client.connect(timeout=3)
        assert not client.connected
    finally:
        await client.close()
        await session.close()


async def test_close_does_not_call_on_close(fake_cloud) -> None:
    rec = Recorder()
    session, client = await _client(fake_cloud.url, rec)
    try:
        await client.connect()
        await client.close()
        await asyncio.sleep(0.1)
        assert not rec.closed.is_set()
        assert not client.connected
    finally:
        await session.close()
