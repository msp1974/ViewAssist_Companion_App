"""Number entities for Wyoming integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Any

from homeassistant.components.number import NumberEntityDescription, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

_MAX_MIC_GAIN: Final = 100
_MIN_SOUND_VOLUME: Final = 0
_MAX_SOUND_VOLUME: Final = 10


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

    entities = []

    entities.extend(
        [
            WyomingSatelliteMicGainNumber(device),
            WyomingSatelliteNotificationVolumeNumber(device),
            WyomingSatelliteMusicVolumeNumber(device),
            WyomingSatelliteAlarmVolumeNumber(device),
            WyomingSatelliteDuckingVolumeNumber(device),
            WyomingSatelliteScreenBrightnessNumber(device),
            WyomingSatelliteWakeWordThresholdNumber(device),
            WyomingSatelliteZoomLevelNumber(device),
        ]
    )

    if device.capabilities and device.capabilities.get("has_front_camera"):
        entities.append(WyomingSatelliteMotionDetectionSensitivityNumber(device))
    if (
        device.capabilities
        and device.capabilities.get("proximity_sensor_type") == "raw"
    ):
        entities.append(WyomingSatelliteRawProximityThresholdNumber(device))
    if device.supportBump():
        entities.append(WyomingSatelliteBumpDetectionSensitivityNumber(device))
    async_add_entities(entities)


class BaseNumberEntity(VASatelliteEntity, RestoreNumber):
    """Base class for number entities."""

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            await self.async_set_native_value(float(state.state))

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.update_number(value)

    async def update_number(self, value: float, send_to_device: bool = True) -> None:
        """Update number value."""
        self._attr_native_value = int(
            max(self._attr_native_min_value, min(self._attr_native_max_value, value))
        )
        self.async_write_ha_state()

        if send_to_device:
            self._device.set_custom_setting(self.entity_description.key, value)


class BaseFeedbackNumber(BaseNumberEntity):
    """Base class for numbers that receive feedback from device."""

    _listener_class = "settings_update"

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self.status_update,
            )
        )

    async def status_update(self, data: dict[str, Any]) -> None:
        """Handle status update."""
        if settings := data.get("settings"):
            if self.entity_description.key in settings:
                setting_value = settings[self.entity_description.key]
                await self.update_number(setting_value, send_to_device=False)


class WyomingSatelliteMicGainNumber(BaseNumberEntity):
    """Entity to represent mic gain amount."""

    entity_description = NumberEntityDescription(
        key="mic_gain",
        translation_key="mic_gain",
        icon="mdi:microphone-plus",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = -10
    _attr_native_max_value = 10
    _attr_native_value = 0

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        mic_gain = int(max(-10, min(10, int(value))))
        self._attr_native_value = mic_gain
        self.async_write_ha_state()
        self._device.set_custom_setting(self.entity_description.key, mic_gain)


class WyomingSatelliteNotificationVolumeNumber(BaseFeedbackNumber):
    """Entity to represent notification volume multiplier."""

    entity_description = NumberEntityDescription(
        key="notification_volume",
        translation_key="notification_volume",
        icon="mdi:speaker-message",
    )
    _attr_should_poll = False
    _attr_native_min_value = _MIN_SOUND_VOLUME
    _attr_native_max_value = _MAX_SOUND_VOLUME
    _attr_native_step = 1
    _attr_native_value = 5

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._attr_native_max_value = self._device.getMaxNotificationVolume()
        last_number_data = await self.async_get_last_number_data()
        if last_number_data and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_max_value = self._device.getMaxNotificationVolume()
        await super().async_set_native_value(
            int(max(_MIN_SOUND_VOLUME, min(self._attr_native_max_value, int(value))))
        )


class WyomingSatelliteMusicVolumeNumber(BaseFeedbackNumber):
    """Entity to represent media volume multiplier."""

    entity_description = NumberEntityDescription(
        key="music_volume",
        translation_key="music_volume",
        icon="mdi:music",
    )
    _attr_should_poll = False
    _attr_native_min_value = _MIN_SOUND_VOLUME
    _attr_native_max_value = _MAX_SOUND_VOLUME
    _attr_native_step = 1
    _attr_native_value = 5

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._attr_native_max_value = self._device.getMaxMusicVolume()
        last_number_data = await self.async_get_last_number_data()
        if last_number_data is not None and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_max_value = self._device.getMaxMusicVolume()
        await super().async_set_native_value(
            int(max(_MIN_SOUND_VOLUME, min(self._attr_native_max_value, int(value))))
        )


class WyomingSatelliteAlarmVolumeNumber(BaseFeedbackNumber):
    """Entity to represent alarm volume multiplier."""

    entity_description = NumberEntityDescription(
        key="alarm_volume",
        translation_key="alarm_volume",
        icon="mdi:alarm",
    )
    _attr_should_poll = False
    _attr_native_min_value = _MIN_SOUND_VOLUME
    _attr_native_max_value = _MAX_SOUND_VOLUME
    _attr_native_step = 1
    _attr_native_value = 5

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._attr_native_max_value = self._device.getMaxAlarmVolume()
        last_number_data = await self.async_get_last_number_data()
        if last_number_data is not None and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_max_value = self._device.getMaxAlarmVolume()
        await super().async_set_native_value(
            int(max(_MIN_SOUND_VOLUME, min(self._attr_native_max_value, int(value))))
        )


class WyomingSatelliteDuckingVolumeNumber(BaseNumberEntity):
    """Entity to represent media volume multiplier."""

    entity_description = NumberEntityDescription(
        key="ducking_volume",
        translation_key="ducking_volume",
        icon="mdi:percent",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_value = 70

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        last_number_data = await self.async_get_last_number_data()
        if last_number_data is not None and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = int(
            max(self._attr_native_min_value, min(self._attr_native_max_value, value))
        )
        self.async_write_ha_state()
        self._device.set_custom_setting(self.entity_description.key, int(value))


class WyomingSatelliteScreenBrightnessNumber(BaseFeedbackNumber):
    """Entity to represent screen brightness amount."""

    entity_description = NumberEntityDescription(
        key="screen_brightness",
        translation_key="screen_brightness",
        icon="mdi:brightness-4",
    )
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_value = 50

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        last_number_data = await self.async_get_last_number_data()
        if last_number_data is not None and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)


class WyomingSatelliteWakeWordThresholdNumber(VASatelliteEntity, RestoreNumber):
    """Entity to represent wake word trigger threshold."""

    entity_description = NumberEntityDescription(
        key="wake_word_threshold",
        translation_key="wake_word_threshold",
        icon="mdi:account-voice",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_value = 6

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            await self.async_set_native_value(float(state.state))

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(max(0, min(10, value)))
        self._attr_native_value = value
        self.async_write_ha_state()
        self._device.set_custom_setting(self.entity_description.key, value)


class WyomingSatelliteZoomLevelNumber(VASatelliteEntity, RestoreNumber):
    """Entity to represent zoom level."""

    entity_description = NumberEntityDescription(
        key="zoom_level",
        translation_key="zoom_level",
        icon="mdi:magnify-plus",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 2.5
    _attr_native_step = 0.1
    _attr_native_value = 0

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            await self.async_set_native_value(float(state.state))

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(max(0, min(self._attr_native_max_value, int(value))))
        self._attr_native_value = value
        self.async_write_ha_state()
        self._device.set_custom_setting(
            self.entity_description.key, int(value * 100) + 60 if value > 0 else 0
        )


class WyomingSatelliteMotionDetectionSensitivityNumber(
    VASatelliteEntity, RestoreNumber
):
    """Entity to represent zoom level."""

    entity_description = NumberEntityDescription(
        key="motion_detection_sensitivity",
        translation_key="motion_detection_sensitivity",
        icon="mdi:tune-variant",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_value = 70

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            await self.async_set_native_value(float(state.state))

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(max(0, min(self._attr_native_max_value, int(value))))
        self._attr_native_value = value
        self.async_write_ha_state()
        # Sensitivity is sent as 0-50 scale
        self._device.set_custom_setting(self.entity_description.key, int(value / 2))


class WyomingSatelliteBumpDetectionSensitivityNumber(VASatelliteEntity, RestoreNumber):
    """Entity to represent bump sensitivity."""

    entity_description = NumberEntityDescription(
        key="bump_sensitivity",
        translation_key="bump_sensitivity",
        icon="mdi:tune-variant",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_native_value = 8

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            await self.async_set_native_value(float(state.state))

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(max(0, min(self._attr_native_max_value, int(value))))
        self._attr_native_value = value
        self.async_write_ha_state()
        # Sensitivity is sent as 1-10 scale
        self._device.set_custom_setting(self.entity_description.key, 11 - value)


class WyomingSatelliteRawProximityThresholdNumber(VASatelliteEntity, RestoreNumber):
    """Entity to represent raw proximity threshold."""

    entity_description = NumberEntityDescription(
        key="raw_proximity_threshold",
        translation_key="raw_proximity_threshold",
        icon="mdi:radar",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 1000
    _attr_native_value = 300

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            await self.async_set_native_value(float(state.state))

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(max(0, min(self._attr_native_max_value, int(value))))
        self._attr_native_value = value
        self.async_write_ha_state()
        self._device.set_custom_setting(self.entity_description.key, value)
