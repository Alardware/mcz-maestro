"""In-process emulation of the legacy MCZ cloud (app.mcz.it:9000).

Speaks Engine.IO v3 (socket.io 2.x behaviour) and/or v4, over websocket and
long-polling, and answers "chiedo" requests like the real service: info frames,
parameter frames and parameter writes.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any

from aiohttp import WSMsgType, web

from .conftest import PARAMS_FRAME, REFERENCE_VALUES, build_info_frame

# Write parameter id -> (frame index, value transform)
_WRITE_MAP: dict[int, tuple[int, Any]] = {
    36: (29, lambda v: v + 10),  # power level -> 11..15
    37: (2, lambda v: v),
    40: (22, lambda v: v),
    41: (23, lambda v: v),
    35: (20, lambda v: v),
    45: (24, lambda v: v),
    50: (49, lambda v: v),
    1111: (25, lambda v: v),
    42: (26, lambda v: v),
}


@dataclass
class _Session:
    sid: str
    eio: int
    transport: str
    ws: web.WebSocketResponse | None = None
    queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    connected_ns: bool = False
    last_seen: float = 0.0
    last_ping_sent: float = 0.0
    closed: bool = False
    tasks: list[asyncio.Task] = field(default_factory=list)


class FakeMczCloud:
    """aiohttp application emulating the MCZ Socket.IO endpoint."""

    def __init__(
        self,
        *,
        accept_eio: frozenset[int] = frozenset({3}),
        allow_websocket: bool = True,
        ping_interval: float = 25.0,
        ping_timeout: float = 5.0,
        respond: bool = True,
        poll_timeout: float = 0.5,
    ) -> None:
        self.accept_eio = accept_eio
        self.allow_websocket = allow_websocket
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.respond = respond
        self.poll_timeout = poll_timeout
        self.values: dict[int, int] = dict(REFERENCE_VALUES)
        self.joins: list[dict] = []
        self.requests: list[dict] = []
        self.commands: list[str] = []
        self.request_times: list[float] = []
        self.sessions: dict[str, _Session] = {}
        self.handshakes: list[tuple[str, int]] = []
        self.app = web.Application()
        self.app.router.add_route("*", "/socket.io/", self._handle)

    # ------------------------------------------------------------------ helpers
    def frame(self) -> str:
        """Current info frame."""
        return build_info_frame(self.values)

    def set_value(self, idx: int, value: int) -> None:
        """Change a frame field (simulates the stove changing state)."""
        self.values[idx] = value

    @property
    def active_sessions(self) -> list[_Session]:
        return [s for s in self.sessions.values() if not s.closed]

    async def drop_all(self) -> None:
        """Kill every client connection, like a cloud restart."""
        for session in list(self.sessions.values()):
            await self._close(session)

    async def push_event(self, event: str, data: Any, ack_id: int | None = None) -> None:
        """Send an event to every connected client."""
        prefix = "42" if ack_id is None else f"42{ack_id}"
        packet = prefix + json.dumps([event, data])
        for session in self.active_sessions:
            await self._send(session, packet)

    async def push_raw(self, packet: str) -> None:
        for session in self.active_sessions:
            await self._send(session, packet)

    # ------------------------------------------------------------------ engine.io
    def _open_packet(self, session: _Session) -> str:
        payload = {
            "sid": session.sid,
            "upgrades": [],
            "pingInterval": int(self.ping_interval * 1000),
            "pingTimeout": int(self.ping_timeout * 1000),
        }
        if session.eio == 4:
            payload["maxPayload"] = 1_000_000
        return "0" + json.dumps(payload)

    async def _send(self, session: _Session, packet: str) -> None:
        if session.closed:
            return
        if session.ws is not None:
            with contextlib.suppress(ConnectionResetError, RuntimeError):
                await session.ws.send_str(packet)
        else:
            session.queue.put_nowait(packet)

    async def _close(self, session: _Session) -> None:
        if session.closed:
            return
        session.closed = True
        for task in session.tasks:
            task.cancel()
        if session.ws is not None:
            await session.ws.close()
        else:
            session.queue.put_nowait("1")

    async def _watchdog(self, session: _Session) -> None:
        loop = asyncio.get_running_loop()
        limit = self.ping_interval + self.ping_timeout
        while not session.closed:
            await asyncio.sleep(min(self.ping_interval, 0.05))
            if session.eio == 4 and loop.time() - session.last_ping_sent >= self.ping_interval:
                session.last_ping_sent = loop.time()
                await self._send(session, "2")
            if loop.time() - session.last_seen > limit:
                await self._close(session)

    def _new_session(self, eio: int, transport: str) -> _Session:
        session = _Session(sid=secrets.token_hex(8), eio=eio, transport=transport)
        session.last_seen = asyncio.get_running_loop().time()
        session.last_ping_sent = session.last_seen
        self.sessions[session.sid] = session
        self.handshakes.append((transport, eio))
        session.tasks.append(asyncio.create_task(self._watchdog(session)))
        return session

    async def _on_packet(self, session: _Session, packet: str) -> None:
        session.last_seen = asyncio.get_running_loop().time()
        kind, body = packet[:1], packet[1:]
        if kind == "2":
            await self._send(session, "3" + body)
        elif kind == "3":
            pass
        elif kind == "1":
            await self._close(session)
        elif kind == "4":
            await self._on_socketio(session, body)

    async def _on_socketio(self, session: _Session, body: str) -> None:
        kind, rest = body[:1], body[1:]
        if kind == "0":
            session.connected_ns = True
            if session.eio == 4:
                await self._send(session, "40" + json.dumps({"sid": session.sid}))
            else:
                await self._send(session, "40")
            return
        if kind != "2" or not session.connected_ns:
            return
        while rest and rest[0].isdigit():
            rest = rest[1:]
        event, *args = json.loads(rest)
        data = args[0] if args else None
        if event == "join":
            self.joins.append(data)
        elif event == "chiedo":
            await self._on_chiedo(session, data)

    async def _on_chiedo(self, session: _Session, data: dict) -> None:
        self.requests.append(data)
        self.request_times.append(asyncio.get_running_loop().time())
        request: str = data.get("richiesta", "")
        if request.startswith("C|WriteParametri|") or request.startswith("C|SalvaDataOra|"):
            self.commands.append(request)
            self._apply_write(request)
            return
        if not self.respond:
            return
        if request == "C|RecuperoInfo":
            reply = self.frame()
        elif request == "RecuperoParametri":
            reply = PARAMS_FRAME
        else:
            return
        await self._send(session, "42" + json.dumps(["rispondo", {"stringaRicevuta": reply}]))

    def _apply_write(self, request: str) -> None:
        parts = request.split("|")
        if parts[1] != "WriteParametri":
            return
        param, value = int(parts[2]), int(parts[3])
        if param == 34:
            self.values[1] = 1 if value == 1 else 40
        elif param == 1 and value == 255:
            self.values[1] = 0
        elif param in _WRITE_MAP:
            idx, transform = _WRITE_MAP[param]
            self.values[idx] = transform(value)

    # ------------------------------------------------------------------ http
    async def _handle(self, request: web.Request) -> web.StreamResponse:
        try:
            eio = int(request.query.get("EIO", "0"))
        except ValueError:
            eio = 0
        if eio not in self.accept_eio:
            return web.json_response(
                {"code": 5, "message": "Unsupported protocol version"}, status=400
            )
        transport = request.query.get("transport")
        if transport == "websocket":
            if not self.allow_websocket:
                return web.json_response({"code": 0, "message": "Transport unknown"}, status=400)
            return await self._handle_ws(request, eio)
        if transport == "polling":
            return await self._handle_polling(request, eio)
        return web.json_response({"code": 0, "message": "Transport unknown"}, status=400)

    async def _handle_ws(self, request: web.Request, eio: int) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        session = self._new_session(eio, "websocket")
        session.ws = ws
        await ws.send_str(self._open_packet(session))
        if eio == 3:
            session.connected_ns = True
            await ws.send_str("40")
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                break
            await self._on_packet(session, msg.data)
        session.closed = True
        for task in session.tasks:
            task.cancel()
        return ws

    @staticmethod
    def _encode(eio: int, packets: list[str]) -> str:
        if eio == 3:
            return "".join(f"{len(p)}:{p}" for p in packets)
        return "\x1e".join(packets)

    @staticmethod
    def _decode(eio: int, payload: str) -> list[str]:
        if eio == 4:
            return payload.split("\x1e") if payload else []
        packets, pos = [], 0
        while pos < len(payload):
            colon = payload.index(":", pos)
            length = int(payload[pos:colon])
            packets.append(payload[colon + 1 : colon + 1 + length])
            pos = colon + 1 + length
        return packets

    async def _handle_polling(self, request: web.Request, eio: int) -> web.Response:
        sid = request.query.get("sid")
        if sid is None:
            if request.method != "GET":
                return web.Response(status=400)
            session = self._new_session(eio, "polling")
            packets = [self._open_packet(session)]
            if eio == 3:
                session.connected_ns = True
                session.queue.put_nowait("40")
            return web.Response(text=self._encode(eio, packets))
        session = self.sessions.get(sid)
        if session is None or session.closed:
            return web.json_response({"code": 1, "message": "Session ID unknown"}, status=400)
        if request.method == "POST":
            for packet in self._decode(eio, await request.text()):
                await self._on_packet(session, packet)
            return web.Response(text="ok")
        session.last_seen = asyncio.get_running_loop().time()
        packets: list[str] = []
        try:
            packets.append(await asyncio.wait_for(session.queue.get(), self.poll_timeout))
        except TimeoutError:
            packets.append("6")
        while not session.queue.empty():
            packets.append(session.queue.get_nowait())
        return web.Response(text=self._encode(eio, packets))
