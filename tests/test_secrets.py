"""The serial number and MAC address (the stove's cloud credentials) never leak.

They may only appear in the config entry data and in what is sent to the MCZ cloud.
Checked here: logs (DEBUG, every logger), registries, states, events, diagnostics,
error messages.
"""

from __future__ import annotations

import json
import logging
import re
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.mcz_maestro.const import (
    CONF_MAC,
    CONF_SERIAL,
    DOMAIN,
    EVENT_ALARM,
)
from custom_components.mcz_maestro.diagnostics import async_get_config_entry_diagnostics

from .helpers import MAC, SERIAL, setup_integration, wait_for

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

# Every spelling a leak could take.
_MAC_PAIRS = [MAC[i : i + 2] for i in range(0, 12, 2)]
PATTERNS = [
    re.compile(re.escape(SERIAL)),
    re.compile(r"[\s\-]?".join(_MAC_PAIRS), re.IGNORECASE),
    re.compile(r"[:\-]".join(_MAC_PAIRS), re.IGNORECASE),
]


def assert_clean(text: str, where: str) -> None:
    for pattern in PATTERNS:
        match = pattern.search(text)
        assert match is None, f"identifier leaked in {where}: …{text[max(0, match.start() - 60):match.end() + 20]}…"


@pytest.fixture
def debug_logs(caplog):
    caplog.set_level(logging.DEBUG)
    return caplog


async def test_full_lifecycle_never_leaks(hass: HomeAssistant, fake_cloud, debug_logs) -> None:
    events = async_capture_events(hass, EVENT_ALARM)
    entry = await setup_integration(hass, fake_cloud)
    coordinator = entry.runtime_data

    # Commands, alarm, malformed traffic, disconnect/reconnect, stale data.
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": "climate.poele", "temperature": 21}, blocking=True
    )
    fake_cloud.set_value(1, 50)
    await coordinator.cloud.request_info()
    await wait_for(lambda: len(events) == 1)
    await fake_cloud.push_raw('42["rispondo",{"serialNumber":"' + SERIAL + '","x":')
    await fake_cloud.push_event("rispondo", {"serialNumber": SERIAL, "macAddress": MAC, "stringaRicevuta": "0A|1"})
    await fake_cloud.drop_all()
    await wait_for(lambda: coordinator.cloud.connected)
    with patch("custom_components.mcz_maestro.coordinator.STALE_AFTER", -1):
        await coordinator.async_refresh()

    # Registries, states and events.
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        assert_clean(repr(device), "device registry")
        assert device.serial_number is None
    for reg_entry in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        assert_clean(repr(reg_entry), "entity registry")
    for state in hass.states.async_all():
        assert_clean(repr(state), f"state {state.entity_id}")
    assert_clean(repr([e.data for e in events]), "alarm event")
    assert_clean(entry.unique_id, "config entry unique_id")
    assert_clean(repr(entry), "config entry repr")

    # Diagnostics.
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert_clean(json.dumps(diag), "diagnostics")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Every log line, at DEBUG, from every logger.
    assert_clean(debug_logs.text, "logs")
    # The credentials really were used (the test would be meaningless otherwise).
    assert entry.data[CONF_SERIAL] == SERIAL
    assert fake_cloud.joins[0]["serialNumber"] == SERIAL


async def test_config_flow_errors_never_leak(
    hass: HomeAssistant, dead_url, fake_cloud_factory, debug_logs
) -> None:
    silent = await fake_cloud_factory(respond=False)
    user_input = {CONF_NAME: "Poêle", CONF_SERIAL: SERIAL, CONF_MAC: MAC}
    with patch("custom_components.mcz_maestro.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        for url, error in ((dead_url, "cannot_connect"), (silent.url, "no_response")):
            with (
                patch("custom_components.mcz_maestro.config_flow.DEFAULT_URL", url),
                patch("custom_components.mcz_maestro.config_flow.VALIDATE_TIMEOUT", 0.3),
            ):
                result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
            assert result["errors"] == {"base": error}
            assert_clean(json.dumps(result, default=str), f"flow result ({error})")
        with patch(
            "custom_components.mcz_maestro.config_flow.async_validate",
            side_effect=RuntimeError(f"boom {SERIAL} {MAC}"),
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
        assert result["errors"] == {"base": "unknown"}
    # The unexpected-error path logs a traceback: the exception text must not carry
    # identifiers into the log.
    assert_clean(debug_logs.text, "config flow logs")
