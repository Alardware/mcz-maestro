"""Stove measurements and counters (the app's "Info" screen)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import MaestroConfigEntry, MaestroCoordinator
from .entity import MaestroEntity
from .protocol import ALARM_LABELS, STATE_OPTIONS, MaestroState

PARALLEL_UPDATES = 0

ALARM_OPTIONS = ["none", *(code.lower() for code in ALARM_LABELS), "safety"]


def _alarm(state: MaestroState) -> str:
    return state.alarm_key or "none"


def _clock(state: MaestroState) -> datetime | None:
    if state.stove_clock is None:
        return None
    return state.stove_clock.replace(tzinfo=dt_util.get_default_time_zone())


@dataclass(frozen=True, kw_only=True)
class MaestroSensorDescription(SensorEntityDescription):
    value_fn: Callable[[MaestroState], object]


_TEMP = {
    "device_class": SensorDeviceClass.TEMPERATURE,
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
    "state_class": SensorStateClass.MEASUREMENT,
}
_DIAG = {"entity_category": EntityCategory.DIAGNOSTIC}
_HOURS = {
    "device_class": SensorDeviceClass.DURATION,
    "native_unit_of_measurement": UnitOfTime.HOURS,
    "state_class": SensorStateClass.TOTAL_INCREASING,
    "suggested_display_precision": 0,
    "entity_category": EntityCategory.DIAGNOSTIC,
}
_RPM = {
    "native_unit_of_measurement": REVOLUTIONS_PER_MINUTE,
    "state_class": SensorStateClass.MEASUREMENT,
    "entity_category": EntityCategory.DIAGNOSTIC,
}

SENSORS: tuple[MaestroSensorDescription, ...] = (
    MaestroSensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_OPTIONS,
        value_fn=lambda s: s.state_key,
    ),
    MaestroSensorDescription(
        key="alarm", translation_key="alarm", device_class=SensorDeviceClass.ENUM,
        options=ALARM_OPTIONS, value_fn=_alarm,
    ),
    MaestroSensorDescription(
        key="ambient_temp", translation_key="ambient_temp", value_fn=lambda s: s.ambient_temp, **_TEMP
    ),
    MaestroSensorDescription(
        key="fumes_temp", translation_key="fumes_temp", value_fn=lambda s: s.fumes_temp, **_TEMP
    ),
    MaestroSensorDescription(
        key="setpoint", translation_key="setpoint", value_fn=lambda s: s.setpoint, **_TEMP, **_DIAG
    ),
    MaestroSensorDescription(
        key="board_temp", translation_key="board_temp", value_fn=lambda s: s.board_temp, **_TEMP, **_DIAG
    ),
    MaestroSensorDescription(
        key="power", translation_key="power", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.power_level,
    ),
    MaestroSensorDescription(
        key="fumes_fan_rpm", translation_key="fumes_fan_rpm", value_fn=lambda s: s.fumes_fan_rpm, **_RPM
    ),
    MaestroSensorDescription(
        key="auger_rpm", translation_key="auger_rpm", value_fn=lambda s: s.auger_rpm_live, **_RPM
    ),
    MaestroSensorDescription(
        key="auger_rpm_set", translation_key="auger_rpm_set", value_fn=lambda s: s.auger_rpm_set, **_RPM
    ),
    MaestroSensorDescription(
        key="active_live", translation_key="active_live", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.active_live, **_DIAG,
    ),
    MaestroSensorDescription(
        key="active_set", translation_key="active_set", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.active_set, **_DIAG,
    ),
    MaestroSensorDescription(
        key="hours_to_service",
        translation_key="hours_to_service",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.hours_to_service,
    ),
    MaestroSensorDescription(
        key="total_hours", translation_key="total_hours", value_fn=lambda s: s.total_hours, **_HOURS
    ),
    *(
        MaestroSensorDescription(
            key=f"power_{n}_hours",
            translation_key=f"power_{n}_hours",
            entity_registry_enabled_default=False,
            value_fn=lambda s, i=n - 1: s.power_hours[i],
            **_HOURS,
        )
        for n in range(1, 6)
    ),
    MaestroSensorDescription(
        key="minutes_to_off",
        translation_key="minutes_to_off",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda s: s.minutes_to_off,
        **_DIAG,
    ),
    MaestroSensorDescription(
        key="ignitions", translation_key="ignitions", state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.ignitions, **_DIAG,
    ),
    MaestroSensorDescription(
        key="season", translation_key="season", device_class=SensorDeviceClass.ENUM,
        options=["winter", "summer"],
        value_fn=lambda s: None if s.summer is None else ("summer" if s.summer else "winter"),
        **_DIAG,
    ),
    MaestroSensorDescription(
        key="stove_clock", translation_key="stove_clock", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_clock, **_DIAG,
    ),
    MaestroSensorDescription(
        key="profile", translation_key="profile", entity_registry_enabled_default=False,
        value_fn=lambda s: s.profile, **_DIAG,
    ),
    MaestroSensorDescription(
        key="antifreeze", translation_key="antifreeze", entity_registry_enabled_default=False,
        value_fn=lambda s: s.antifreeze, **_DIAG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaestroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(MaestroSensor(entry.runtime_data, d) for d in SENSORS)


class MaestroSensor(MaestroEntity, SensorEntity):
    """Read-only stove value."""

    entity_description: MaestroSensorDescription

    def __init__(self, coordinator: MaestroCoordinator, description: MaestroSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.state_data)
