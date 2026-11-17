"""Heating, igniter, alarm, brazier, pellets, cloud link."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaestroConfigEntry, MaestroCoordinator
from .entity import MaestroEntity
from .protocol import MaestroState

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MaestroBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[MaestroState], bool | None]


BINARY_SENSORS: tuple[MaestroBinaryDescription, ...] = (
    MaestroBinaryDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda s: s.is_heating,
    ),
    MaestroBinaryDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: s.is_alarm,
    ),
    MaestroBinaryDescription(
        key="igniter",
        translation_key="igniter",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.igniter_on,
    ),
    MaestroBinaryDescription(
        key="brazier",
        translation_key="brazier",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: s.brazier_dirty,
    ),
)

PELLETS = MaestroBinaryDescription(
    key="pellets_empty",
    translation_key="pellets_empty",
    device_class=BinarySensorDeviceClass.PROBLEM,
    value_fn=lambda s: s.pellets_empty,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaestroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        MaestroBinarySensor(coordinator, d) for d in BINARY_SENSORS
    ]
    if coordinator.data.pellet_sensor in (10, 11):
        entities.append(MaestroBinarySensor(coordinator, PELLETS))
    entities.append(MaestroCloudSensor(coordinator))
    async_add_entities(entities)


class MaestroBinarySensor(MaestroEntity, BinarySensorEntity):
    """Boolean stove value."""

    entity_description: MaestroBinaryDescription

    def __init__(self, coordinator: MaestroCoordinator, description: MaestroBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.state_data)


class MaestroCloudSensor(MaestroEntity, BinarySensorEntity):
    """Link to the MCZ cloud (stays available when everything else is not)."""

    _attr_translation_key = "cloud"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MaestroCoordinator) -> None:
        super().__init__(coordinator, "cloud")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.cloud.connected
