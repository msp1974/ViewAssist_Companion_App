"""Event sensor for Wyoming"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.event import (
    EventEntity,
    EventEntityDescription,
    EventDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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

    entities = [
        WyomingGestureEvent(device),
    ]
    if device.has_proximity_sensor():
        entities.append(WyomingProximityEvent(device))

    if entities:
        async_add_entities(entities)


class WyomingGestureEvent(VASatelliteEntity, EventEntity):
    """Gesture event for Wyoming satellites."""

    _listener_class = "gesture_update"
    entity_description = EventEntityDescription(
        key="gesture",
        translation_key="gesture",
        icon="mdi:gesture-swipe",
    )
    _touch_points = [1, 2, 3]
    _gestures = [
        "left",
        "right",
        "up",
        "down",
        "up_right",
        "up_left",
        "down_right",
        "down_left",
        "left_up",
        "right_up",
        "left_down",
        "right_down",
    ]

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self._async_handle_event,
            )
        )

    @property
    def event_types(self) -> list[str]:
        """Return a list of possible events."""
        event_types = []
        for gesture in self._gestures:
            event_types.extend(
                f"{gesture}_{touch_point}" for touch_point in self._touch_points
            )
        return event_types

    @callback
    def _async_handle_event(self, data: dict[str, Any]) -> None:
        """Handle the gesture event."""
        gesture = data.get("gesture")
        touch_points = data.get("touch_points")
        _LOGGER.debug(
            "Received gesture event: %s with %s touch points", gesture, touch_points
        )
        self._trigger_event(
            f"{gesture}_{touch_points}",
            {
                "gesture": gesture,
                "touch_points": touch_points,
                "startX": data.get("startX"),
                "startY": data.get("startY"),
            },
        )
        self.async_write_ha_state()


class WyomingProximityEvent(VASatelliteEntity, EventEntity):
    """Proximity event for Wyoming satellites."""

    _listener_class = "proximity_update"
    entity_description = EventEntityDescription(
        key="proximity",
        translation_key="proximity",
        icon="mdi:gesture-swipe",
    )

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self._async_handle_event,
            )
        )

    @property
    def event_types(self) -> list[str]:
        """Return a list of possible events."""
        return ["proximity_near", "proximity_far"]

    @callback
    def _async_handle_event(self, data: dict[str, Any]) -> None:
        """Handle the proximity event."""
        is_near = data.get("near")
        _LOGGER.debug("Received proximity event: %s", is_near)
        self._trigger_event(
            f"proximity_{'near' if is_near else 'far'}",
            {
                "proximity": data.get("proximity"),
            },
        )
        self.async_write_ha_state()
