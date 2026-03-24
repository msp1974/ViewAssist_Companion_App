from __future__ import annotations

import logging

from homeassistant.core import callback
from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .devices import VASatelliteDevice

_LOGGER = logging.getLogger(__name__)


class VASatelliteEntity(entity.Entity):
    """VACA satellite entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: VASatelliteDevice) -> None:
        """Initialize entity."""
        self._device = device
        self._attr_unique_id = f"{device.satellite_id}-{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.satellite_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_connectivity",
                self._update_connectivity,
            )
        )

    @callback
    def _update_connectivity(self) -> None:
        """Update entity availability."""
        try:
            self.async_write_ha_state()
        except (ValueError, AttributeError) as err:
            _LOGGER.warning(
                "Error writing state during connectivity update: key=%s value=%s",
                self.entity_id,
                err,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device.is_connected
