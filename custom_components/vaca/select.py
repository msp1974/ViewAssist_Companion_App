"""Select entities for Wyoming integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.assist_pipeline import (
    AssistPipelineSelect,
    VadSensitivity,
    VadSensitivitySelect,
)
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

_NOISE_SUPPRESSION_LEVEL: Final = {
    "off": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "max": 4,
}
_DEFAULT_NOISE_SUPPRESSION_LEVEL: Final = "off"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    device: VASatelliteDevice = item.device  # type: ignore[assignment]

    # Setup is only forwarded for satellites
    assert item.device is not None

    entities = [
        WyomingSatellitePipelineSelect(hass, device),
        WyomingSatelliteNoiseSuppressionLevelSelect(device),
        WyomingSatelliteVadSensitivitySelect(hass, device),
        WyomingSatelliteWakeWordEngineSelect(device),
        WyomingSatelliteWakeWordSelect(device),
        WyomingSatelliteWakeWordSoundSelect(device),
        WyomingSatelliteAlarmSoundSelect(device),
        WyomingSatelliteScreenTimeoutSelect(device),
        WyomingSatelliteScreenOrientationModeSelect(device),
    ]

    if device.capabilities and device.capabilities.get("has_front_camera"):
        entities.append(WyomingSatelliteMotionDetectionModeSelect(device))

    if entities:
        async_add_entities(entities)


class WyomingSatellitePipelineSelect(VASatelliteEntity, AssistPipelineSelect):
    """Pipeline selector for Wyoming satellites."""

    def __init__(self, hass: HomeAssistant, device: VASatelliteDevice) -> None:
        """Initialize a pipeline selector."""
        self.device = device

        VASatelliteEntity.__init__(self, device)
        AssistPipelineSelect.__init__(self, hass, DOMAIN, device.satellite_id)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await super().async_select_option(option)
        self.device.set_pipeline_name(option)


class WyomingSatelliteNoiseSuppressionLevelSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent noise suppression level setting."""

    entity_description = SelectEntityDescription(
        key="noise_suppression_level",
        translation_key="noise_suppression_level",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_current_option = _DEFAULT_NOISE_SUPPRESSION_LEVEL
    _attr_options = list(_NOISE_SUPPRESSION_LEVEL.keys())

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            self._attr_current_option = state.state

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_noise_suppression_level(_NOISE_SUPPRESSION_LEVEL[option])


class WyomingSatelliteVadSensitivitySelect(VASatelliteEntity, VadSensitivitySelect):
    """VAD sensitivity selector for Wyoming satellites."""

    def __init__(self, hass: HomeAssistant, device: VASatelliteDevice) -> None:
        """Initialize a VAD sensitivity selector."""
        self.device = device

        VASatelliteEntity.__init__(self, device)
        VadSensitivitySelect.__init__(self, hass, device.satellite_id)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await super().async_select_option(option)
        self.device.set_vad_sensitivity(VadSensitivity(option))


class WyomingSatelliteMotionDetectionModeSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent motion detection mode setting."""

    entity_description = SelectEntityDescription(
        key="motion_detection_mode",
        translation_key="motion_detection_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:motion-sensor",
    )
    _attr_should_poll = False
    _attr_current_option = "none"
    _attr_options = ["none", "motion", "face"]

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_custom_setting(self.entity_description.key, option)


class WyomingSatelliteWakeWordSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent wake word setting."""

    entity_description = SelectEntityDescription(
        key="wake_word",
        translation_key="wake_word",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:account-voice",
    )
    _attr_should_poll = False
    _attr_current_option = "hey_jarvis"

    @property
    def options(self) -> list[str]:
        """Return the list of available wake word options."""
        options = ["None"]
        options.extend(self.get_wake_word_options())
        return options

    def get_wake_word_options(self) -> list[str]:
        """Return the list of available wake word options."""
        wake_options: list[str] = []
        if self._device.info and self._device.info.wake:
            for wake_program in self._device.info.wake:
                if wake_program.name == "available_wake_words":
                    wake_options = [
                        model.name.replace("_", " ").title()
                        for model in wake_program.models
                        if model.attribution.name in [self._device.wakeword_engine, ""]
                    ]
        return wake_options

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)
        # Default to the first available option if no state is found
        elif self.options:
            await self.async_select_option(self.options[0])

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_info_update",
                self.update_options_list,
            )
        )
        # Add listener for chaging wake word engine selector
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_wakewords_update",
                self.update_options_list,
            )
        )

    async def update_options_list(self, _data: dict[str, Any]) -> None:
        """Method to trigger state update."""
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_custom_setting("wake_word", option.lower().replace(" ", "_"))


class WyomingSatelliteWakeWordSoundSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent wake word sound setting."""

    entity_description = SelectEntityDescription(
        key="wake_word_sound",
        translation_key="wake_word_sound",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:bell-circle-outline",
    )
    _attr_should_poll = False
    _attr_current_option = "None"

    @property
    def options(self) -> list[str]:
        """Return the list of available wake word sound options."""
        options = ["None"]
        options.extend(self.get_wake_word_sound_options())
        return options

    def get_wake_word_sound_options(self) -> list[str]:
        """Return the list of available wake word sound options."""
        wake_sound_options: list[str] = []
        if self._device.capabilities and self._device.capabilities.get("wake_sounds"):
            wake_sound_options = [
                wake_sound.get("name", "Unknown")
                for wake_sound in self._device.capabilities["wake_sounds"]
            ]
        return wake_sound_options

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_capabilities_update",
                self.update_options_list,
            )
        )

    async def update_options_list(self, _data: dict[str, Any]) -> None:
        """Method to trigger state update."""
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_custom_setting(
            "wake_word_sound", option.lower().replace(" ", "_")
        )


class WyomingSatelliteScreenTimeoutSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent screen timeout setting."""

    entity_description = SelectEntityDescription(
        key="screen_timeout",
        translation_key="screen_timeout",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:timer-sand",
    )
    _attr_should_poll = False
    _attr_current_option = "60"
    _attr_options = ["15", "30", "60", "120", "300", "600", "1800"]

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_custom_setting(self.entity_description.key, int(option))


class WyomingSatelliteAlarmSoundSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent alarm sound setting."""

    entity_description = SelectEntityDescription(
        key="alarm_sound",
        translation_key="alarm_sound",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:alarm",
    )
    _attr_should_poll = False
    _attr_current_option = "Default"

    @property
    def options(self) -> list[str]:
        """Return the list of available alarm sound options."""
        options = []
        options.extend(self.get_alarm_sound_options())
        return options

    def get_alarm_sound_options(self) -> list[str]:
        """Return the list of available alarm sound options."""
        alarm_sound_options: list[str] = []
        if self._device.capabilities and self._device.capabilities.get("alarms"):
            alarm_sound_options = [
                alarm_sound.get("name", "Unknown")
                for alarm_sound in self._device.capabilities["alarms"]
            ]
        return alarm_sound_options

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_capabilities_update",
                self.update_options_list,
            )
        )

    async def update_options_list(self, _data: dict[str, Any]) -> None:
        """Method to trigger state update."""
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_custom_setting("alarm_sound", option.lower().replace(" ", "_"))


class WyomingSatelliteWakeWordEngineSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent wake word engine setting."""

    entity_description = SelectEntityDescription(
        key="wake_word_engine",
        translation_key="wake_word_engine",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:microphone-settings",
    )
    _attr_should_poll = False
    _attr_current_option = "openwakeword"
    _attr_options = ["openwakeword", "openwakeword_rt", "microwakeword"]

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)
        else:
            await self.async_select_option(self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self._device.wakeword_engine = option

        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_{self._device.device_id}_wakewords_update",
            {"engine": option},
        )

        self.async_write_ha_state()
        self._device.set_custom_setting("wake_word_engine", option)


class WyomingSatelliteScreenOrientationModeSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent screen orientation mode setting."""

    entity_description = SelectEntityDescription(
        key="screen_orientation_mode",
        translation_key="screen_orientation_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:screen-rotation",
    )
    _attr_should_poll = False
    _attr_current_option = "auto"
    _attr_options = [
        "auto",
        "portrait",
        "landscape",
        "reverse_portrait",
        "reverse_landscape",
    ]

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_custom_setting("screen_orientation_mode", option)
