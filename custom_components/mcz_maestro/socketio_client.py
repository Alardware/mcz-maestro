"""Minimal Socket.IO client on top of aiohttp.

Only what the MCZ cloud needs: default namespace, emitting events, receiving
events. Speaks Engine.IO v3 (socket.io 1.x/2.x servers) and v4 (socket.io
3.x/4.x servers), over websocket or HTTP long-polling.

Connection order: websocket EIO=3, websocket EIO=4, polling EIO=3.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
from collections import deque
from collections.abc import Callable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_ATTEMPTS: tuple[tuple[str, int], ...] = (("websocket", 3), ("websocket", 4), ("polling", 3))
_POLL_TIMEOUT = 60


class SocketIOError(Exception):
    """Connection failed or was lost."""


class _WebSocketTransport:
    name = "websocket"

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._ws = ws

    @classmethod
    async def open(cls, session: aiohttp.ClientSession, url: str, eio: int) -> _WebSocketTransport:
        ws = await session.ws_connect(
            f"{url}/socket.io/?EIO={eio}&transport=websocket", heartbeat=None, autoping=True
        )
        return cls(ws)

    async def receive(self) -> str:
        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            return msg.data
        raise SocketIOError(f"websocket closed ({msg.type.name})")

    async def send(self, packet: str) -> None:
        try:
            await self._ws.send_str(packet)
        except (ConnectionResetError, RuntimeError, aiohttp.ClientError) as err:
            raise SocketIOError(f"websocket send failed: {err}") from err

    async def close(self) -> None:
        await self._ws.close()


class _PollingTransport:
    name = "polling"

    def __init__(self, session: aiohttp.ClientSession, url: str, eio: int) -> None:
        self._session = session
        self._url = f"{url}/socket.io/"
        self._eio = eio
        self._buffer: deque[str] = deque()
        self._send_lock = asyncio.Lock()
        self.sid: str | None = None

    @classmethod
    async def open(cls, session: aiohttp.ClientSession, url: str, eio: int) -> _PollingTransport:
        transport = cls(session, url, eio)
        await transport._poll()
        return transport

    def _params(self) -> dict[str, str]:
        params = {"EIO": str(self._eio), "transport": "polling", "t": secrets.token_hex(4)}
        if self._eio == 3:
            params["b64"] = "1"
        if self.sid:
            params["sid"] = self.sid
        return params

    def _encode(self, packets: list[str]) -> str:
        if self._eio == 3:
            return "".join(f"{len(p)}:{p}" for p in packets)
        return "\x1e".join(packets)

    def _decode(self, payload: str) -> list[str]:
        if self._eio != 3:
            return [p for p in payload.split("\x1e") if p]
        packets: list[str] = []
        pos = 0
        while pos < len(payload):
            colon = payload.find(":", pos)
            if colon < 0:
                raise SocketIOError("bad polling payload")
            try:
                length = int(payload[pos:colon])
            except ValueError as err:
                raise SocketIOError("bad polling payload") from err
            packets.append(payload[colon + 1 : colon + 1 + length])
            pos = colon + 1 + length
        return packets

    async def _poll(self) -> None:
        try:
            async with self._session.get(
                self._url,
                params=self._params(),
                timeout=aiohttp.ClientTimeout(total=_POLL_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    raise SocketIOError(f"polling HTTP {resp.status}")
                payload = await resp.text()
        except aiohttp.ClientConnectorError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SocketIOError(f"polling failed: {err}") from err
        self._buffer.extend(self._decode(payload))

    async def receive(self) -> str:
        while not self._buffer:
            await self._poll()
        return self._buffer.popleft()

    async def send(self, packet: str) -> None:
        async with self._send_lock:
            try:
                async with self._session.post(
                    self._url,
                    params=self._params(),
                    data=self._encode([packet]).encode(),
                    headers={"Content-Type": "text/plain;charset=UTF-8"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        raise SocketIOError(f"polling send HTTP {resp.status}")
            except (aiohttp.ClientError, TimeoutError) as err:
                raise SocketIOError(f"polling send failed: {err}") from err

    async def close(self) -> None:
        self._buffer.clear()


class SocketIOClient:
    """One Socket.IO connection. Does not reconnect by itself."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        on_event: Callable[[str, Any], None],
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._on_event = on_event
        self._on_close = on_close
        self._transport: _WebSocketTransport | _PollingTransport | None = None
        self._tasks: list[asyncio.Task] = []
        self._ping_interval = 25.0
        self._ping_timeout = 20.0
        self._last_rx = 0.0
        self._closing = False
        self.connected = False
        self.eio: int | None = None
        self.transport: str | None = None

    # ---------------------------------------------------------------- connect
    async def connect(self, timeout: float = 15) -> None:
        """Connect, trying each transport/protocol in turn."""
        errors: list[str] = []
        for transport, eio in _ATTEMPTS:
            try:
                async with asyncio.timeout(timeout):
                    await self._attempt(transport, eio)
            except aiohttp.ClientConnectorError as err:
                await self._drop_transport()
                raise SocketIOError(f"cannot reach {self._url}: {err}") from err
            except (
                aiohttp.ClientError,
                SocketIOError,
                TimeoutError,
                ValueError,
            ) as err:
                errors.append(f"{transport}/EIO{eio}: {err!r}")
                _LOGGER.debug("Socket.IO %s EIO=%s failed: %r", transport, eio, err)
                await self._drop_transport()
                continue
            self._start()
            return
        raise SocketIOError("; ".join(errors))

    async def _attempt(self, transport: str, eio: int) -> None:
        if transport == "websocket":
            self._transport = await _WebSocketTransport.open(self._session, self._url, eio)
        else:
            self._transport = await _PollingTransport.open(self._session, self._url, eio)
        first = await self._transport.receive()
        if not first.startswith("0"):
            raise SocketIOError(f"unexpected open packet {first[:20]!r}")
        handshake = json.loads(first[1:])
        self._ping_interval = handshake.get("pingInterval", 25000) / 1000
        self._ping_timeout = handshake.get("pingTimeout", 20000) / 1000
        if isinstance(self._transport, _PollingTransport):
            self._transport.sid = handshake["sid"]
        # EIO3 servers join the default namespace on their own; EIO4 ones wait for us.
        if eio == 4:
            await self._transport.send("40")
        self._pending: list[str] = []
        while True:
            packet = await self._transport.receive()
            if packet.startswith("40"):
                break
            if packet.startswith("44"):
                raise SocketIOError(f"namespace refused: {packet[2:]}")
            if packet.startswith("2"):
                await self._transport.send("3" + packet[1:])
            elif packet.startswith("42"):
                self._pending.append(packet)
        self.eio = eio
        self.transport = transport

    def _start(self) -> None:
        self.connected = True
        self._closing = False
        self._last_rx = asyncio.get_running_loop().time()
        self._tasks = [
            asyncio.create_task(self._reader(), name="mcz_maestro socketio reader"),
            asyncio.create_task(self._heartbeat(), name="mcz_maestro socketio heartbeat"),
        ]
        for packet in self._pending:
            self._handle_socketio(packet[1:])
        self._pending = []
        _LOGGER.debug("Socket.IO connected via %s EIO=%s", self.transport, self.eio)

    # ---------------------------------------------------------------- runtime
    async def emit(self, event: str, data: Any) -> None:
        """Send an event on the default namespace."""
        if not self.connected or self._transport is None:
            raise SocketIOError("not connected")
        packet = "42" + json.dumps([event, data], separators=(",", ":"))
        try:
            await self._transport.send(packet)
        except SocketIOError:
            self._lost()
            raise

    async def _reader(self) -> None:
        assert self._transport is not None
        try:
            while True:
                packet = await self._transport.receive()
                self._last_rx = asyncio.get_running_loop().time()
                if not await self._handle_packet(packet):
                    break
        except asyncio.CancelledError:
            raise
        except (SocketIOError, aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Socket.IO receive ended: %r", err)
        self._lost()

    async def _handle_packet(self, packet: str) -> bool:
        """Process one Engine.IO packet. Return False when the session ended."""
        assert self._transport is not None
        kind, body = packet[:1], packet[1:]
        if kind == "2":
            await self._transport.send("3" + body)
        elif kind == "1":
            return False
        elif kind == "4":
            if body.startswith("1") or body.startswith("4"):
                _LOGGER.debug("Socket.IO server disconnect: %s", body)
                return False
            self._handle_socketio(body)
        return True

    def _handle_socketio(self, body: str) -> None:
        if not body.startswith("2"):
            return
        rest = body[1:]
        if rest.startswith("/"):
            rest = rest.partition(",")[2]
        while rest[:1].isdigit():
            rest = rest[1:]
        try:
            event, *args = json.loads(rest)
        except (ValueError, TypeError):
            _LOGGER.debug("Ignoring malformed Socket.IO event (%d chars)", len(body))
            return
        if not isinstance(event, str):
            return
        data = args[0] if len(args) == 1 else (args or None)
        try:
            self._on_event(event, data)
        except Exception:  # noqa: BLE001 - a bad callback must not kill the link
            _LOGGER.exception("Error in Socket.IO event handler")

    async def _heartbeat(self) -> None:
        assert self._transport is not None
        loop = asyncio.get_running_loop()
        last_ping = loop.time()
        step = max(min(self._ping_interval / 4, 5.0), 0.02)
        while True:
            await asyncio.sleep(step)
            now = loop.time()
            if self.eio == 3 and now - last_ping >= self._ping_interval:
                last_ping = now
                try:
                    await self._transport.send("2")
                except SocketIOError:
                    break
            if now - self._last_rx > self._ping_interval + self._ping_timeout:
                _LOGGER.debug("Socket.IO heartbeat timeout")
                break
        self._lost()

    # ---------------------------------------------------------------- closing
    def _lost(self) -> None:
        """Remote side gone: tear down and notify once."""
        if not self.connected or self._closing:
            return
        self.connected = False
        current = asyncio.current_task()
        for task in self._tasks:
            if task is not current:
                task.cancel()
        if self._transport is not None:
            transport = self._transport
            self._transport = None
            asyncio.get_running_loop().create_task(transport.close())
        if self._on_close:
            self._on_close()

    async def _drop_transport(self) -> None:
        if self._transport is not None:
            with contextlib.suppress(Exception):
                await self._transport.close()
            self._transport = None

    async def close(self) -> None:
        """Close on purpose (no on_close callback)."""
        self._closing = True
        was_connected = self.connected
        self.connected = False
        if was_connected and self._transport is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._transport.send("1"), 2)
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await self._drop_transport()
