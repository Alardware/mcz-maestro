# MCZ Maestro (ancienne appli) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Execution note: executed inline by the same agent that wrote the spec (no subagents in this session). Interfaces below are locked; test cases are listed per task and written first (TDD).

**Goal:** Home Assistant custom integration `mcz_maestro` + bundled Lovelace card controlling a legacy MCZ Maestro pellet stove through the MCZ cloud (serial + MAC).

**Architecture:** Dependency-free Socket.IO client on aiohttp (`socketio_client.py`) → MCZ protocol codec (`protocol.py`) → cloud session with reconnection and command queue (`api.py`) → push `DataUpdateCoordinator` (`coordinator.py`) → entity platforms. Card is a vanilla web component served by the integration.

**Tech Stack:** Python 3.13, Home Assistant 2026.x APIs, aiohttp, pytest + pytest-homeassistant-custom-component, vanilla JS (custom elements, shadow DOM).

Spec: `docs/superpowers/specs/2026-11-17-mcz-maestro-ha-design.md`

---

## File map

```
custom_components/mcz_maestro/
  __init__.py            setup/unload entry, card registration
  manifest.json          domain, version, iot_class cloud_push, no requirements
  const.py               DOMAIN, CONF_*, DEFAULT_URL, timings
  socketio_client.py     SocketIOClient (single connection, EIO3/EIO4, ws/polling)
  protocol.py            MaestroState, parse_frame, parse_info, command builders, tables
  api.py                 MaestroCloud (supervisor, queue), async_validate
  coordinator.py         MaestroCoordinator
  entity.py              MaestroEntity base
  climate.py fan.py select.py switch.py sensor.py binary_sensor.py button.py
  diagnostics.py
  strings.json translations/{en,fr}.json icons.json
  frontend/mcz-maestro-card.js
tests/
  conftest.py            fake MCZ cloud fixture, reference frame
  fake_cloud.py          aiohttp Socket.IO server emulating app.mcz.it (v3/v4, ws/polling)
  test_socketio_client.py test_protocol.py test_api.py test_config_flow.py
  test_init.py test_entities.py test_diagnostics.py
  card/                  card harness (HTML + fake hass) and screenshot script
hacs.json  README.md  pyproject.toml (pytest config)
```

## Locked interfaces

```python
# socketio_client.py
class SocketIOError(Exception): ...
class SocketIOClient:
    def __init__(self, session: aiohttp.ClientSession, url: str,
                 on_event: Callable[[str, Any], None],
                 on_close: Callable[[], None] | None = None) -> None
    async def connect(self, timeout: float = 15) -> None   # tries ws EIO3, ws EIO4, polling EIO3
    async def emit(self, event: str, data: Any) -> None      # raises SocketIOError if closed
    async def close(self) -> None
    connected: bool; eio: int | None; transport: str | None  # "websocket" | "polling"

# protocol.py
@dataclass(frozen=True) class MaestroState  # fields per spec §3.3 + raw: tuple[str, ...]
    is_on, is_heating, is_alarm, alarm_code ("A01"…|None), state_key (str), pellets_empty (bool|None)
def parse_frame(text: str) -> tuple[str, list[str]]
def parse_info(text: str) -> MaestroState                    # ValueError if type != "01"
REQUEST_INFO = "C|RecuperoInfo"; REQUEST_PARAMS = "RecuperoParametri"
def cmd_power(on: bool) -> str; cmd_setpoint(t: float); cmd_power_level(n: int); cmd_fan(n: int)
def cmd_dynamic(on: bool); cmd_eco(on); cmd_active(on); cmd_silent(on); cmd_sounds(on); cmd_chrono(on)
def cmd_reset_alarm() -> str; cmd_set_datetime(dt: datetime) -> str
STATE_KEYS: dict[int, str]; STATE_OPTIONS: list[str]

# api.py
class CannotConnect(Exception); class NoResponse(Exception); class NotConnected(Exception)
class MaestroCloud:
    def __init__(self, session, serial: str, mac: str, *, url: str = DEFAULT_URL,
                 on_info: Callable[[MaestroState], None],
                 on_params: Callable[[str], None] | None = None,
                 on_connection: Callable[[bool], None] | None = None,
                 command_interval: float = 1.0, refresh_delay: float = 2.0,
                 backoff: tuple[float, float] = (5.0, 300.0)) -> None
    async def start(self) -> None; async def stop(self) -> None
    async def request_info(self) -> None; async def request_params(self) -> None
    async def send(self, command: str) -> None               # NotConnected if offline
    connected: bool; last_info_raw: str | None; last_params_raw: str | None
async def async_validate(session, serial, mac, url=DEFAULT_URL, timeout=20.0) -> MaestroState
def normalize_mac(mac: str) -> str; def normalize_serial(serial: str) -> str  # ValueError

# coordinator.py
class MaestroCoordinator(DataUpdateCoordinator[MaestroState]):
    def __init__(self, hass, entry, session) -> None
    cloud: MaestroCloud
    async def async_start(self, first_frame_timeout: float = 30) -> None  # ConfigEntryNotReady
    async def async_stop(self) -> None
    async def async_send(self, command: str) -> None       # HomeAssistantError
```

---

### Task 1: Scaffold + protocol codec
**Files:** `manifest.json`, `const.py`, `protocol.py`, `pyproject.toml`, `tests/conftest.py` (reference frame), `tests/test_protocol.py`
- [ ] Tests: reference frame (spec §9 values) decodes to every expected field; ÷2 temperatures; seconds→hours; power 11–15→1–5; fan 6 → auto; missing/short/non-hex fields → None; `parse_info` rejects type `00`; state keys for 0, 15, 41, 50→alarm A01, unknown code → `unknown`; `is_on`/`is_heating`/`is_alarm`; pellets 0→None, 10→False, 11→True; every command builder string (setpoint 19.5 → `C|WriteParametri|42|39`, power off → `|34|40`, datetime → `C|SalvaDataOra|171120260630`).
- [ ] Run → fail; implement; run → pass; commit.

### Task 2: Fake MCZ cloud + Socket.IO client
**Files:** `tests/fake_cloud.py`, `socketio_client.py`, `tests/test_socketio_client.py`
- Fake cloud options: `accept_eio={3,4}`, `allow_websocket=True`, `ping_interval`, frame provider, records joins/requests/commands, `drop_all()` to kill connections.
- [ ] Tests: connects via ws EIO3 (default); falls back to ws EIO4 when EIO3 rejected; falls back to polling EIO3 when websocket refused; emit `join`/`chiedo` reach server with exact payloads; server event `rispondo` reaches `on_event`; EIO3 client pings keep session alive past 2 × pingInterval; EIO4 client answers server pings; event with ack id (`421[...]`) parsed; server close → `on_close` called, `connected` False; connect to dead port → `SocketIOError`.
- [ ] Run → fail; implement; run → pass; commit.

### Task 3: Cloud session (api.py)
**Files:** `api.py`, `tests/test_api.py`
- [ ] Tests: start → join + RecuperoParametri + RecuperoInfo sent, `on_info` called with parsed state, `on_connection(True)`; commands spaced ≥ `command_interval`; RecuperoInfo sent `refresh_delay` after last write (debounced: 3 rapid writes → 1 refresh); `send` while offline → `NotConnected`; server drop → `on_connection(False)` then auto-reconnect and join again; `00` frame → `on_params` + `last_params_raw`; garbage frame ignored; `async_validate` ok / CannotConnect (dead url) / NoResponse (server never answers); normalize_mac (`0A1B2C3D4E5F` → `0A1B2CA137E0`, bad → ValueError), normalize_serial.
- [ ] Run → fail; implement; run → pass; commit.

### Task 4: Config flow + setup + coordinator
**Files:** `config_flow.py`, `__init__.py`, `coordinator.py`, `strings.json`, `translations/*.json`, `tests/test_config_flow.py`, `tests/test_init.py`
- [ ] Tests: user step success creates entry (title = name, unique_id = serial, data normalized); errors `invalid_serial`, `invalid_mac`, `cannot_connect`, `no_response`; duplicate → abort `already_configured`; options flow sets scan interval (15–300); reconfigure updates MAC; setup → entities created, unload stops cloud; no first frame → `ConfigEntryNotReady` (entry state SETUP_RETRY); frame age > 180 s → entities unavailable; alarm transition fires one `mcz_maestro_alarm` event (code, label, device_id), not repeated for same alarm.
- [ ] Run → fail; implement; run → pass; commit.

### Task 5: Entity platforms
**Files:** `entity.py`, `climate.py`, `fan.py`, `select.py`, `switch.py`, `sensor.py`, `binary_sensor.py`, `button.py`, `icons.json`, `tests/test_entities.py`
- [ ] Tests (each against fake cloud, asserting state AND exact command string received):
  climate state/temps/preset/hvac_action, turn on/off, set temperature, set preset; fan percentage/preset auto, set speed 3 → `37|3`, preset auto → `37|6`, turn off → `37|0`; select power 1–5 → `36|n`; each switch on/off; sensors values incl. state enum key and hours; binary sensors; buttons reset alarm / sync time / refresh; diagnostic entities have entity_category; P1–P5 hour sensors disabled by default.
- [ ] Run → fail; implement; run → pass; commit.

### Task 6: Diagnostics
**Files:** `diagnostics.py`, `tests/test_diagnostics.py`
- [ ] Tests: output contains raw `01` and `00` frames, transport/eio, decoded state; serial and MAC absent from the whole JSON dump.
- [ ] Run → fail; implement; run → pass; commit.

### Task 7: Lovelace card
**Files:** `frontend/mcz-maestro-card.js`, `__init__.py` (registration), `tests/card/harness.html`, `tests/card/shoot.py`, `tests/test_init.py` (registration test)
- [ ] Test: integration registers static path `/mcz_maestro/mcz-maestro-card.js` and extra JS URL when `http`/`frontend` available (mocked).
- [ ] Card: config `entity` (+ `name`), sibling lookup via `hass.entities` (`device_id`, `platform`, `translation_key`), dial, power, presets, power segments, fan, info drawer, alarm banner, editor via `ha-form`, `window.customCards` entry.
- [ ] Harness: fake `hass` (states, entities, callService recorder, themes light/dark); screenshots at 390 px and 1100 px light/dark, states: dynamic heating, manual, off, alarm; click tests assert callService payloads.
- [ ] Commit.

### Task 8: Packaging + docs + full verification
**Files:** `hacs.json`, `README.md`, `.gitignore`, `LICENSE`
- [ ] Full test suite green; `python -m compileall`; JSON files valid; manifest keys checked against hassfest rules (domain, name, codeowners, config_flow, documentation, iot_class, issue_tracker, version, requirements); translations: every `translation_key` used in code exists in `strings.json`, `en.json`, `fr.json`.
- [ ] Commit; deliver.
