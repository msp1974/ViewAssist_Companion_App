"""Wyoming switch entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import VACASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.device is not None

    async_add_entities(
        [
            WyomingSatelliteMuteSwitch(item.device),
            WyomingSatelliteSwipeToRefreshSwitch(item.device),
        ]
    )


class WyomingSatelliteMuteSwitch(
    VACASatelliteEntity, restore_state.RestoreEntity, SwitchEntity
):
    """Entity to represent if satellite is muted."""

    entity_description = SwitchEntityDescription(key="mute", translation_key="mute")

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()

        # Default to off
        self._attr_is_on = (state is not None) and (state.state == STATE_ON)
        self._device.set_custom_setting("is_muted", self._attr_is_on)

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:microphone-off" if self._attr_is_on else "mdi:microphone"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        self._attr_is_on = True
        self.async_write_ha_state()
        self._device.set_custom_setting("is_muted", self._attr_is_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        self._attr_is_on = False
        self.async_write_ha_state()
        self._device.set_custom_setting("is_muted", self._attr_is_on)


class WyomingSatelliteSwipeToRefreshSwitch(
    VACASatelliteEntity, restore_state.RestoreEntity, SwitchEntity
):
    """Entity to control swipe to refresh."""

    entity_description = SwitchEntityDescription(
        key="swipe_refresh",
        translation_key="swipe_refresh",
        icon="mdi:web-refresh",
        entity_category=EntityCategory.CONFIG,
    )

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()

        # Default to off
        self._attr_is_on = (state is not None) and (state.state == STATE_ON)
        self._device.set_custom_setting("swipe_refresh", self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        self._attr_is_on = True
        self.async_write_ha_state()
        self._device.set_custom_setting("swipe_refresh", self._attr_is_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        self._attr_is_on = False
        self.async_write_ha_state()
        self._device.set_custom_setting("swipe_refresh", self._attr_is_on)
