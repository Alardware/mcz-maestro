"""Stove thermostat: on/off, setpoint, Dynamic/Manual mode."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaestroConfigEntry, MaestroCoordinator
from .entity import MaestroEntity
from .protocol import cmd_dynamic, cmd_power, cmd_setpoint

PRESET_DYNAMIC = "dynamic"
PRESET_MANUAL = "manual"

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaestroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MaestroClimate(entry.runtime_data)])


class MaestroClimate(MaestroEntity, ClimateEntity):
    """The stove as a thermostat."""

    _attr_name = None
    _attr_translation_key = "stove"
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_DYNAMIC, PRESET_MANUAL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 5
    _attr_max_temp = 35

    def __init__(self, coordinator: MaestroCoordinator) -> None:
        super().__init__(coordinator, "climate")

    @property
    def current_temperature(self) -> float | None:
        return self.state_data.ambient_temp

    @property
    def target_temperature(self) -> float | None:
        return self.state_data.setpoint

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self.state_data.is_on else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        if self.state_data.is_heating:
            return HVACAction.HEATING
        if self.state_data.is_on:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def preset_mode(self) -> str | None:
        if self.state_data.dynamic is None:
            return None
        return PRESET_DYNAMIC if self.state_data.dynamic else PRESET_MANUAL

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._send(cmd_power(hvac_mode == HVACMode.HEAT))

    async def async_turn_on(self) -> None:
        await self._send(cmd_power(True))

    async def async_turn_off(self) -> None:
        await self._send(cmd_power(False))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(mode)
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._send(cmd_setpoint(temperature))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._send(cmd_dynamic(preset_mode == PRESET_DYNAMIC))
