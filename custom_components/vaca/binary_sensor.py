"""Binary Sensor for Wyoming."""

from __future__ import annotations

import asyncio
from asyncio import Task
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    device: VASatelliteDevice = item.device  # type: ignore[assignment]

    # Setup is only forwarded for satellites
    assert item.device is not None

    entities = []

    entities.append(WyomingSatelliteScreenOnBinarySensor(device))

    if capabilities := device.capabilities:
        if capabilities.get("has_battery"):
            entities.append(WyomingSatelliteBatteryChargingBinarySensor(device))
        if capabilities.get("has_front_camera"):
            entities.append(WyomingSatelliteMotionDetectedSensor(device))

    if entities:
        async_add_entities(entities)


class _WyomingSatelliteDeviceBinarySensorBase(
    VASatelliteEntity, BinarySensorEntity, RestoreEntity
):
    """Base class for device sensors."""

    _attr_is_on = False
    _listener_class = "status_update"
    _dont_restore_state = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self._dont_restore_state:
            state = await self.async_get_last_state()
            if state is not None:
                # Restore the state of the binary sensor
                self._attr_is_on = bool(state.state)
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self.status_update,
            )
        )

    def _get_binary_value(self, value: Any) -> Any:
        """Get the binary value from the data."""
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return value

    @callback
    def status_update(self, data: dict[str, Any]) -> None:
        """Update entity."""
        if sensors := data.get("sensors"):
            if self.entity_description.key in sensors:
                self._attr_is_on = self._get_binary_value(
                    sensors[self.entity_description.key]
                )
                self.async_write_ha_state()


class WyomingSatelliteBatteryChargingBinarySensor(
    _WyomingSatelliteDeviceBinarySensorBase
):
    """Entity to represent battery charging sensor for satellite."""

    entity_description = BinarySensorEntityDescription(
        key="battery_charging",
        translation_key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    )


class WyomingSatelliteScreenOnBinarySensor(_WyomingSatelliteDeviceBinarySensorBase):
    """Entity to represent screen on status sensor for satellite."""

    entity_description = BinarySensorEntityDescription(
        key="screen_on", translation_key="screen_on", icon="mdi:monitor"
    )


class WyomingSatelliteMotionDetectedSensor(_WyomingSatelliteDeviceBinarySensorBase):
    """Entity to represent screen on status sensor for satellite."""

    detection_reset_task: Task | None = None
    _dont_restore_state = True
    entity_description = BinarySensorEntityDescription(
        key="motion_detected",
        translation_key="motion_detected",
        icon="mdi:monitor",
        device_class=BinarySensorDeviceClass.MOTION,
    )

    @callback
    def status_update(self, data: dict[str, Any]) -> None:
        """Update entity."""
        super().status_update(data)
        if (
            self.detection_reset_task is not None
            and not self.detection_reset_task.done()
        ):
            self.detection_reset_task.cancel()

        self.detection_reset_task = self.hass.async_create_background_task(
            self.reset_detection(), name="VACA Motion Detection Reset"
        )

    async def reset_detection(self) -> None:
        """Reset motion detection."""
        await asyncio.sleep(20)
        self._attr_is_on = False
        self.schedule_update_ha_state()
