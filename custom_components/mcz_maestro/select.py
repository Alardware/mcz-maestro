"""Manual power level 1-5."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaestroConfigEntry, MaestroCoordinator
from .entity import MaestroEntity
from .protocol import cmd_power_level

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaestroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MaestroPowerSelect(entry.runtime_data)])


class MaestroPowerSelect(MaestroEntity, SelectEntity):
    """Power level used in Manual mode."""

    _attr_translation_key = "power_level"
    _attr_options = ["1", "2", "3", "4", "5"]

    def __init__(self, coordinator: MaestroCoordinator) -> None:
        super().__init__(coordinator, "power_level")

    @property
    def current_option(self) -> str | None:
        level = self.state_data.power_level
        return None if level is None else str(level)

    async def async_select_option(self, option: str) -> None:
        await self._send(cmd_power_level(int(option)))
