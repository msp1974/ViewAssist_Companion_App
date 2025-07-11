"""Wyoming button entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.device is not None

    async_add_entities(
        [
            WyomingSatelliteScreenWakeButton(item.device),
        ]
    )


class WyomingSatelliteScreenWakeButton(VASatelliteEntity, ButtonEntity):
    """Entity to represent if satellite is muted."""

    entity_description = ButtonEntityDescription(
        key="wake_screen", translation_key="wake_screen", icon="mdi:monitor-screenshot"
    )
    _attr_name = "Wake screen"

    async def async_press(self) -> None:
        """Press the button to wake the screen."""
        self._device.send_custom_action(
            command="screen",
            payload={"action": "on"},
        )
