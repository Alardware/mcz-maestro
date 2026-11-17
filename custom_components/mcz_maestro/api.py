"""Session with the legacy MCZ cloud: join, requests, commands, reconnection."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import re
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import DEFAULT_URL
from .protocol import (
    FRAME_INFO,
    FRAME_PARAMS,
    REQUEST_INFO,
    REQUEST_PARAMS,
    MaestroState,
    parse_frame,
    parse_info,
)
from .socketio_client import SocketIOClient, SocketIOError

_LOGGER = logging.getLogger(__name__)

_MAC_SEPARATORS = re.compile(r"[\s:.\-]")
_MAC_RE = re.compile(r"^[0-9A-F]{12}$")
_SERIAL_RE = re.compile(r"^[0-9A-Z]{6,20}$")

_WRITE_PREFIXES = ("C|WriteParametri|", "C|SalvaDataOra|")


class CannotConnect(Exception):
    """MCZ cloud unreachable."""


class NoResponse(Exception):
    """Cloud reachable but the stove never answered (offline or wrong serial/MAC)."""


class NotConnected(Exception):
    """Command attempted while the cloud link is down."""


def stove_id(serial: str) -> str:
    """Opaque id used as config entry unique_id, so the serial never appears there."""
    return hashlib.sha256(f"mcz_maestro:{serial}".encode()).hexdigest()[:16]


def normalize_mac(mac: str) -> str:
    """Return the MAC as 12 uppercase hex digits, the format the cloud expects."""
    value = _MAC_SEPARATORS.sub("", mac).upper()
    if not _MAC_RE.match(value):
        raise ValueError("invalid MAC address")
    return value


def normalize_serial(serial: str) -> str:
    """Return the serial number without spaces."""
    value = re.sub(r"\s", "", serial).upper()
    if not _SERIAL_RE.match(value):
        raise ValueError("invalid serial number")
    return value


class MaestroCloud:
    """Keeps one stove connected through the MCZ cloud."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        serial: str,
        mac: str,
        *,
        url: str = DEFAULT_URL,
        on_info: Callable[[MaestroState], None],
        on_params: Callable[[str], None] | None = None,
        on_connection: Callable[[bool], None] | None = None,
        command_interval: float = 1.0,
        refresh_delay: float = 2.0,
        backoff: tuple[float, float] = (5.0, 300.0),
        connect_timeout: float = 15.0,
    ) -> None:
        self._session = session
        self._serial = serial
        self._mac = mac
        self._url = url
        self._on_info = on_info
        self._on_params = on_params
        self._on_connection = on_connection
        self._command_interval = command_interval
        self._refresh_delay = refresh_delay
        self._backoff = backoff
        self._connect_timeout = connect_timeout
        self._client: SocketIOClient | None = None
        self._closed_event = asyncio.Event()
        self._supervisor: asyncio.Task | None = None
        self._worker: asyncio.Task | None = None
        self._queue: asyncio.Queue[tuple[int, str, asyncio.Future[None]]] = asyncio.Queue()
        self._refresh_handle: asyncio.TimerHandle | None = None
        self._last_emit = 0.0
        self._stopping = False
        self.connected = False
        self.last_info_raw: str | None = None
        self.last_params_raw: str | None = None

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        """Start connecting in the background (returns immediately)."""
        self._stopping = False
        self._supervisor = asyncio.create_task(self._supervise(), name="mcz_maestro cloud")

    async def stop(self) -> None:
        """Disconnect and stop reconnecting."""
        self._stopping = True
        if self._refresh_handle:
            self._refresh_handle.cancel()
            self._refresh_handle = None
        for task in (self._supervisor, self._worker):
            if task:
                task.cancel()
        for task in (self._supervisor, self._worker):
            if task:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._supervisor = self._worker = None
        if self._client:
            await self._client.close()
            self._client = None
        self._fail_pending(NotConnected("stopped"))
        self._set_connected(False)

    @property
    def transport_info(self) -> dict[str, Any]:
        """Transport actually negotiated (for diagnostics)."""
        if not self._client:
            return {"transport": None, "eio": None}
        return {"transport": self._client.transport, "eio": self._client.eio}

    async def _supervise(self) -> None:
        delay = self._backoff[0]
        while not self._stopping:
            self._closed_event.clear()
            client = SocketIOClient(self._session, self._url, self._on_event, self._closed_event.set)
            try:
                await client.connect(timeout=self._connect_timeout)
                await self._handshake(client)
            except (SocketIOError, aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("MCZ cloud connection failed: %r (retry in %ss)", err, delay)
                await client.close()
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._backoff[1])
                continue
            delay = self._backoff[0]
            self._client = client
            self._set_connected(True)
            self._worker = asyncio.create_task(self._send_loop(), name="mcz_maestro commands")
            await self._closed_event.wait()
            _LOGGER.info("MCZ cloud connection lost, reconnecting")
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None
            self._client = None
            await client.close()
            self._set_connected(False)
            self._fail_pending(NotConnected("connection lost"))
            await asyncio.sleep(self._backoff[0])

    async def _handshake(self, client: SocketIOClient) -> None:
        await client.emit(
            "join",
            {"serialNumber": self._serial, "macAddress": self._mac, "type": "Android-App"},
        )
        await client.emit("chiedo", self._payload(0, REQUEST_PARAMS))
        await client.emit("chiedo", self._payload(1, REQUEST_INFO))
        self._last_emit = asyncio.get_running_loop().time()

    def _set_connected(self, value: bool) -> None:
        if self.connected == value:
            return
        self.connected = value
        if self._on_connection:
            self._on_connection(value)

    def _fail_pending(self, err: Exception) -> None:
        while not self._queue.empty():
            _, _, future = self._queue.get_nowait()
            if not future.done():
                future.set_exception(err)

    # ------------------------------------------------------------- incoming
    def _on_event(self, event: str, data: Any) -> None:
        if event != "rispondo" or not isinstance(data, dict):
            return
        raw = data.get("stringaRicevuta")
        if not isinstance(raw, str):
            return
        kind, _ = parse_frame(raw)
        if kind == FRAME_INFO:
            try:
                state = parse_info(raw)
            except ValueError:
                return
            self.last_info_raw = raw
            self._on_info(state)
        elif kind == FRAME_PARAMS:
            self.last_params_raw = raw
            if self._on_params:
                self._on_params(raw)
        else:
            _LOGGER.debug("Ignoring MCZ frame type %s", kind[:8])

    # ------------------------------------------------------------- outgoing
    def _payload(self, call_type: int, request: str) -> dict[str, Any]:
        return {
            "serialNumber": self._serial,
            "macAddress": self._mac,
            "tipoChiamata": call_type,
            "richiesta": request,
        }

    async def _enqueue(self, call_type: int, request: str) -> None:
        if not self.connected:
            raise NotConnected("MCZ cloud not connected")
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._queue.put_nowait((call_type, request, future))
        await future

    async def send(self, command: str) -> None:
        """Send a command (rate limited). Writes trigger a delayed refresh."""
        await self._enqueue(1, command)
        if command.startswith(_WRITE_PREFIXES):
            self._schedule_refresh()

    async def request_info(self) -> None:
        """Ask the stove for a fresh info frame."""
        await self._enqueue(1, REQUEST_INFO)

    async def request_params(self) -> None:
        """Ask the stove for its parameters frame (kept raw)."""
        await self._enqueue(0, REQUEST_PARAMS)

    def _schedule_refresh(self) -> None:
        loop = asyncio.get_running_loop()
        if self._refresh_handle:
            self._refresh_handle.cancel()

        def _fire() -> None:
            self._refresh_handle = None
            if self.connected:
                task = loop.create_task(self.request_info())
                task.add_done_callback(lambda t: t.cancelled() or t.exception())

        self._refresh_handle = loop.call_later(self._refresh_delay, _fire)

    async def _send_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            call_type, request, future = await self._queue.get()
            wait = self._last_emit + self._command_interval - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            client = self._client
            try:
                if client is None:
                    raise NotConnected("MCZ cloud not connected")
                await client.emit("chiedo", self._payload(call_type, request))
            except (SocketIOError, NotConnected) as err:
                if not future.done():
                    future.set_exception(NotConnected(str(err)))
                continue
            self._last_emit = loop.time()
            if not future.done():
                future.set_result(None)


async def async_validate(
    session: aiohttp.ClientSession,
    serial: str,
    mac: str,
    url: str = DEFAULT_URL,
    timeout: float = 20.0,
) -> MaestroState:
    """Connect once and wait for an info frame from this stove."""
    got: asyncio.Future[MaestroState] = asyncio.get_running_loop().create_future()

    def on_event(event: str, data: Any) -> None:
        if event != "rispondo" or not isinstance(data, dict) or got.done():
            return
        raw = data.get("stringaRicevuta")
        if isinstance(raw, str) and raw.startswith(FRAME_INFO + "|"):
            with contextlib.suppress(ValueError):
                got.set_result(parse_info(raw))

    client = SocketIOClient(session, url, on_event)
    try:
        try:
            await client.connect(timeout=min(timeout, 15))
        except SocketIOError as err:
            raise CannotConnect(str(err)) from err
        try:
            await client.emit(
                "join", {"serialNumber": serial, "macAddress": mac, "type": "Android-App"}
            )
            await client.emit(
                "chiedo",
                {
                    "serialNumber": serial,
                    "macAddress": mac,
                    "tipoChiamata": 1,
                    "richiesta": REQUEST_INFO,
                },
            )
        except SocketIOError as err:
            raise CannotConnect(str(err)) from err
        try:
            return await asyncio.wait_for(asyncio.shield(got), timeout)
        except TimeoutError as err:
            raise NoResponse("no info frame received") from err
    finally:
        if not got.done():
            got.cancel()
        await client.close()
