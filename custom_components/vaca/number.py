"""Number entities for ViewAssist Companion App (VACA)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final, Any

from homeassistant.components.number import NumberEntityDescription, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

_LOGGER = logging.getLogger(__name__)

# Constants for volume and gain limits
_MAX_MIC_GAIN: Final = 100
_MIN_SOUND_VOLUME: Final = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    device: VASatelliteDevice = item.device  # type: ignore[assignment]

    # Setup is only forwarded for satellites
    assert item.device is not None

    entities: list[VASatelliteEntity] = [
        VACAMicGainNumber(device),
        VACAVolumeNumber(
            device,
            NumberEntityDescription(
                key="media_volume",
                translation_key="media_volume",
                icon="mdi:music",
            ),
            "max_media_volume",
        ),
        VACAVolumeNumber(
            device,
            NumberEntityDescription(
                key="voice_volume",
                translation_key="voice_volume",
                icon="mdi:speaker-message",
            ),
            "max_voice_volume",
        ),
        VACAVolumeNumber(
            device,
            NumberEntityDescription(
                key="alarm_volume",
                translation_key="alarm_volume",
                icon="mdi:alarm",
            ),
            "max_alarm_volume",
        ),
        VACADuckingVolumeNumber(device),
        VACAScreenBrightnessNumber(device),
        VACAWakeWordThresholdNumber(device),
        VACAZoomLevelNumber(device),
    ]

    # Add optional sensors based on capabilities
    if device.capabilities:
        if device.capabilities.get("has_front_camera"):
            entities.append(VACAMotionDetectionSensitivityNumber(device))

        if device.capabilities.get("proximity_sensor_type") == "raw":
            entities.append(VACARawProximityThresholdNumber(device))

        if device.supportBump():
            entities.append(VACABumpDetectionSensitivityNumber(device))

    async_add_entities(entities)


class BaseNumberEntity(VASatelliteEntity, RestoreNumber):
    """Base class for number entities where HA is the source of truth."""

    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 100.0
    _attr_native_step: float = 1.0
    _attr_native_value: float | None = None

    def __init__(self, device: VASatelliteDevice) -> None:
        """Initialize number entity."""
        super().__init__(device)

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in ("unavailable", "unknown")
        ):
            try:
                val = float(state.state)
                # Store the value first, even if max is currently None
                self._attr_native_value = val

                # Push restored state to device settings store immediately if HA is master
                self.update_number(val, send_to_device=True)
            except (ValueError, TypeError):
                pass
        elif self._attr_native_value is not None:
            # Populate settings store with default value
            self.update_number(self._attr_native_value, send_to_device=True)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self.update_number(value)

    def update_number(self, value: float, send_to_device: bool = True) -> None:
        """Update number value."""
        if self._attr_native_max_value is None:
            # Store the value but don't clamp yet or send if max is unknown
            self._attr_native_value = value
            self.async_write_ha_state()
            return

        val = max(self._attr_native_min_value, min(self._attr_native_max_value, value))
        self._attr_native_value = float(val)
        self.async_write_ha_state()

        if send_to_device:
            self._device.set_custom_setting(self.entity_description.key, value)


class BaseFeedbackNumber(BaseNumberEntity):
    """Base class for numbers that receive feedback from device (Device is source of truth)."""

    _listener_class = "settings"

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        # For feedback numbers, we override the auto-push of restored state
        await super(BaseNumberEntity, self).async_added_to_hass()

        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in ("unavailable", "unknown")
        ):
            try:
                # Sync to state but DON'T push to device yet, wait for hardware status
                val = float(state.state)
                self._attr_native_value = val
                self.update_number(val, send_to_device=False)
            except (ValueError, TypeError):
                pass

        # Listen for settings updates (current values)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}_update",
                self.status_update,
            )
        )

        # Listen for capability updates (max ranges)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_capabilities_update",
                self.capabilities_update,
            )
        )

    def status_update(self, data: dict[str, Any]) -> None:
        """Handle status update."""
        if settings := data.get("settings"):
            if self.entity_description.key in settings:
                setting_value = settings[self.entity_description.key]
                self.update_number(float(setting_value), send_to_device=False)

    @callback
    def capabilities_update(self, data: dict[str, Any]) -> None:
        """Handle capabilities update."""
        self.update_native_max_value()
        # After max value is updated, re-apply current value to ensuring clamping and visibility
        if self._attr_native_value is not None:
            self.update_number(self._attr_native_value, send_to_device=False)
        self.async_write_ha_state()

    def update_native_max_value(self) -> None:
        """Update max value from device capabilities."""


class VACAVolumeNumber(BaseFeedbackNumber):
    """Generic volume entity for system audio streams."""

    _attr_native_max_value: float | None = None

    def __init__(
        self,
        device: VASatelliteDevice,
        description: NumberEntityDescription,
        capability_key: str,
    ) -> None:
        """Initialize."""
        self.entity_description = description
        super().__init__(device)
        self._capability_key = capability_key
        self._attr_native_min_value = float(_MIN_SOUND_VOLUME)
        self._attr_native_max_value = None
        self._attr_native_step = 1.0

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        self.update_native_max_value()
        await super().async_added_to_hass()

    def update_native_max_value(self) -> None:
        """Update max value from device capabilities."""
        max_vol = self._device.get_max_stream_volume(self._capability_key)
        self._attr_native_max_value = float(max_vol) if max_vol is not None else None


class VACAMicGainNumber(BaseNumberEntity):
    """Entity to represent mic gain amount."""

    entity_description = NumberEntityDescription(
        key="mic_gain",
        translation_key="mic_gain",
        icon="mdi:microphone-plus",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_native_min_value: float = -10.0
    _attr_native_max_value: float | None = 10.0
    _attr_native_value: float | None = 0.0


class VACADuckingVolumeNumber(BaseNumberEntity):
    """Entity to represent media volume multiplier."""

    entity_description = NumberEntityDescription(
        key="ducking_volume",
        translation_key="ducking_volume",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
    )
    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 100.0
    _attr_native_step: float = 1.0
    _attr_native_value: float | None = 70.0


class VACAScreenBrightnessNumber(BaseFeedbackNumber):
    """Entity to represent screen brightness amount."""

    entity_description = NumberEntityDescription(
        key="screen_brightness",
        translation_key="screen_brightness",
        icon="mdi:brightness-4",
        native_unit_of_measurement=PERCENTAGE,
    )
    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 100.0
    _attr_native_step: float = 1.0

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        # Check if we already have it in capabilities
        if self._device.capabilities and (
            brightness := self._device.capabilities.get("screen_brightness")
        ):
            self._attr_native_value = float(brightness)

        await super().async_added_to_hass()

    @callback
    def capabilities_update(self, data: dict[str, Any]) -> None:
        """Handle capabilities update."""
        if data and (brightness := data.get("screen_brightness")):
            self._attr_native_value = float(brightness)
        super().capabilities_update(data)


class VACAWakeWordThresholdNumber(BaseNumberEntity):
    """Entity to represent wake word trigger threshold."""

    entity_description = NumberEntityDescription(
        key="wake_word_threshold",
        translation_key="wake_word_threshold",
        icon="mdi:account-voice",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 10.0
    _attr_native_step: float = 1.0
    _attr_native_value: float | None = 6.0


class VACAZoomLevelNumber(BaseNumberEntity):
    """Entity to represent zoom level."""

    entity_description = NumberEntityDescription(
        key="zoom_level",
        translation_key="zoom_level",
        icon="mdi:magnify-plus",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 2.5
    _attr_native_step: float = 0.1
    _attr_native_value: float | None = 0.0

    def update_number(self, value: float, send_to_device: bool = True) -> None:
        """Update number value."""
        val = max(0.0, min(2.5, value))
        self._attr_native_value = float(val)
        self.async_write_ha_state()
        if send_to_device:
            # Zoom is sent as integer percentage/offset (specific to device handler)
            ZOOM_OFFSET = 60
            self._device.set_custom_setting(
                self.entity_description.key,
                int(val * 100) + ZOOM_OFFSET if val > 0 else 0,
            )


class VACAMotionDetectionSensitivityNumber(BaseNumberEntity):
    """Entity to represent motion detection sensitivity."""

    entity_description = NumberEntityDescription(
        key="motion_detection_sensitivity",
        translation_key="motion_detection_sensitivity",
        icon="mdi:tune-variant",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
    )
    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 100.0
    _attr_native_step: float = 1.0
    _attr_native_value: float | None = 70.0

    def update_number(self, value: float, send_to_device: bool = True) -> None:
        """Update number value."""
        # Sensitivity is sent as 0-50 scale to device (HA uses 0-100)
        self._attr_native_value = float(value)
        self.async_write_ha_state()
        if send_to_device:
            self._device.set_custom_setting(self.entity_description.key, int(value / 2))


class VACABumpDetectionSensitivityNumber(BaseNumberEntity):
    """Entity to represent bump sensitivity."""

    entity_description = NumberEntityDescription(
        key="bump_sensitivity",
        translation_key="bump_sensitivity",
        icon="mdi:tune-variant",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 10.0
    _attr_native_step: float = 1.0
    _attr_native_value: float | None = 8.0

    def update_number(self, value: float, send_to_device: bool = True) -> None:
        """Update number value."""
        val = max(0.0, min(10.0, value))
        self._attr_native_value = float(val)
        self.async_write_ha_state()
        if send_to_device:
            # Sensitivity is sent as 1-10 scale (inverted logic on some devices)
            self._device.set_custom_setting(self.entity_description.key, 11 - int(val))


class VACARawProximityThresholdNumber(BaseNumberEntity):
    """Entity to represent raw proximity threshold."""

    entity_description = NumberEntityDescription(
        key="raw_proximity_threshold",
        translation_key="raw_proximity_threshold",
        icon="mdi:radar",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_native_min_value: float = 0.0
    _attr_native_max_value: float | None = 1000.0
    _attr_native_step: float = 1.0
    _attr_native_value: float | None = 300.0
