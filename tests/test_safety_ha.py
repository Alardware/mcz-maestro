"""Safety features wired into Home Assistant."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.mcz_maestro.const import (
    CONF_OVERHEAT_TEMP,
    CONF_SAFETY_DELAY,
    CONF_SAFETY_NOTIFY,
    CONF_SAFETY_OVERHEAT,
    CONF_SAFETY_REVERT,
    CONF_SCAN_INTERVAL,
    CONF_SHUTDOWN_TEMP,
    DOMAIN,
    EVENT_SAFETY,
)
from custom_components.mcz_maestro.safety import SafetyConfig

from .helpers import assert_sent, setup_integration, wait_for

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

NOTIFY = "custom_components.mcz_maestro.coordinator.persistent_notification.async_create"


def fast(entry, delay: float = 0.3) -> None:
    """Shrink the revert delay to fractions of a second."""
    guard = entry.runtime_data.safety
    old = guard.config
    guard.config = SafetyConfig(
        revert=old.revert,
        delay=delay,
        overheat=old.overheat,
        overheat_temp=old.overheat_temp,
        shutdown_temp=old.shutdown_temp,
    )


async def _push(entry, cloud, **values: int) -> None:
    for idx, value in values.items():
        cloud.set_value(int(idx.removeprefix("i")), value)
    await entry.runtime_data.cloud.request_info()


async def test_eco_restored_after_delay(hass: HomeAssistant, fake_cloud) -> None:
    events = async_capture_events(hass, EVENT_SAFETY)
    with patch(NOTIFY) as notify:
        entry = await setup_integration(hass, fake_cloud)
        fast(entry)
        await _push(entry, fake_cloud, i23=0)
        await wait_for(lambda: hass.states.get("switch.poele_eco_stop").state == "off")
        await asyncio.sleep(0.35)
        await entry.runtime_data.cloud.request_info()
        await assert_sent(fake_cloud, "C|WriteParametri|41|1")
        await wait_for(lambda: len(events) == 1)
        await wait_for(lambda: hass.states.get("switch.poele_eco_stop").state == "on")
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert events[0].data["action"] == "eco_restored"
    assert events[0].data["device_id"] == device.id
    assert "Eco Stop" in events[0].data["label"]
    notify.assert_called_once()
    assert "Eco Stop" in notify.call_args.args[1]


async def test_dynamic_restored_after_delay(hass: HomeAssistant, fake_cloud) -> None:
    events = async_capture_events(hass, EVENT_SAFETY)
    with patch(NOTIFY):
        entry = await setup_integration(hass, fake_cloud)
        fast(entry)
        await _push(entry, fake_cloud, i22=0)
        await wait_for(lambda: hass.states.get("climate.poele").attributes["preset_mode"] == "manual")
        await asyncio.sleep(0.35)
        await entry.runtime_data.cloud.request_info()
        await assert_sent(fake_cloud, "C|WriteParametri|40|1")
        await wait_for(lambda: len(events) == 1)
    assert events[0].data["action"] == "dynamic_restored"


async def test_overheat_restores_immediately(hass: HomeAssistant, fake_cloud) -> None:
    events = async_capture_events(hass, EVENT_SAFETY)
    with patch(NOTIFY) as notify:
        entry = await setup_integration(hass, fake_cloud)
        await _push(entry, fake_cloud, i6=56, i22=0, i23=0)  # 28 °C, Manual, Eco off
        await assert_sent(fake_cloud, "C|WriteParametri|41|1", "C|WriteParametri|40|1")
        await wait_for(lambda: len(events) == 1)
    assert events[0].data["action"] == "overheat"
    assert events[0].data["temperature"] == 28.0
    assert "28" in notify.call_args.args[1]


async def test_shutdown_above_limit(hass: HomeAssistant, fake_cloud) -> None:
    events = async_capture_events(hass, EVENT_SAFETY)
    with patch(NOTIFY):
        entry = await setup_integration(hass, fake_cloud)
        await _push(entry, fake_cloud, i6=62)  # 31 °C
        await assert_sent(fake_cloud, "C|WriteParametri|34|40")
        await wait_for(lambda: len(events) == 1)
        await wait_for(lambda: hass.states.get("climate.poele").state == "off")
    assert events[0].data["action"] == "shutdown"


async def test_notification_can_be_disabled(hass: HomeAssistant, fake_cloud) -> None:
    events = async_capture_events(hass, EVENT_SAFETY)
    with patch(NOTIFY) as notify:
        entry = await setup_integration(hass, fake_cloud, options={CONF_SAFETY_NOTIFY: False})
        await _push(entry, fake_cloud, i6=56, i23=0)
        await assert_sent(fake_cloud, "C|WriteParametri|41|1")
        await wait_for(lambda: len(events) == 1)
    notify.assert_not_called()


async def test_safeties_can_be_disabled(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(
        hass, fake_cloud, options={CONF_SAFETY_REVERT: False, CONF_SAFETY_OVERHEAT: False}
    )
    fast(entry, 0.05)
    await _push(entry, fake_cloud, i6=70, i22=0, i23=0)
    await asyncio.sleep(0.2)
    await entry.runtime_data.cloud.request_info()
    await asyncio.sleep(0.2)
    assert fake_cloud.commands == []


async def test_notification_text_follows_language(hass: HomeAssistant, fake_cloud) -> None:
    hass.config.language = "fr"
    with patch(NOTIFY) as notify:
        entry = await setup_integration(hass, fake_cloud)
        await _push(entry, fake_cloud, i6=62)
        await wait_for(lambda: notify.called)
    title, message = notify.call_args.args[2], notify.call_args.args[1]
    assert "31" in message and "éteint" in message
    assert "Sécurité" in title


async def test_climate_shows_restore_times(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    attrs = hass.states.get("climate.poele").attributes
    assert attrs["eco_stop_restore_at"] is None
    assert attrs["dynamic_restore_at"] is None
    await _push(entry, fake_cloud, i22=0, i23=0)
    await wait_for(lambda: hass.states.get("climate.poele").attributes["dynamic_restore_at"] is not None)
    attrs = hass.states.get("climate.poele").attributes
    assert attrs["eco_stop_restore_at"].endswith("+00:00")
    assert attrs["eco_stop_restore_at"][17:19] == "00"  # whole minutes: no jitter in history


async def test_options_flow_safety(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    bad = {
        CONF_SCAN_INTERVAL: 30,
        CONF_SAFETY_REVERT: True,
        CONF_SAFETY_DELAY: 60,
        CONF_SAFETY_OVERHEAT: True,
        CONF_OVERHEAT_TEMP: 28,
        CONF_SHUTDOWN_TEMP: 27,
        CONF_SAFETY_NOTIFY: True,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], bad)
    assert result["errors"] == {CONF_SHUTDOWN_TEMP: "shutdown_below_overheat"}
    good = {**bad, CONF_SAFETY_DELAY: 30, CONF_SHUTDOWN_TEMP: 31}
    result = await hass.config_entries.options.async_configure(result["flow_id"], good)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_SAFETY_DELAY] == 30
    assert entry.runtime_data.safety.config.delay == 1800
    assert entry.runtime_data.safety.config.shutdown_temp == 31
