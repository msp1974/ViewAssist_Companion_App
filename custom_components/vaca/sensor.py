"""Sensor for Wyoming."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import RestoreSensor, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

UNKNOWN: str = "unknown"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.device is not None

    async_add_entities(
        [
            WyomingSatelliteSTTSensor(item.device),
            WyomingSatelliteTTSSensor(item.device),
            WyomingSatelliteLightSensor(item.device),
            WyomingSatelliteOrientationSensor(item.device),
        ]
    )


class WyomingSatelliteSTTSensor(VASatelliteEntity, RestoreSensor):
    """Entity to represent STT sensor for satellite."""

    entity_description = SensorEntityDescription(
        key="stt",
        translation_key="stt",
        icon="mdi:microphone-message",
    )
    _attr_native_value = UNKNOWN

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            self._value_changed(state.state)

        self._device.set_stt_listener(self._value_changed)

    @callback
    def _value_changed(self, value: str) -> None:
        """Call when value changed."""
        if value:
            if len(value) > 254:
                # Limit the length of the value to avoid issues with Home Assistant
                value = value[:252] + ".."
            self._attr_native_value = value
            self.async_write_ha_state()


class WyomingSatelliteTTSSensor(VASatelliteEntity, RestoreSensor):
    """Entity to represent TTS sensor for satellite."""

    entity_description = SensorEntityDescription(
        key="tts", translation_key="tts", icon="mdi:speaker-message"
    )
    _attr_native_value = UNKNOWN

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            self._value_changed(state.state)

        self._device.set_tts_listener(self._value_changed)

    @callback
    def _value_changed(self, value: str) -> None:
        """Call when value changed."""
        if value:
            if len(value) > 254:
                # Limit the length of the value to avoid issues with Home Assistant
                value = value[:252] + ".."
            self._attr_native_value = value
            self.async_write_ha_state()


class WyomingSatelliteLightSensor(VASatelliteEntity, RestoreSensor):
    """Entity to represent light sensor for satellite."""

    entity_description = SensorEntityDescription(
        key="light",
        translation_key="light_level",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
    )
    _attr_native_value = 0

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            self._attr_native_value = state.state
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_status_update",
                self.status_update,
            )
        )

    @callback
    def status_update(self, data: dict[str, Any]) -> None:
        """Update entity."""
        if sensors := data.get("sensors"):
            if self.entity_description.key in sensors:
                self._attr_native_value = int(sensors[self.entity_description.key])
                self.async_write_ha_state()


class WyomingSatelliteOrientationSensor(VASatelliteEntity, RestoreSensor):
    """Entity to represent orientation sensor for satellite."""

    entity_description = SensorEntityDescription(
        key="orientation",
        translation_key="orientation",
    )
    _attr_native_value = UNKNOWN

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            self._attr_native_value = state.state
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_status_update",
                self.status_update,
            )
        )

    @callback
    def status_update(self, data: dict[str, Any]) -> None:
        """Update entity."""
        if sensors := data.get("sensors"):
            if self.entity_description.key in sensors:
                self._attr_native_value = sensors[self.entity_description.key]
                self.async_write_ha_state()
