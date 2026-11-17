"""Reset alarm, sync stove clock, refresh."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import NotConnected
from .const import DOMAIN
from .coordinator import MaestroConfigEntry, MaestroCoordinator
from .entity import MaestroEntity
from .protocol import cmd_reset_alarm, cmd_set_datetime

PARALLEL_UPDATES = 0


async def _refresh(coordinator: MaestroCoordinator) -> None:
    try:
        await coordinator.cloud.request_info()
    except NotConnected as err:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="not_connected") from err


@dataclass(frozen=True, kw_only=True)
class MaestroButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[MaestroCoordinator], Awaitable[None]]


BUTTONS: tuple[MaestroButtonDescription, ...] = (
    MaestroButtonDescription(
        key="reset_alarm",
        translation_key="reset_alarm",
        press_fn=lambda c: c.async_send(cmd_reset_alarm()),
    ),
    MaestroButtonDescription(
        key="sync_clock",
        translation_key="sync_clock",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c: c.async_send(cmd_set_datetime(dt_util.now())),
    ),
    MaestroButtonDescription(
        key="refresh",
        translation_key="refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=_refresh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaestroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(MaestroButton(entry.runtime_data, d) for d in BUTTONS)


class MaestroButton(MaestroEntity, ButtonEntity):
    """One-shot action."""

    entity_description: MaestroButtonDescription

    def __init__(self, coordinator: MaestroCoordinator, description: MaestroButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)
