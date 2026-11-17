"""MCZ Maestro (legacy app) integration: pellet stove through the MCZ cloud."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import CARD_URL, DOMAIN
from .coordinator import MaestroConfigEntry, MaestroCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_CARD_FILE = Path(__file__).parent / "frontend" / "mcz-maestro-card.js"
_CARD_REGISTERED = f"{DOMAIN}_card_registered"


async def async_register_card(hass: HomeAssistant, version: str) -> None:
    """Serve the Lovelace card and load it in every dashboard (once)."""
    if getattr(hass, "http", None) is None or hass.data.get(_CARD_REGISTERED):
        return
    hass.data[_CARD_REGISTERED] = True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(_CARD_FILE), cache_headers=False)]
    )
    if "frontend" in hass.config.components:
        add_extra_js_url(hass, f"{CARD_URL}?v={version}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> None | bool:
    """Register the card when the integration is loaded."""
    integration = await async_get_integration(hass, DOMAIN)
    await async_register_card(hass, str(integration.version))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MaestroConfigEntry) -> bool:
    """Connect to the stove and create its entities."""
    coordinator = MaestroCoordinator(hass, entry)
    await coordinator.async_start()
    entry.runtime_data = coordinator

    async def _stop(_: Event) -> None:
        await coordinator.async_stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop))
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: MaestroConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MaestroConfigEntry) -> bool:
    """Disconnect and remove entities."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
