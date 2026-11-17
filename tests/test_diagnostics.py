"""Diagnostics: raw frames for phase 2, identifiers never leaked."""

from __future__ import annotations

import json

import pytest
from homeassistant.core import HomeAssistant

from custom_components.mcz_maestro.diagnostics import async_get_config_entry_diagnostics

from .helpers import MAC, SERIAL, setup_integration, wait_for

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_diagnostics(hass: HomeAssistant, fake_cloud) -> None:
    entry = await setup_integration(hass, fake_cloud)
    cloud = entry.runtime_data.cloud
    await wait_for(lambda: cloud.last_params_raw is not None)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["frames"]["info"].startswith("01|")
    assert diag["frames"]["params"].startswith("00|")
    assert diag["cloud"]["connected"] is True
    assert diag["cloud"]["transport"] == "websocket"
    assert diag["cloud"]["eio"] == 3
    assert diag["state"]["setpoint"] == 19.0
    assert diag["state"]["state_key"] == "power_5"
    assert diag["state"]["stove_clock"].startswith("2026-11-17T05:50")

    dump = json.dumps(diag)
    assert SERIAL not in dump
    assert MAC not in dump
    assert MAC.lower() not in dump
    assert "**REDACTED**" in dump
