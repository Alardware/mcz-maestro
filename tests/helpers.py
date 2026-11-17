"""Test helpers."""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mcz_maestro.api import MaestroCloud, stove_id
from custom_components.mcz_maestro.const import CONF_MAC, CONF_SERIAL, CONF_URL, DOMAIN

# Production timings (1 s between commands, refresh 2 s later) shrunk for tests.
FAST_CLOUD = functools.partial(
    MaestroCloud, command_interval=0.01, refresh_delay=0.05, backoff=(0.05, 0.2)
)

SERIAL = "1234567890123"
MAC = "0A1B2C3D4E5F"


async def setup_integration(
    hass: HomeAssistant, cloud, *, expect_loaded: bool = True, options: dict | None = None
) -> MockConfigEntry:
    """Add a config entry pointing at the fake cloud and set it up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Poêle",
        unique_id=stove_id(SERIAL),
        data={CONF_SERIAL: SERIAL, CONF_MAC: MAC, CONF_URL: cloud.url},
        options=options or {},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.mcz_maestro.coordinator.MaestroCloud", FAST_CLOUD):
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


async def assert_sent(cloud, *commands: str, timeout: float = 5.0) -> None:
    """Wait until the fake cloud's last received commands are exactly `commands`."""
    expected = list(commands)
    try:
        await wait_for(lambda: cloud.commands[-len(expected):] == expected, timeout)
    except TimeoutError:
        raise AssertionError(f"expected {expected}, got {cloud.commands[-5:]}") from None
