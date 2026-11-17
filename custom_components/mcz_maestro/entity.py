"""Base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import MaestroCoordinator
from .protocol import MaestroState


class MaestroEntity(CoordinatorEntity[MaestroCoordinator]):
    """Entity attached to the stove device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MaestroCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial}_{key}"
        firmware = coordinator.data.firmware if coordinator.data else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            name=coordinator.config_entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=coordinator.serial,
            sw_version=str(firmware) if firmware is not None else None,
        )

    @property
    def state_data(self) -> MaestroState:
        """Latest decoded frame."""
        return self.coordinator.data

    async def _send(self, command: str) -> None:
        await self.coordinator.async_send(command)
