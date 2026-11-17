"""Eco Stop, Chrono, Silent, Active, sounds."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaestroConfigEntry, MaestroCoordinator
from .entity import MaestroEntity
from .protocol import (
    MaestroState,
    cmd_active,
    cmd_chrono,
    cmd_eco,
    cmd_silent,
    cmd_sounds,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MaestroSwitchDescription(SwitchEntityDescription):
    value_fn: Callable[[MaestroState], bool | None]
    command_fn: Callable[[bool], str]


SWITCHES: tuple[MaestroSwitchDescription, ...] = (
    MaestroSwitchDescription(
        key="eco", translation_key="eco", value_fn=lambda s: s.eco, command_fn=cmd_eco
    ),
    MaestroSwitchDescription(
        key="chrono", translation_key="chrono", value_fn=lambda s: s.chrono, command_fn=cmd_chrono
    ),
    MaestroSwitchDescription(
        key="silent", translation_key="silent", value_fn=lambda s: s.silent, command_fn=cmd_silent
    ),
    MaestroSwitchDescription(
        key="active",
        translation_key="active",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.active_mode,
        command_fn=cmd_active,
    ),
    MaestroSwitchDescription(
        key="sounds",
        translation_key="sounds",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.sounds,
        command_fn=cmd_sounds,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaestroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(MaestroSwitch(entry.runtime_data, d) for d in SWITCHES)


class MaestroSwitch(MaestroEntity, SwitchEntity):
    """On/off stove setting."""

    entity_description: MaestroSwitchDescription

    def __init__(self, coordinator: MaestroCoordinator, description: MaestroSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.state_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(self.entity_description.command_fn(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(self.entity_description.command_fn(False))
