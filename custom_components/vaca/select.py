"""Select entities for ViewAssist Companion App (VACA)."""

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

# Maps to the Android app's Speex processor denoise scale (0-100%)
_NOISE_SUPPRESSION_LEVEL: Final = {
    "off": 0,
    "low": 25,
    "medium": 50,
    "high": 75,
    "max": 100,
}

_LOGGER = logging.getLogger(__name__)

_SOUND_OPTIONS: Final = [
    "none",
    "alexa_wake_word",
    "havpe_wake_word",
    "generic_ding",
    "generic_bubble",
    "havpe_processing",
    "generic_error",
    "generic_stop_word",
    "havpe_mic_on",
    "havpe_mic_off",
]


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

    async_add_entities(
        [
            VACAPipelineSelect(hass, device),
            VACANoiseSuppressionLevelSelect(device),
            VACAEchoCancellationModeSelect(device),
            VACAVadSensitivitySelect(hass, device),
            VACAWakeWordEngineSelect(device),
            VACAWakeWordSelect(device),
            VACAWakeWordSoundSelect(device),
            VACAProcessingSoundSelect(device),
            VACAErrorSoundSelect(device),
            VACAStopWordSoundSelect(device),
            VACAMicOnSoundSelect(device),
            VACAMicOffSoundSelect(device),
            VACAMicAudioSourceSelect(device),
            VACAScreenTimeoutSelect(device),
            VACAScreenOrientationModeSelect(device),
        ]
    )


class BaseSelect(VASatelliteEntity, SelectEntity, restore_state.RestoreEntity):
    """Base class for VACA select entities where HA is the source of truth."""

    _attr_should_poll = False
    _attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            # Push restored state to device settings store immediately
            await self.set_select_option(state.state, send_to_device=True)
        elif self._attr_current_option is not None:
            # Populate settings store with default value
            await self.set_select_option(self._attr_current_option, send_to_device=True)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.set_select_option(option)

    async def set_select_option(self, option: str, send_to_device: bool = True) -> None:
        """Update selected option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        if send_to_device:
            self.send_to_device(option)

    def send_to_device(self, option: str) -> None:
        """Handover the setting to the device."""
        self._device.set_custom_setting(self.entity_description.key, option)


class BaseFeedbackSelect(BaseSelect):
    """Base class for selections where the device is the source of truth (lazy init)."""

    _listener_class = "settings_update"
    _attr_current_option = None # Wait for device feedback

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        # For feedback selects, we override the auto-push of restored state
        await super(BaseSelect, self).async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
             # Sync to state but DON'T push to device yet, wait for hardware status
             await self.set_select_option(state.state, send_to_device=False)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self.status_update,
            )
        )

    async def status_update(self, data: dict[str, Any]) -> None:
        """Handle status update."""
        update_key = self.entity_description.key
        if settings := data.get("settings"):
            if update_key in settings:
                setting_value = settings[update_key]
                # Map back from integer values if necessary in subclasses
                await self.process_feedback_value(setting_value)

    async def process_feedback_value(self, value: Any) -> None:
        """Process feedback from device."""
        await self.set_select_option(str(value), send_to_device=False)


class VACAPipelineSelect(VASatelliteEntity, AssistPipelineSelect):
    """Pipeline selector for VACA satellites."""

    def __init__(self, hass: HomeAssistant, device: VASatelliteDevice) -> None:
        """Initialize a pipeline selector."""
        self.device = device

        VASatelliteEntity.__init__(self, device)
        AssistPipelineSelect.__init__(self, hass, DOMAIN, device.satellite_id)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await super().async_select_option(option)
        self.device.set_pipeline_name(option)


class VACANoiseSuppressionLevelSelect(BaseSelect):
    """Entity to represent noise suppression level setting."""

    entity_description = SelectEntityDescription(
        key="noise_suppression_level",
        translation_key="noise_suppression_level",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = list(_NOISE_SUPPRESSION_LEVEL.keys())
    _attr_current_option = "off"

    def send_to_device(self, option: str) -> None:
        """Send setting to device."""
        self._device.set_custom_setting(self.entity_description.key, _NOISE_SUPPRESSION_LEVEL[option])


class VACAEchoCancellationModeSelect(BaseSelect):
    """Entity to select echo cancellation mode."""

    entity_description = SelectEntityDescription(
        key="echo_cancellation_mode",
        translation_key="echo_cancellation_mode",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = ["platform", "software"]
    _attr_current_option = "platform"

    def send_to_device(self, option: str) -> None:
        """Send setting to device."""
        self._device.set_custom_setting(self.entity_description.key, option)


class VACAVadSensitivitySelect(VASatelliteEntity, VadSensitivitySelect):
    """VAD sensitivity selector for VACA satellites."""

    def __init__(self, hass: HomeAssistant, device: VASatelliteDevice) -> None:
        """Initialize a VAD sensitivity selector."""
        self.device = device

        VASatelliteEntity.__init__(self, device)
        VadSensitivitySelect.__init__(self, hass, device.satellite_id)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await super().async_select_option(option)
        self.device.set_vad_sensitivity(VadSensitivity(option))


class VACAWakeWordSelect(BaseSelect):
    """Entity to represent wake word setting."""

    entity_description = SelectEntityDescription(
        key="wake_word",
        translation_key="wake_word",
        entity_category=EntityCategory.CONFIG,
    )

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

        # Listen for wake words data updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_wakewords_update",
                self._update_options,
            )
        )

    async def _update_options(self, _data: dict[str, Any]) -> None:
        """Update options state."""
        self.async_write_ha_state()

    def send_to_device(self, option: str) -> None:
        """Send setting to device."""
        self._device.set_custom_setting("wake_word", option.lower().replace(" ", "_"))


class VACAWakeWordSoundSelect(BaseSelect):
    """Entity to represent wake word sound setting."""

    entity_description = SelectEntityDescription(
        key="wake_word_sound",
        translation_key="wake_word_sound",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = _SOUND_OPTIONS
    _attr_current_option = "havpe_wake_word"


class VACAProcessingSoundSelect(BaseSelect):
    """Entity to represent processing sound setting."""

    entity_description = SelectEntityDescription(
        key="processing_sound",
        translation_key="processing_sound",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = _SOUND_OPTIONS
    _attr_current_option = "havpe_processing"


class VACAErrorSoundSelect(BaseSelect):
    """Entity to represent error sound setting."""

    entity_description = SelectEntityDescription(
        key="error_sound",
        translation_key="error_sound",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = _SOUND_OPTIONS
    _attr_current_option = "generic_error"


class VACAStopWordSoundSelect(BaseSelect):
    """Entity to represent stop word sound setting."""

    entity_description = SelectEntityDescription(
        key="stop_word_sound",
        translation_key="stop_word_sound",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = _SOUND_OPTIONS
    _attr_current_option = "generic_stop_word"


class VACAMicOnSoundSelect(BaseSelect):
    """Entity to represent mic on sound setting."""

    entity_description = SelectEntityDescription(
        key="mic_on_sound",
        translation_key="mic_on_sound",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = _SOUND_OPTIONS
    _attr_current_option = "havpe_mic_on"


class VACAMicOffSoundSelect(BaseSelect):
    """Entity to represent mic off sound setting."""

    entity_description = SelectEntityDescription(
        key="mic_off_sound",
        translation_key="mic_off_sound",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = _SOUND_OPTIONS
    _attr_current_option = "havpe_mic_off"


class VACAMicAudioSourceSelect(BaseSelect):
    """Entity to represent microphone capture source."""

    entity_description = SelectEntityDescription(
        key="mic_audio_source",
        translation_key="mic_audio_source",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = ["voice_recognition", "voice_communication"]
    _attr_current_option = "voice_recognition"

    def send_to_device(self, option: str) -> None:
        """Send setting to device."""
        self._device.set_custom_setting(self.entity_description.key, option)


class VACAScreenTimeoutSelect(BaseSelect):
    """Entity to represent screen timeout setting."""

    entity_description = SelectEntityDescription(
        key="screen_timeout",
        translation_key="screen_timeout",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = ["15", "30", "60", "120", "300", "600", "1800"]
    _attr_current_option = "60"

    def send_to_device(self, option: str) -> None:
        """Send setting to device."""
        self._device.set_custom_setting(self.entity_description.key, int(option))


class VACAWakeWordEngineSelect(BaseSelect):
    """Entity to represent wake word engine setting."""

    entity_description = SelectEntityDescription(
        key="wake_word_engine",
        translation_key="wake_word_engine",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = ["openwakeword", "microwakeword"]
    _attr_current_option = "openwakeword"

    def send_to_device(self, option: str) -> None:
        """Send setting to device."""
        self._device.wakeword_engine = option
        self._device.set_custom_setting("wake_word_engine", option)
        
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_{self._device.device_id}_wakewords_update",
            {"engine": option},
        )


class VACAScreenOrientationModeSelect(BaseSelect):
    """Entity to represent screen orientation mode setting."""

    entity_description = SelectEntityDescription(
        key="screen_orientation_mode",
        translation_key="screen_orientation_mode",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_options = [
        "auto",
        "portrait",
        "landscape",
        "reverse_portrait",
        "reverse_landscape",
    ]
    _attr_current_option = "auto"
