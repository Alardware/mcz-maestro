"""Entities: state from the frame and exact command sent for each action."""

from __future__ import annotations

import re

import pytest
from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE,
)
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.fan import ATTR_PRESET_MODE as FAN_PRESET
from homeassistant.components.fan import (
    DOMAIN as FAN,
)
from homeassistant.components.fan import SERVICE_SET_PRESET_MODE as FAN_SET_PRESET
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.components.select import DOMAIN as SELECT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .helpers import assert_sent, setup_integration, wait_for

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

CLIMATE_ID = "climate.poele"


def _state(hass: HomeAssistant, entity_id: str):
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} missing"
    return state


async def _call(hass, domain, service, entity_id, **data) -> None:
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )


async def test_climate_state(hass: HomeAssistant, fake_cloud) -> None:
    await setup_integration(hass, fake_cloud)
    state = _state(hass, CLIMATE_ID)
    assert state.state == "heat"
    assert state.attributes["current_temperature"] == 18.0
    assert state.attributes[ATTR_TEMPERATURE] == 19.0
    assert state.attributes[ATTR_PRESET_MODE] == "dynamic"
    assert state.attributes[ATTR_HVAC_ACTION] == "heating"
    assert state.attributes["min_temp"] == 5
    assert state.attributes["max_temp"] == 35
    assert state.attributes["target_temp_step"] == 0.5


async def test_climate_commands(hass: HomeAssistant, fake_cloud) -> None:
    await setup_integration(hass, fake_cloud)

    await _call(hass, CLIMATE, SERVICE_TURN_OFF, CLIMATE_ID)
    await assert_sent(fake_cloud, "C|WriteParametri|34|40")
    await wait_for(lambda: _state(hass, CLIMATE_ID).state == "off")
    assert _state(hass, CLIMATE_ID).attributes[ATTR_HVAC_ACTION] == "off"

    await _call(hass, CLIMATE, SERVICE_SET_HVAC_MODE, CLIMATE_ID, **{ATTR_HVAC_MODE: "heat"})
    await assert_sent(fake_cloud, "C|WriteParametri|34|1")
    await wait_for(lambda: _state(hass, CLIMATE_ID).state == "heat")

    await _call(hass, CLIMATE, SERVICE_SET_TEMPERATURE, CLIMATE_ID, **{ATTR_TEMPERATURE: 20.5})
    await assert_sent(fake_cloud, "C|WriteParametri|42|41")
    await wait_for(lambda: _state(hass, CLIMATE_ID).attributes[ATTR_TEMPERATURE] == 20.5)

    await _call(hass, CLIMATE, SERVICE_SET_PRESET_MODE, CLIMATE_ID, **{ATTR_PRESET_MODE: "manual"})
    await assert_sent(fake_cloud, "C|WriteParametri|40|0")
    await wait_for(lambda: _state(hass, CLIMATE_ID).attributes[ATTR_PRESET_MODE] == "manual")

    await _call(hass, CLIMATE, SERVICE_TURN_OFF, CLIMATE_ID)
    await _call(
        hass,
        CLIMATE,
        SERVICE_SET_TEMPERATURE,
        CLIMATE_ID,
        **{ATTR_TEMPERATURE: 21, ATTR_HVAC_MODE: "heat"},
    )
    await assert_sent(fake_cloud, "C|WriteParametri|34|1", "C|WriteParametri|42|42")


async def test_fan(hass: HomeAssistant, fake_cloud) -> None:
    await setup_integration(hass, fake_cloud)
    fan_id = "fan.poele_room_fan"
    state = _state(hass, fan_id)
    assert state.state == "on"
    assert state.attributes[FAN_PRESET] == "auto"
    assert state.attributes[ATTR_PERCENTAGE] is None

    await _call(hass, FAN, SERVICE_SET_PERCENTAGE, fan_id, **{ATTR_PERCENTAGE: 60})
    await assert_sent(fake_cloud, "C|WriteParametri|37|3")
    await wait_for(lambda: _state(hass, fan_id).attributes[ATTR_PERCENTAGE] == 60)
    assert _state(hass, fan_id).attributes[FAN_PRESET] is None

    await _call(hass, FAN, FAN_SET_PRESET, fan_id, **{FAN_PRESET: "auto"})
    await assert_sent(fake_cloud, "C|WriteParametri|37|6")

    await _call(hass, FAN, SERVICE_TURN_OFF, fan_id)
    await assert_sent(fake_cloud, "C|WriteParametri|37|0")
    await wait_for(lambda: _state(hass, fan_id).state == "off")

    await _call(hass, FAN, SERVICE_TURN_ON, fan_id)
    await assert_sent(fake_cloud, "C|WriteParametri|37|6")

    await _call(hass, FAN, SERVICE_TURN_ON, fan_id, **{ATTR_PERCENTAGE: 20})
    await assert_sent(fake_cloud, "C|WriteParametri|37|1")

    await _call(hass, FAN, SERVICE_SET_PERCENTAGE, fan_id, **{ATTR_PERCENTAGE: 0})
    await assert_sent(fake_cloud, "C|WriteParametri|37|0")


async def test_power_select(hass: HomeAssistant, fake_cloud) -> None:
    await setup_integration(hass, fake_cloud)
    select_id = "select.poele_power_level"
    assert _state(hass, select_id).state == "5"
    await _call(hass, SELECT, SERVICE_SELECT_OPTION, select_id, **{ATTR_OPTION: "2"})
    await assert_sent(fake_cloud, "C|WriteParametri|36|2")
    await wait_for(lambda: _state(hass, select_id).state == "2")
    assert _state(hass, "sensor.poele_current_power").state == "2"


@pytest.mark.parametrize(
    ("entity_id", "initial", "service", "command"),
    [
        ("switch.poele_eco_stop", "on", SERVICE_TURN_OFF, "C|WriteParametri|41|0"),
        ("switch.poele_chrono", "on", SERVICE_TURN_OFF, "C|WriteParametri|1111|0"),
        ("switch.poele_silent", "off", SERVICE_TURN_ON, "C|WriteParametri|45|1"),
        ("switch.poele_active", "on", SERVICE_TURN_OFF, "C|WriteParametri|35|0"),
        ("switch.poele_sounds", "on", SERVICE_TURN_OFF, "C|WriteParametri|50|0"),
    ],
)
async def test_switches(hass: HomeAssistant, fake_cloud, entity_id, initial, service, command) -> None:
    await setup_integration(hass, fake_cloud)
    assert _state(hass, entity_id).state == initial
    await _call(hass, "switch", service, entity_id)
    await assert_sent(fake_cloud, command)
    expected = "on" if service == SERVICE_TURN_ON else "off"
    await wait_for(lambda: _state(hass, entity_id).state == expected)


async def test_sensors(hass: HomeAssistant, fake_cloud) -> None:
    await setup_integration(hass, fake_cloud)
    expected = {
        "sensor.poele_state": "power_5",
        "sensor.poele_alarm": "none",
        "sensor.poele_room_temperature": "18.0",
        "sensor.poele_flue_gas_temperature": "120",
        "sensor.poele_setpoint": "19.0",
        "sensor.poele_motherboard_temperature": "23.0",
        "sensor.poele_current_power": "5",
        "sensor.poele_flue_fan_speed": "1886",
        "sensor.poele_auger_speed": "1350",
        "sensor.poele_auger_speed_setpoint": "1400",
        "sensor.poele_active": "166",
        "sensor.poele_active_setpoint": "160",
        "sensor.poele_hours_before_service": "660",
        "sensor.poele_operating_time": "18000.0",
        "sensor.poele_minutes_before_shutdown": "0",
        "sensor.poele_ignitions": "1234",
        "sensor.poele_season": "winter",
    }
    for entity_id, value in expected.items():
        assert _state(hass, entity_id).state == value, entity_id
    assert _state(hass, "sensor.poele_stove_clock").state.startswith("2026-11-17T")
    assert "power_5" in _state(hass, "sensor.poele_state").attributes["options"]


async def test_entity_registry_details(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    registry = er.async_get(hass)
    for entity_id in (
        "sensor.poele_operating_time_power_1",
        "sensor.poele_operating_time_power_5",
        "sensor.poele_profile_raw",
        "sensor.poele_frost_protection_raw",
    ):
        reg_entry = registry.async_get(entity_id)
        assert reg_entry is not None, entity_id
        assert reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get("sensor.poele_flue_fan_speed").entity_category is EntityCategory.DIAGNOSTIC
    assert registry.async_get("switch.poele_sounds").entity_category is EntityCategory.CONFIG
    assert registry.async_get("binary_sensor.poele_mcz_cloud").entity_category is EntityCategory.DIAGNOSTIC
    climate = registry.async_get(CLIMATE_ID)
    assert climate.unique_id == f"{entry.entry_id}_climate"
    assert climate.translation_key == "stove"


async def test_binary_sensors(hass: HomeAssistant, fake_cloud) -> None:
    await setup_integration(hass, fake_cloud)
    assert _state(hass, "binary_sensor.poele_heating").state == "on"
    assert _state(hass, "binary_sensor.poele_alarm").state == "off"
    assert _state(hass, "binary_sensor.poele_igniter").state == "off"
    assert _state(hass, "binary_sensor.poele_brazier_to_clean").state == "off"
    assert _state(hass, "binary_sensor.poele_mcz_cloud").state == "on"
    assert hass.states.get("binary_sensor.poele_pellets_empty") is None


async def test_pellet_sensor_created_when_present(hass: HomeAssistant, fake_cloud) -> None:
    fake_cloud.set_value(47, 11)
    await setup_integration(hass, fake_cloud)
    assert _state(hass, "binary_sensor.poele_pellets_empty").state == "on"


async def test_alarm_entities(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    fake_cloud.set_value(1, 50)
    await entry.runtime_data.cloud.request_info()
    await wait_for(lambda: _state(hass, "sensor.poele_alarm").state == "a01")
    assert _state(hass, "binary_sensor.poele_alarm").state == "on"
    assert _state(hass, "sensor.poele_state").state == "alarm_a01"
    assert _state(hass, CLIMATE_ID).state == "off"

    await _call(hass, "button", "press", "button.poele_reset_alarm")
    await assert_sent(fake_cloud, "C|WriteParametri|1|255")
    await wait_for(lambda: _state(hass, "sensor.poele_alarm").state == "none")


async def test_buttons(hass: HomeAssistant, fake_cloud) -> None:
    await setup_integration(hass, fake_cloud)
    await _call(hass, "button", "press", "button.poele_sync_stove_clock")
    await wait_for(lambda: bool(fake_cloud.commands))
    assert re.fullmatch(r"C\|SalvaDataOra\|\d{12}", fake_cloud.commands[-1])
    before = len([r for r in fake_cloud.requests if r["richiesta"] == "C|RecuperoInfo"])
    await _call(hass, "button", "press", "button.poele_refresh")
    await wait_for(
        lambda: len([r for r in fake_cloud.requests if r["richiesta"] == "C|RecuperoInfo"]) > before
    )


async def test_command_offline_raises(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    await entry.runtime_data.cloud.stop()
    with pytest.raises(HomeAssistantError):
        await _call(hass, "switch", SERVICE_TURN_OFF, "switch.poele_eco_stop")
    with pytest.raises(HomeAssistantError):
        await _call(hass, "button", "press", "button.poele_refresh")
