"""Tests for the MCZ Maestro frame codec."""

from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.mcz_maestro import protocol as p

from .conftest import REFERENCE_FRAME, build_info_frame


def test_reference_frame_matches_info_screen() -> None:
    s = p.parse_info(REFERENCE_FRAME)
    assert s.state_code == 15
    assert s.state_key == "power_5"
    assert s.fan == 6
    assert s.fumes_temp == 120
    assert s.ambient_temp == 18.0
    assert s.igniter_on is False
    assert s.active_set == 160
    assert s.active_live == 166
    assert s.fumes_fan_rpm == 1886
    assert s.auger_rpm_set == 1400
    assert s.auger_rpm_live == 1350
    assert s.brazier_dirty is False
    assert s.profile == 11
    assert s.active_mode is True
    assert s.dynamic is True
    assert s.eco is True
    assert s.silent is False
    assert s.chrono is True
    assert s.setpoint == 19.0
    assert s.board_temp == 23.0
    assert s.power_level == 5
    assert s.firmware == 181
    assert s.stove_clock == datetime(2026, 11, 17, 5, 50)
    assert s.total_hours == 18000.0
    assert s.power_hours == (1000.0, 2000.0, 3000.0, 4000.0, 8000.0)
    assert s.hours_to_service == 660
    assert s.minutes_to_off == 0
    assert s.ignitions == 1234
    assert s.active_temp == 0
    assert s.pellet_sensor == 0
    assert s.pellets_empty is None
    assert s.sounds is True
    assert s.summer is False
    assert s.antifreeze == 0
    assert s.raw[0] == "01"


def test_half_degree_temperatures() -> None:
    s = p.parse_info(build_info_frame({6: 37, 26: 41}))
    assert s.ambient_temp == 18.5
    assert s.setpoint == 20.5


def test_short_and_garbage_fields_become_none() -> None:
    s = p.parse_info("01|f|zz|0|0|0")
    assert s.state_code == 15
    assert s.fan is None
    assert s.fumes_temp == 0
    assert s.ambient_temp is None
    assert s.setpoint is None
    assert s.power_level is None
    assert s.power_hours == (None, None, None, None, None)
    assert s.stove_clock is None


def test_power_level_outside_range_is_none() -> None:
    assert p.parse_info(build_info_frame({29: 0})).power_level is None
    assert p.parse_info(build_info_frame({29: 11})).power_level == 1


def test_two_digit_year() -> None:
    s = p.parse_info(build_info_frame({36: 26}))
    assert s.stove_clock == datetime(2026, 11, 17, 5, 50)


def test_invalid_clock_is_none() -> None:
    assert p.parse_info(build_info_frame({35: 13})).stove_clock is None


def test_parse_info_rejects_other_types() -> None:
    with pytest.raises(ValueError):
        p.parse_info("00|1|2|3")
    with pytest.raises(ValueError):
        p.parse_info("")


def test_parse_frame() -> None:
    assert p.parse_frame("0A|1|2") == ("0A", ["1", "2"])
    assert p.parse_frame("PING") == ("PING", [])


@pytest.mark.parametrize(
    ("code", "key", "on", "heating", "alarm", "alarm_code"),
    [
        (0, "off", False, False, False, None),
        (1, "checking", True, True, False, None),
        (10, "stabilising", True, True, False, None),
        (15, "power_5", True, True, False, None),
        (31, "on", True, True, False, None),
        (40, "extinguishing", False, False, False, None),
        (41, "cooling", False, False, False, None),
        (42, "cleaning_low", True, False, False, None),
        (45, "auto_eco", True, False, False, None),
        (46, "standby", True, False, False, None),
        (50, "alarm_a01", False, False, True, "A01"),
        (67, "alarm_a17", False, False, True, "A17"),
        (69, "waiting_safety_alarms", False, False, True, None),
        (99, "unknown", False, False, False, None),
    ],
)
def test_state_classification(code, key, on, heating, alarm, alarm_code) -> None:
    s = p.parse_info(build_info_frame({1: code}))
    assert s.state_key == key
    assert s.is_on is on
    assert s.is_heating is heating
    assert s.is_alarm is alarm
    assert s.alarm_code == alarm_code


def test_state_options_cover_every_key() -> None:
    assert set(p.STATE_KEYS.values()) | {"unknown"} == set(p.STATE_OPTIONS)
    assert len(p.STATE_OPTIONS) == len(set(p.STATE_OPTIONS))


@pytest.mark.parametrize(("raw", "empty"), [(0, None), (10, False), (11, True)])
def test_pellet_sensor(raw, empty) -> None:
    assert p.parse_info(build_info_frame({47: raw})).pellets_empty is empty


def test_command_builders() -> None:
    assert p.REQUEST_INFO == "C|RecuperoInfo"
    assert p.REQUEST_PARAMS == "RecuperoParametri"
    assert p.cmd_power(True) == "C|WriteParametri|34|1"
    assert p.cmd_power(False) == "C|WriteParametri|34|40"
    assert p.cmd_setpoint(19.5) == "C|WriteParametri|42|39"
    assert p.cmd_setpoint(20) == "C|WriteParametri|42|40"
    assert p.cmd_power_level(3) == "C|WriteParametri|36|3"
    assert p.cmd_fan(6) == "C|WriteParametri|37|6"
    assert p.cmd_fan(0) == "C|WriteParametri|37|0"
    assert p.cmd_dynamic(True) == "C|WriteParametri|40|1"
    assert p.cmd_dynamic(False) == "C|WriteParametri|40|0"
    assert p.cmd_eco(True) == "C|WriteParametri|41|1"
    assert p.cmd_active(False) == "C|WriteParametri|35|0"
    assert p.cmd_silent(True) == "C|WriteParametri|45|1"
    assert p.cmd_sounds(False) == "C|WriteParametri|50|0"
    assert p.cmd_chrono(True) == "C|WriteParametri|1111|1"
    assert p.cmd_reset_alarm() == "C|WriteParametri|1|255"
    assert p.cmd_set_datetime(datetime(2026, 11, 17, 6, 30)) == "C|SalvaDataOra|171120260630"


@pytest.mark.parametrize("bad", [0, 6, -1])
def test_power_level_bounds(bad) -> None:
    with pytest.raises(ValueError):
        p.cmd_power_level(bad)


@pytest.mark.parametrize("bad", [-1, 7])
def test_fan_bounds(bad) -> None:
    with pytest.raises(ValueError):
        p.cmd_fan(bad)


def test_setpoint_rounds_to_half_degree() -> None:
    assert p.cmd_setpoint(19.26) == "C|WriteParametri|42|39"
