"""Setup, unload, availability and alarm event."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.mcz_maestro import async_register_card
from custom_components.mcz_maestro.const import CARD_URL, DOMAIN, EVENT_ALARM

from .helpers import setup_integration, wait_for

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_setup_and_unload(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.poele") is not None
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device.manufacturer == "MCZ"
    assert device.name == "Poêle"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    await wait_for(lambda: not fake_cloud.active_sessions)


async def test_setup_retry_without_first_frame(hass: HomeAssistant, fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(respond=False)
    with patch("custom_components.mcz_maestro.coordinator.FIRST_FRAME_TIMEOUT", 0.3):
        entry = await setup_integration(hass, cloud, expect_loaded=False)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    await wait_for(lambda: not cloud.active_sessions)


async def test_stale_data_makes_entities_unavailable(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    coordinator = entry.runtime_data
    fake_cloud.respond = False
    with patch("custom_components.mcz_maestro.coordinator.STALE_AFTER", 0.2):
        await asyncio.sleep(0.3)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("climate.poele").state == STATE_UNAVAILABLE
        assert hass.states.get("binary_sensor.poele_mcz_cloud").state == "on"
        fake_cloud.respond = True
        await coordinator.cloud.request_info()
        await wait_for(lambda: hass.states.get("climate.poele").state != STATE_UNAVAILABLE)


async def test_connectivity_sensor_follows_link(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    assert hass.states.get("binary_sensor.poele_mcz_cloud").state == "on"
    with patch.object(entry.runtime_data.cloud, "_backoff", (5.0, 5.0)):
        await fake_cloud.drop_all()
        await wait_for(lambda: hass.states.get("binary_sensor.poele_mcz_cloud").state == "off")


async def test_alarm_event_fired_once_per_alarm(hass: HomeAssistant, fake_cloud) -> None:
    events = async_capture_events(hass, EVENT_ALARM)
    entry = await setup_integration(hass, fake_cloud)
    cloud = entry.runtime_data.cloud
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    fake_cloud.set_value(1, 50)
    await cloud.request_info()
    await wait_for(lambda: len(events) == 1)
    assert events[0].data == {
        "device_id": device.id,
        "code": "A01",
        "state": "alarm_a01",
        "label": "A01 – Ignition failed",
    }
    await cloud.request_info()
    await asyncio.sleep(0.2)
    assert len(events) == 1

    fake_cloud.set_value(1, 0)
    await cloud.request_info()
    await asyncio.sleep(0.2)
    fake_cloud.set_value(1, 51)
    await cloud.request_info()
    await wait_for(lambda: len(events) == 2)
    assert events[1].data["code"] == "A02"


@pytest.mark.parametrize(
    ("language", "label"),
    [
        ("fr", "A01 – Allumage raté"),
        ("en", "A01 – Ignition failed"),
        ("it", "A01 – Accensione fallita"),
        ("de", "A01 – Zündung fehlgeschlagen"),
        ("es", "A01 – Ignition failed"),
    ],
)
async def test_alarm_label_follows_ha_language(
    hass: HomeAssistant, fake_cloud, language, label
) -> None:
    hass.config.language = language
    events = async_capture_events(hass, EVENT_ALARM)
    entry = await setup_integration(hass, fake_cloud)
    fake_cloud.set_value(1, 50)
    await entry.runtime_data.cloud.request_info()
    await wait_for(lambda: len(events) == 1)
    assert events[0].data["label"] == label


async def test_card_registration() -> None:
    hass = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.config.components = {"frontend", "http"}
    hass.data = {}
    with patch("custom_components.mcz_maestro.add_extra_js_url") as add_js:
        await async_register_card(hass, "0.1.0")
        await async_register_card(hass, "0.1.0")
    paths = hass.http.async_register_static_paths.call_args.args[0]
    assert paths[0].url_path == CARD_URL
    assert paths[0].path.endswith("frontend/mcz-maestro-card.js")
    add_js.assert_called_once_with(hass, f"{CARD_URL}?v=0.1.0")
    assert hass.http.async_register_static_paths.call_count == 1


async def test_card_registration_without_http() -> None:
    hass = MagicMock()
    hass.http = None
    hass.data = {}
    await async_register_card(hass, "0.1.0")
