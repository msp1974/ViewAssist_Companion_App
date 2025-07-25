"""Select entities for Wyoming integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from homeassistant.components.assist_pipeline.select import (
    AssistPipelineSelect,
    VadSensitivitySelect,
)
from homeassistant.components.assist_pipeline.vad import VadSensitivity
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .devices import SatelliteDevice
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.device is not None

    async_add_entities(
        [
            WyomingSatellitePipelineSelect(hass, item.device),
            WyomingSatelliteNoiseSuppressionLevelSelect(item.device),
            WyomingSatelliteVadSensitivitySelect(hass, item.device),
            WyomingSatelliteWakeWordSelect(item.device),
            WyomingSatelliteWakeWordSoundSelect(item.device),
        ]
    )


class WyomingSatellitePipelineSelect(VASatelliteEntity, AssistPipelineSelect):
    """Pipeline selector for Wyoming satellites."""

    def __init__(self, hass: HomeAssistant, device: SatelliteDevice) -> None:
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

    def __init__(self, hass: HomeAssistant, device: SatelliteDevice) -> None:
        """Initialize a VAD sensitivity selector."""
        self.device = device

        VASatelliteEntity.__init__(self, device)
        VadSensitivitySelect.__init__(self, hass, device.satellite_id)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await super().async_select_option(option)
        self.device.set_vad_sensitivity(VadSensitivity(option))


class WyomingSatelliteWakeWordSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent wake word setting."""

    entity_description = SelectEntityDescription(
        key="wake_word",
        translation_key="wake_word",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_current_option = "hey_jarvis"

    @property
    def options(self) -> list[str]:
        """Return the list of available wake word options."""
        return self.get_wake_word_options()

    def get_wake_word_options(self) -> list[str]:
        """Return the list of available wake word options."""
        wake_options: list[dict[str, str]] = []
        if self._device.info:
            if self._device.info.wake:
                for wake_program in self._device.info.wake:
                    if wake_program.name == "available_wake_words":
                        wake_options = [
                            model.name.replace("_", " ").title()
                            for model in wake_program.models
                        ]
        return wake_options

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
        self._device.set_custom_setting("wake_word", option.lower().replace(" ", "_"))


class WyomingSatelliteWakeWordSoundSelect(
    VASatelliteEntity, SelectEntity, restore_state.RestoreEntity
):
    """Entity to represent wake word sound setting."""

    entity_description = SelectEntityDescription(
        key="wake_word_sound",
        translation_key="wake_word_sound",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_current_option = "havpe"
    _attr_options = ["none", "alexa", "havpe", "ding", "bubble"]

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
        self._device.set_custom_setting("wake_word_sound", option)
