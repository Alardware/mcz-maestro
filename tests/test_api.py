"""Tests for the MCZ cloud session."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from custom_components.mcz_maestro import api
from custom_components.mcz_maestro.protocol import MaestroState

SERIAL = "1234567890123"
MAC = "0A1B2CA137E0"


class Sink:
    def __init__(self) -> None:
        self.states: list[MaestroState] = []
        self.params: list[str] = []
        self.links: list[bool] = []
        self.state_event = asyncio.Event()
        self.link_event = asyncio.Event()

    def on_info(self, state: MaestroState) -> None:
        self.states.append(state)
        self.state_event.set()

    def on_params(self, raw: str) -> None:
        self.params.append(raw)

    def on_connection(self, up: bool) -> None:
        self.links.append(up)
        self.link_event.set()

    async def next_state(self, timeout: float = 5) -> MaestroState:
        self.state_event.clear()
        await asyncio.wait_for(self.state_event.wait(), timeout)
        return self.states[-1]

    async def wait_links(self, expected: list[bool], timeout: float = 5) -> None:
        async def _wait() -> None:
            while self.links != expected:
                self.link_event.clear()
                await self.link_event.wait()

        await asyncio.wait_for(_wait(), timeout)


@pytest.fixture
async def http():
    async with aiohttp.ClientSession() as session:
        yield session


def _cloud(http, url, sink, **kw) -> api.MaestroCloud:
    kw.setdefault("command_interval", 0.05)
    kw.setdefault("refresh_delay", 0.1)
    kw.setdefault("backoff", (0.05, 0.2))
    return api.MaestroCloud(
        http,
        SERIAL,
        MAC,
        url=url,
        on_info=sink.on_info,
        on_params=sink.on_params,
        on_connection=sink.on_connection,
        **kw,
    )


async def test_start_joins_and_requests(fake_cloud, http) -> None:
    sink = Sink()
    cloud = _cloud(http, fake_cloud.url, sink)
    await cloud.start()
    try:
        state = await sink.next_state()
        assert state.setpoint == 19.0
        assert cloud.connected
        assert sink.links == [True]
        assert fake_cloud.joins == [
            {"serialNumber": SERIAL, "macAddress": MAC, "type": "Android-App"}
        ]
        requests = [(r["tipoChiamata"], r["richiesta"]) for r in fake_cloud.requests]
        assert requests[:2] == [(0, "RecuperoParametri"), (1, "C|RecuperoInfo")]
        assert all(r["serialNumber"] == SERIAL and r["macAddress"] == MAC for r in fake_cloud.requests)
        await asyncio.sleep(0.1)
        assert sink.params and sink.params[0].startswith("00|")
        assert cloud.last_params_raw == sink.params[0]
        assert cloud.last_info_raw.startswith("01|")
        assert cloud.transport_info == {"transport": "websocket", "eio": 3}
    finally:
        await cloud.stop()


async def test_send_spacing_and_debounced_refresh(fake_cloud, http) -> None:
    sink = Sink()
    cloud = _cloud(http, fake_cloud.url, sink, command_interval=0.2, refresh_delay=0.4)
    await cloud.start()
    try:
        await sink.next_state()
        fake_cloud.requests.clear()
        fake_cloud.request_times.clear()
        await asyncio.gather(
            cloud.send("C|WriteParametri|41|0"),
            cloud.send("C|WriteParametri|42|40"),
            cloud.send("C|WriteParametri|36|2"),
        )
        assert fake_cloud.commands == [
            "C|WriteParametri|41|0",
            "C|WriteParametri|42|40",
            "C|WriteParametri|36|2",
        ]
        times = fake_cloud.request_times
        assert all(b - a >= 0.18 for a, b in zip(times, times[1:]))
        state = await sink.next_state(3)
        assert state.eco is False
        assert state.setpoint == 20.0
        assert state.power_level == 2
        await asyncio.sleep(0.6)
        info_requests = [r for r in fake_cloud.requests if r["richiesta"] == "C|RecuperoInfo"]
        assert len(info_requests) == 1
    finally:
        await cloud.stop()


async def test_send_offline_raises(dead_url, http) -> None:
    sink = Sink()
    cloud = _cloud(http, dead_url, sink)
    await cloud.start()
    try:
        await asyncio.sleep(0.05)
        assert not cloud.connected
        with pytest.raises(api.NotConnected):
            await cloud.send("C|WriteParametri|41|0")
    finally:
        await cloud.stop()


async def test_reconnects_after_drop(fake_cloud, http) -> None:
    sink = Sink()
    cloud = _cloud(http, fake_cloud.url, sink)
    await cloud.start()
    try:
        await sink.next_state()
        await fake_cloud.drop_all()
        await sink.wait_links([True, False, True])
        await sink.next_state()
        assert len(fake_cloud.joins) == 2
        assert cloud.connected
    finally:
        await cloud.stop()


async def test_keeps_retrying_until_cloud_answers(fake_cloud_factory, http, dead_url) -> None:
    sink = Sink()
    cloud = _cloud(http, dead_url, sink)
    await cloud.start()
    await asyncio.sleep(0.4)
    assert sink.links == []
    assert cloud.connected is False
    await cloud.stop()


async def test_garbage_and_other_frames_ignored(fake_cloud, http) -> None:
    sink = Sink()
    cloud = _cloud(http, fake_cloud.url, sink)
    await cloud.start()
    try:
        await sink.next_state()
        count = len(sink.states)
        await fake_cloud.push_event("rispondo", {"stringaRicevuta": "PING"})
        await fake_cloud.push_event("rispondo", {"stringaRicevuta": "0A|1|2"})
        await fake_cloud.push_event("rispondo", "not a dict")
        await fake_cloud.push_event("other", {"x": 1})
        await fake_cloud.push_event("rispondo", {"stringaRicevuta": "01"})
        await asyncio.sleep(0.2)
        # "01" with no fields is still an info frame (all None) and is delivered.
        assert len(sink.states) == count + 1
        assert cloud.connected
    finally:
        await cloud.stop()


async def test_stop_is_clean(fake_cloud, http) -> None:
    sink = Sink()
    cloud = _cloud(http, fake_cloud.url, sink)
    await cloud.start()
    await sink.next_state()
    await cloud.stop()
    assert not cloud.connected
    assert sink.links == [True, False]
    with pytest.raises(api.NotConnected):
        await cloud.send("C|RecuperoInfo")


async def test_validate_ok(fake_cloud, http) -> None:
    state = await api.async_validate(http, SERIAL, MAC, url=fake_cloud.url, timeout=5)
    assert state.ambient_temp == 18.0
    assert fake_cloud.joins[0]["serialNumber"] == SERIAL


async def test_validate_cannot_connect(dead_url, http) -> None:
    with pytest.raises(api.CannotConnect):
        await api.async_validate(http, SERIAL, MAC, url=dead_url, timeout=3)


async def test_validate_no_response(fake_cloud_factory, http) -> None:
    cloud = await fake_cloud_factory(respond=False)
    with pytest.raises(api.NoResponse):
        await api.async_validate(http, SERIAL, MAC, url=cloud.url, timeout=0.5)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0A1B2CA137E0", "0A1B2CA137E0"),
        ("0A1B2C3D4E5F", "0A1B2CA137E0"),
        (" 0A1B2C3D4E5F ", "0A1B2CA137E0"),
    ],
)
def test_normalize_mac(raw, expected) -> None:
    assert api.normalize_mac(raw) == expected


@pytest.mark.parametrize("raw", ["", "0A1B2CA137", "0A1B2CA137E0FF", "0A1B2CA137EZ"])
def test_normalize_mac_invalid(raw) -> None:
    with pytest.raises(ValueError):
        api.normalize_mac(raw)


def test_normalize_serial() -> None:
    assert api.normalize_serial(" 1234567890123 ") == "1234567890123"
    assert api.normalize_serial("1234 5678 90123") == "1234567890123"
    for bad in ("", "123", "1234-56*7890123", "x" * 30):
        with pytest.raises(ValueError):
            api.normalize_serial(bad)
