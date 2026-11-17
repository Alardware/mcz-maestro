"""Test helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mcz_maestro.const import CONF_MAC, CONF_SERIAL, CONF_URL, DOMAIN

SERIAL = "1234567890123"
MAC = "0A1B2CA137E0"


async def setup_integration(
    hass: HomeAssistant, cloud, *, expect_loaded: bool = True, options: dict | None = None
) -> MockConfigEntry:
    """Add a config entry pointing at the fake cloud and set it up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Poêle",
        unique_id=SERIAL,
        data={CONF_SERIAL: SERIAL, CONF_MAC: MAC, CONF_URL: cloud.url},
        options=options or {},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if expect_loaded:
        assert entry.state is ConfigEntryState.LOADED
    return entry


async def wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    """Poll until predicate() is true."""
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.02)
