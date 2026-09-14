"""Sensor for Wyoming."""

from __future__ import annotations

from functools import reduce
import logging
from typing import TYPE_CHECKING, Any
from datetime import timedelta

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import now, parse_datetime

from .const import DOMAIN
from .devices import VASatelliteDevice
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
    device: VASatelliteDevice = item.device  # type: ignore[assignment]

    # Setup is only forwarded for satellites
    assert item.device is not None

    entities = [
        WyomingSatelliteSTTSensor(device),
        WyomingSatelliteTTSSensor(device),
        WyomingSatelliteIntentSensor(device),
        WyomingSatelliteOrientationSensor(device),
        WyomingSatelliteBrowserPathSensor(device),
    ]

    if capabilities := device.capabilities:
        if capabilities.get("app_version"):
            entities.append(WyomingSatelliteAppVersionSensor(device))
        if capabilities.get("has_battery"):
            entities.append(WyomingSatelliteBatteryLevelSensor(device))
        if device.has_light_sensor():
            entities.append(WyomingSatelliteLightSensor(device))
        if device.supports_motion_detection():
            entities.append(WyomingSatelliteLastMotionSensor(device))

    async_add_entities(entities)


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


class WyomingSatelliteIntentSensor(VASatelliteEntity, RestoreSensor):
    """Entity to represent intent sensor for satellite."""

    entity_description = SensorEntityDescription(
        key="intent", translation_key="intent", icon="mdi:message-bulleted"
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
                f"{DOMAIN}_{self._device.device_id}_intent_output",
                self.status_update,
            )
        )

    @callback
    def status_update(self, data: dict[str, Any]) -> None:
        """Update entity."""
        if data and data.get("intent_output"):
            value = str(
                self.get_key("intent_output.response.speech.plain.speech", data)
            )
            if value:
                if len(value) > 254:
                    # Limit the length of the value to avoid issues with Home Assistant
                    value = value[:252] + ".."
                self._attr_native_value = value

            self._attr_extra_state_attributes = data
            self.async_write_ha_state()

    def get_key(
        self, dot_notation_path: str, data: dict
    ) -> dict[str, dict | str | int] | str | int | None:
        """Try to get a deep value from a dict based on a dot-notation."""

        try:
            if "." in dot_notation_path:
                dn_list = dot_notation_path.split(".")
            else:
                dn_list = [dot_notation_path]
            return reduce(dict.get, dn_list, data)  # type: ignore[return-value]
        except (TypeError, KeyError):
            return None


class _WyomingSatelliteDeviceSensorBase(VASatelliteEntity, RestoreSensor):
    """Base class for device sensors."""

    _attr_native_value = 0
    _listener_class = "status_update"

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = self._get_timestamp_from_string(state.state)
            else:
                self._attr_native_value = state.state
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self.status_update,
            )
        )

    def _get_native_value(self, value: Any) -> Any:
        """Get the native value from the data."""
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            if value.isdigit():
                return int(value)
            return value
        return value

    def _get_timestamp_from_string(self, timestamp_str: str) -> Any:
        """Convert timestamp string to datetime object."""
        if timestamp_str.startswith("1970-01-01"):
            return now() - timedelta(days=14)  # Default to a long time ago
        if parsed_time := parse_datetime(timestamp_str):
            if parsed_time > now(parsed_time.tzinfo):
                return now(parsed_time.tzinfo)
            return parsed_time
        return None

    @callback
    def status_update(self, data: dict[str, Any]) -> None:
        """Update entity."""
        if self._listener_class == "status_update":
            if sensors := data.get("sensors"):
                if self.entity_description.key in sensors:
                    if (
                        self.entity_description.device_class
                        == SensorDeviceClass.TIMESTAMP
                    ):
                        # Handle timestamp conversion
                        timestamp_str = sensors[self.entity_description.key]
                        self._attr_native_value = self._get_timestamp_from_string(
                            timestamp_str
                        )
                    else:
                        self._attr_native_value = self._get_native_value(
                            sensors[self.entity_description.key]
                        )
                    self.async_write_ha_state()
        elif self._listener_class == "capabilities_update":
            if self._device.capabilities and self._device.capabilities.get(
                self.entity_description.key
            ):
                self._attr_native_value = self._get_native_value(
                    self._device.capabilities[self.entity_description.key]
                )
                self.async_write_ha_state()


class WyomingSatelliteLightSensor(_WyomingSatelliteDeviceSensorBase):
    """Entity to represent light sensor for satellite."""

    entity_description = SensorEntityDescription(
        key="light",
        translation_key="light_level",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        suggested_display_precision=0,
    )


class WyomingSatelliteOrientationSensor(_WyomingSatelliteDeviceSensorBase):
    """Entity to represent orientation sensor for satellite."""

    _attr_native_value = UNKNOWN
    entity_description = SensorEntityDescription(
        key="orientation", translation_key="orientation", icon="mdi:screen-rotation"
    )


class WyomingSatelliteBatteryLevelSensor(_WyomingSatelliteDeviceSensorBase):
    """Entity to represent battery level sensor for satellite."""

    entity_description = SensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    )


class WyomingSatelliteBrowserPathSensor(_WyomingSatelliteDeviceSensorBase):
    """Entity to represent browser path sensor for satellite."""

    _attr_native_value = UNKNOWN
    entity_description = SensorEntityDescription(
        key="current_path", translation_key="current_path", icon="mdi:web"
    )


class WyomingSatelliteLastMotionSensor(_WyomingSatelliteDeviceSensorBase):
    """Entity to represent last motion for satellite."""

    _attr_native_value = now() - timedelta(days=14)  # Default to a long time ago
    entity_description = SensorEntityDescription(
        key="last_motion",
        translation_key="last_motion",
        icon="mdi:motion-sensor",
        device_class=SensorDeviceClass.TIMESTAMP,
    )


class WyomingSatelliteAppVersionSensor(_WyomingSatelliteDeviceSensorBase):
    """Entity to represent app version sensor for satellite."""

    _listener_class = "capabilities_update"
    _attr_native_value = UNKNOWN
    entity_description = SensorEntityDescription(
        key="app_version",
        translation_key="app_version",
        icon="mdi:application",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def _get_native_value(self, value: Any) -> Any:
        """Get the native value from the data."""
        return value if value is not None else UNKNOWN

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        return {
            "device_signature": self.get_capability("device_signature"),
            "android_version": self.get_capability("release"),
            "webview_version": self.get_capability("webview_version"),
            "has_battery": self.get_capability("has_battery"),
            "has_front_camera": self.get_capability("has_front_camera"),
            "has_light_sensor": self._device.has_light_sensor(),
            "sensors": self.get_sensor_names(),
            "audio": self.get_capability("audio"),
        }

    def get_capability(self, capability: str) -> Any:
        """Get a specific capability from the device."""
        if self._device.capabilities is None:
            return UNKNOWN
        return self._device.capabilities.get(capability, UNKNOWN)

    def get_sensor_names(self) -> list[str] | None:
        """Get the names of all sensors."""
        if self._device.capabilities and (
            sensors := self._device.capabilities.get("sensors")
        ):
            return [sensor.get("name") for sensor in sensors]
        return None
