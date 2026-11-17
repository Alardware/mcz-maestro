"""Room (front) fan: 5 speeds + automatic."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .coordinator import MaestroConfigEntry, MaestroCoordinator
from .entity import MaestroEntity
from .protocol import cmd_fan

PRESET_AUTO = "auto"
FAN_AUTO = 6
SPEED_RANGE = (1, 5)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaestroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MaestroFan(entry.runtime_data)])


class MaestroFan(MaestroEntity, FanEntity):
    """Room fan."""

    _attr_translation_key = "room_fan"
    _attr_speed_count = 5
    _attr_preset_modes = [PRESET_AUTO]
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: MaestroCoordinator) -> None:
        super().__init__(coordinator, "room_fan")

    @property
    def is_on(self) -> bool | None:
        fan = self.state_data.fan
        return None if fan is None else fan != 0

    @property
    def percentage(self) -> int | None:
        fan = self.state_data.fan
        if fan is None or fan == FAN_AUTO:
            return None
        if fan == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, min(fan, 5))

    @property
    def preset_mode(self) -> str | None:
        return PRESET_AUTO if self.state_data.fan == FAN_AUTO else None

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self._send(cmd_fan(speed))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._send(cmd_fan(FAN_AUTO))

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any
    ) -> None:
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._send(cmd_fan(FAN_AUTO))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(cmd_fan(0))
