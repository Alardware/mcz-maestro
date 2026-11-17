"""Codec for the legacy MCZ Maestro protocol.

Frames are ``|``-separated strings. Field 0 is the frame type ("01" info,
"00" parameters, ...); the other fields are hexadecimal integers. Commands
are plain strings such as ``C|WriteParametri|<id>|<value>``.

This module is pure: no network, no Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

FRAME_INFO = "01"
FRAME_PARAMS = "00"

REQUEST_INFO = "C|RecuperoInfo"
REQUEST_PARAMS = "RecuperoParametri"

_WRITE = "C|WriteParametri"

# Stove state code -> translation key.
STATE_KEYS: dict[int, str] = {
    0: "off",
    1: "checking",
    2: "cleaning_cold",
    3: "loading_cold",
    4: "start_1_cold",
    5: "start_2_cold",
    6: "cleaning_hot",
    7: "loading_hot",
    8: "start_1_hot",
    9: "start_2_hot",
    10: "stabilising",
    11: "power_1",
    12: "power_2",
    13: "power_3",
    14: "power_4",
    15: "power_5",
    30: "diagnostics",
    31: "on",
    40: "extinguishing",
    41: "cooling",
    42: "cleaning_low",
    43: "cleaning_high",
    44: "unlocking_auger",
    45: "auto_eco",
    46: "standby",
    48: "diagnostics",
    49: "loading_auger",
    50: "alarm_a01",
    51: "alarm_a02",
    52: "alarm_a03",
    53: "alarm_a04",
    54: "alarm_a05",
    55: "alarm_a06",
    56: "alarm_a09",
    57: "alarm_a11",
    58: "alarm_a13",
    59: "alarm_a14",
    60: "alarm_a18",
    61: "alarm_a19",
    62: "alarm_a20",
    63: "alarm_a21",
    64: "alarm_a22",
    65: "alarm_a23",
    66: "alarm_a12",
    67: "alarm_a17",
    69: "waiting_safety_alarms",
}

# Alarm descriptions in English, for logs and diagnostics. Text shown to users comes
# from the integration's translations, in Home Assistant's language.
ALARM_LABELS: dict[str, str] = {
    "A01": "Ignition failed",
    "A02": "No flame",
    "A03": "Tank overheating",
    "A04": "Flue gas too hot",
    "A05": "Flue obstructed or wind",
    "A06": "Poor draught",
    "A09": "Flue gas probe fault",
    "A11": "Gear motor fault",
    "A12": "Gear motor controller fault",
    "A13": "Motherboard too hot",
    "A14": "Active fault",
    "A17": "Auger jammed",
    "A18": "Water too hot",
    "A19": "Water probe fault",
    "A20": "Auxiliary probe fault",
    "A21": "Pressure switch alarm",
    "A22": "Room probe fault",
    "A23": "Brazier closing fault",
}

STATE_OPTIONS: list[str] = list(dict.fromkeys([*STATE_KEYS.values(), "unknown"]))

# Running (thermostat "heat" mode): ignition, power levels, on, periodic
# cleaning and eco/standby pauses.
_ON_CODES = frozenset({*range(1, 16), 31, 42, 43, 44, 45, 46, 49})
# Flame expected: ignition sequence, stabilisation, power levels, on.
_HEATING_CODES = frozenset({*range(1, 16), 31})
_ALARM_CODES = frozenset({*range(50, 68), 69})


def parse_frame(text: str) -> tuple[str, list[str]]:
    """Split a raw frame into (type, fields)."""
    parts = text.split("|")
    return parts[0], parts[1:]


def _hex(fields: list[str], idx: int) -> int | None:
    """Return field ``idx`` (1-based, as in the frame) as int, or None."""
    pos = idx - 1
    if pos < 0 or pos >= len(fields):
        return None
    try:
        return int(fields[pos], 16)
    except ValueError:
        return None


def _half(value: int | None) -> float | None:
    return None if value is None else value / 2


def _flag(value: int | None) -> bool | None:
    return None if value is None else value != 0


def _hours(seconds: int | None) -> float | None:
    return None if seconds is None else round(seconds / 3600, 1)


@dataclass(frozen=True, slots=True)
class MaestroState:
    """Decoded "01" info frame."""

    state_code: int | None
    fan: int | None
    fumes_temp: int | None
    ambient_temp: float | None
    igniter_on: bool | None
    active_set: int | None
    fumes_fan_rpm: int | None
    auger_rpm_set: int | None
    auger_rpm_live: int | None
    brazier_dirty: bool | None
    profile: int | None
    active_mode: bool | None
    active_live: int | None
    dynamic: bool | None
    eco: bool | None
    silent: bool | None
    chrono: bool | None
    setpoint: float | None
    board_temp: float | None
    power_level: int | None
    firmware: int | None
    stove_clock: datetime | None
    total_hours: float | None
    power_hours: tuple[float | None, ...]
    hours_to_service: int | None
    minutes_to_off: int | None
    ignitions: int | None
    active_temp: int | None
    pellet_sensor: int | None
    sounds: bool | None
    summer: bool | None
    antifreeze: int | None
    raw: tuple[str, ...]

    @property
    def state_key(self) -> str:
        """Translation key of the stove state."""
        if self.state_code is None:
            return "unknown"
        return STATE_KEYS.get(self.state_code, "unknown")

    @property
    def is_on(self) -> bool:
        """Stove running (user intent "on"), including eco/standby pauses."""
        return self.state_code in _ON_CODES

    @property
    def is_heating(self) -> bool:
        """Flame expected (ignition, stabilisation, power levels)."""
        return self.state_code in _HEATING_CODES

    @property
    def is_alarm(self) -> bool:
        """Stove blocked by an alarm."""
        return self.state_code in _ALARM_CODES

    @property
    def alarm_code(self) -> str | None:
        """Alarm code as printed on the stove ("A01"...), if any."""
        key = self.state_key
        if key.startswith("alarm_"):
            return key.removeprefix("alarm_").upper()
        return None

    @property
    def alarm_key(self) -> str | None:
        """Option of the alarm sensor ("a01"..., "safety"), None without alarm."""
        if not self.is_alarm:
            return None
        code = self.alarm_code
        return code.lower() if code else "safety"

    @property
    def alarm_label(self) -> str | None:
        """Alarm in English ("A01 – Ignition failed"), for logs and diagnostics."""
        if not self.is_alarm:
            return None
        code = self.alarm_code
        if code is None:
            return "Waiting for safety alarms"
        return f"{code} – {ALARM_LABELS.get(code, 'Alarm')}"

    @property
    def pellets_empty(self) -> bool | None:
        """None without pellet sensor, else True when the hopper is empty."""
        if self.pellet_sensor == 10:
            return False
        if self.pellet_sensor == 11:
            return True
        return None


def _clock(fields: list[str]) -> datetime | None:
    hour, minute, day, month, year = (_hex(fields, i) for i in range(32, 37))
    if None in (hour, minute, day, month, year):
        return None
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def parse_info(text: str) -> MaestroState:
    """Decode a "01" info frame. Raises ValueError for any other frame type."""
    kind, fields = parse_frame(text)
    if kind != FRAME_INFO:
        raise ValueError(f"not an info frame: {kind!r}")

    def h(idx: int) -> int | None:
        return _hex(fields, idx)

    power = h(29)
    return MaestroState(
        state_code=h(1),
        fan=h(2),
        fumes_temp=h(5),
        ambient_temp=_half(h(6)),
        igniter_on=_flag(h(10)),
        active_set=h(11),
        fumes_fan_rpm=h(12),
        auger_rpm_set=h(13),
        auger_rpm_live=h(14),
        brazier_dirty=_flag(h(17)),
        profile=h(18),
        active_mode=_flag(h(20)),
        active_live=h(21),
        dynamic=_flag(h(22)),
        eco=_flag(h(23)),
        silent=_flag(h(24)),
        chrono=_flag(h(25)),
        setpoint=_half(h(26)),
        board_temp=_half(h(28)),
        power_level=power - 10 if power is not None and 11 <= power <= 15 else None,
        firmware=h(30),
        stove_clock=_clock(fields),
        total_hours=_hours(h(37)),
        power_hours=tuple(_hours(h(i)) for i in range(38, 43)),
        hours_to_service=h(43),
        minutes_to_off=h(44),
        ignitions=h(45),
        active_temp=h(46),
        pellet_sensor=h(47),
        sounds=_flag(h(49)),
        summer=_flag(h(51)),
        antifreeze=h(60),
        raw=(kind, *fields),
    )


def _write(param: int, value: int) -> str:
    return f"{_WRITE}|{param}|{value}"


def cmd_power(on: bool) -> str:
    """Switch the stove on (1) or off (40)."""
    return _write(34, 1 if on else 40)


def cmd_setpoint(temperature: float) -> str:
    """Set the room temperature target, 0.5 °C resolution."""
    return _write(42, round(temperature * 2))


def cmd_power_level(level: int) -> str:
    """Set the manual power level 1-5."""
    if not 1 <= level <= 5:
        raise ValueError(f"power level out of range: {level}")
    return _write(36, level)


def cmd_fan(speed: int) -> str:
    """Set the room fan: 0 off, 1-5, 6 auto."""
    if not 0 <= speed <= 6:
        raise ValueError(f"fan speed out of range: {speed}")
    return _write(37, speed)


def cmd_dynamic(on: bool) -> str:
    """Dynamic (automatic) mode when True, Manual when False."""
    return _write(40, int(on))


def cmd_eco(on: bool) -> str:
    """Eco Stop."""
    return _write(41, int(on))


def cmd_active(on: bool) -> str:
    """Active combustion control."""
    return _write(35, int(on))


def cmd_silent(on: bool) -> str:
    """Silent mode."""
    return _write(45, int(on))


def cmd_sounds(on: bool) -> str:
    """Stove beeps."""
    return _write(50, int(on))


def cmd_chrono(on: bool) -> str:
    """Chronothermostat programme."""
    return _write(1111, int(on))


def cmd_reset_alarm() -> str:
    """Acknowledge the current alarm."""
    return _write(1, 255)


def cmd_set_datetime(moment: datetime) -> str:
    """Set the stove clock."""
    return f"C|SalvaDataOra|{moment:%d%m%Y%H%M}"
