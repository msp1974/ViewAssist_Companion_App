"""Select entities for Wyoming integration."""

import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.assist_pipeline import (
    AssistPipelineSelect,
    VadSensitivity,
    VadSensitivitySelect,
)
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, EntityCategory
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
_NO_MUSIC_ASSISTANT: Final = "None"

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
        WyomingSatelliteMusicAssistantServerSelect(device),
        WyomingSatelliteAudioInputSelect(device),
        WyomingSatelliteAudioOutputSelect(device),
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


class WyomingRestoreSelectEntityBase(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Base class for Wyoming satellite select entities that restore state."""

    _attr_should_poll = False
    _attr_current_option = None
    _attr_default_option = None
    _attr_options = []

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        attributes = state.attributes if state else {}
        # Restore available options
        self._attr_options = attributes.get("options", [])

        if state is not None and state.state in self.options:
            await self.async_select_option(state.state)
        elif (
            self._attr_default_option is not None
            and self._attr_default_option in self.options
        ):
            await self.async_select_option(self._attr_default_option)
        elif self.options:
            await self.async_select_option(self.options[0])

        # Register device listener for this select entity
        if hasattr(self, "_attr_device_listeners"):
            for key in self._attr_device_listeners:
                self._register_device_listener(key)

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        if hasattr(self, "_attr_options_fn"):
            options_fn = getattr(self, self._attr_options_fn, None)
            if callable(options_fn):
                return options_fn()
        elif hasattr(self, "_attr_options"):
            return self._attr_options
        elif (
            hasattr(self, "entity_description")
            and self.entity_description.options is not None
        ):
            return self.entity_description.options
        return []

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
        self._device.set_custom_setting(
            self.entity_description.key, self._option_value_convert(option)
        )

    def _option_value_convert(self, option: str) -> str:
        """Convert the option value to the format expected by the device."""
        return option

    async def _update_options_list(self, _data: dict[str, Any]) -> None:
        """Method to trigger state update."""
        self.async_write_ha_state()

    def _register_device_listener(self, key: str):
        async_dispatcher_connect(
            self.hass,
            f"{DOMAIN}_{self._device.device_id}_{key}",
            self._update_options_list,
        )


class WyomingSatelliteMotionDetectionModeSelect(WyomingRestoreSelectEntityBase):
    """Entity to represent motion detection mode setting."""

    entity_description = SelectEntityDescription(
        key="motion_detection_mode",
        translation_key="motion_detection_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:motion-sensor",
    )
    _attr_options = ["none", "motion", "face"]


class WyomingSatelliteWakeWordSelect(WyomingRestoreSelectEntityBase):
    """Entity to represent wake word setting."""

    entity_description = SelectEntityDescription(
        key="wake_word",
        translation_key="wake_word",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:account-voice",
    )
    _attr_options = ["hey_jarvis"]
    _attr_options_fn = "get_wake_word_options"
    _attr_device_listeners = ["info_update", "wakewords_update"]

    def get_wake_word_options(self) -> list[str]:
        """Return the list of available wake word options."""
        wake_options: list[str] = ["None"]
        if self._device.info and self._device.info.wake:
            for wake_program in self._device.info.wake:
                if wake_program.name == "available_wake_words":
                    wake_options.extend(
                        [
                            model.name.replace("_", " ").title()
                            for model in wake_program.models
                            if model.attribution.name
                            in [self._device.wakeword_engine, ""]
                        ]
                    )
        return wake_options

    def _option_value_convert(self, option: str) -> str:
        """Convert the option value to the format expected by the device."""
        return option.lower().replace(" ", "_")


class WyomingSatelliteWakeWordSoundSelect(WyomingRestoreSelectEntityBase):
    """Entity to represent wake word sound setting."""

    entity_description = SelectEntityDescription(
        key="wake_word_sound",
        translation_key="wake_word_sound",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:bell-circle-outline",
    )
    _attr_options = ["None"]
    _attr_device_listeners = ["capabilities_update"]

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

    def _option_value_convert(self, option: str) -> str:
        """Convert the option value to the format expected by the device."""
        return option.lower().replace(" ", "_")


class WyomingSatelliteScreenTimeoutSelect(WyomingRestoreSelectEntityBase):
    """Entity to represent screen timeout setting."""

    entity_description = SelectEntityDescription(
        key="screen_timeout",
        translation_key="screen_timeout",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:timer-sand",
    )
    _attr_default_option = "60"
    _attr_options = ["15", "30", "60", "120", "300", "600", "1800"]

    def _option_value_convert(self, option: str) -> str:
        """Convert the option value to the format expected by the device."""
        return int(option)


class WyomingSatelliteAlarmSoundSelect(WyomingRestoreSelectEntityBase):
    """Entity to represent alarm sound setting."""

    entity_description = SelectEntityDescription(
        key="alarm_sound",
        translation_key="alarm_sound",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:alarm",
    )
    _attr_options = ["Default"]
    _attr_options_fn = "get_alarm_sound_options"
    _attr_device_listeners = ["capabilities_update"]

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

    def _option_value_convert(self, option: str) -> str:
        """Convert the option value to the format expected by the device."""
        return option.lower().replace(" ", "_")


class WyomingSatelliteWakeWordEngineSelect(WyomingRestoreSelectEntityBase):
    """Entity to represent wake word engine setting."""

    entity_description = SelectEntityDescription(
        key="wake_word_engine",
        translation_key="wake_word_engine",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:microphone-settings",
    )
    _attr_options = ["openwakeword", "openwakeword_rt", "microwakeword"]

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._device.wakeword_engine = option
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_{self._device.device_id}_wakewords_update",
            {"engine": option},
        )
        await super().async_select_option(option)


class WyomingSatelliteMusicAssistantServerSelect(WyomingRestoreSelectEntityBase):
    """Entity to select the Music Assistant server."""

    entity_description = SelectEntityDescription(
        key="sendspin_preferred_server",
        translation_key="sendspin_preferred_server",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:music-box-multiple",
    )
    _attr_options = ["Auto"]

    def _get_servers(self) -> dict[str, str]:
        """Return available Music Assistant servers as name -> url."""
        return {
            entry.title: entry.data.get(CONF_URL, "")
            for entry in self.hass.config_entries.async_entries("music_assistant")
        }

    @property
    def options(self) -> list[str]:
        """Return the list of available Music Assistant servers."""
        return ["Auto", *self._get_servers()]

    def _option_value_convert(self, option: str) -> str:
        """Convert the selected server name to its url."""
        return self._get_servers().get(option, "")


class _WyomingSatelliteAudioDeviceSelect(WyomingRestoreSelectEntityBase):
    """Base for audio device selects populated from hardware capabilities."""

    _attr_options = []
    _attr_device_listeners = ["capabilities_update"]
    _capabilities_key = ""

    def _get_devices(self) -> dict[str, Any]:
        """Return available audio devices as name -> id."""
        audio = (self._device.capabilities or {}).get("audio") or {}
        devices: dict[str, Any] = {}
        for item in audio.get(self._capabilities_key) or []:
            if isinstance(item, dict):
                name = item.get("type_name")
                device_id = item.get("id", name)
            else:
                name = device_id = item
            if name and str(name) not in devices:
                devices[str(name)] = device_id
        return devices

    @property
    def options(self) -> list[str]:
        """Return the audio devices reported by the satellite."""
        return list(self._get_devices())

    def _option_value_convert(self, option: str) -> Any:
        """Convert the selected name to the device id expected by the satellite."""
        return self._get_devices().get(option, option)


class WyomingSatelliteAudioInputSelect(_WyomingSatelliteAudioDeviceSelect):
    """Entity to select the audio input."""

    entity_description = SelectEntityDescription(
        key="audio_input",
        translation_key="audio_input",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:microphone",
    )
    _capabilities_key = "inputs"


class WyomingSatelliteAudioOutputSelect(_WyomingSatelliteAudioDeviceSelect):
    """Entity to select the audio output."""

    entity_description = SelectEntityDescription(
        key="audio_output",
        translation_key="audio_output",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:speaker",
    )
    _capabilities_key = "outputs"


class WyomingSatelliteScreenOrientationModeSelect(WyomingRestoreSelectEntityBase):
    """Entity to represent screen orientation mode setting."""

    entity_description = SelectEntityDescription(
        key="screen_orientation_mode",
        translation_key="screen_orientation_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:screen-rotation",
    )
    _attr_options = [
        "auto",
        "portrait",
        "landscape",
        "reverse_portrait",
        "reverse_landscape",
    ]
