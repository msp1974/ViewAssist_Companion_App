"""Class to manage satellite devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wyoming.info import Info

from homeassistant.components.wyoming import SatelliteDevice
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


@dataclass
class VASatelliteDevice(SatelliteDevice):
    """VACA Class to store device."""

    info: Info | None = None
    custom_settings: dict[str, Any] | None = None
    capabilities: dict[str, Any] | None = None

    _custom_settings_listener: Callable[[], None] | None = None
    _custom_action_listener: Callable[[Any, Any], None] | None = None
    _info_listener: Callable[[], None] | None = None
    stt_listener: Callable[[str], None] | None = None
    tts_listener: Callable[[str], None] | None = None

    def get_pipeline_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for pipeline select."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{self.satellite_id}-pipeline"
        )

    def get_noise_suppression_level_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for noise suppression select."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{self.satellite_id}-noise_suppression_level"
        )

    def get_vad_sensitivity_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for VAD sensitivity."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{self.satellite_id}-vad_sensitivity"
        )

    @callback
    def set_custom_setting(self, setting: str, value: str | float) -> None:
        """Set custom setting."""
        if self.custom_settings is None:
            self.custom_settings = {}

        if setting not in self.custom_settings:
            self.custom_settings[setting] = value
        elif self.custom_settings[setting] == value:
            return
        else:
            self.custom_settings[setting] = value

        if self._custom_settings_listener is not None:
            self._custom_settings_listener()

    @callback
    def send_custom_action(
        self, command: str, payload: dict[str, Any] | None = None
    ) -> None:
        """Send a media player command."""
        if self._custom_action_listener is not None:
            self._custom_action_listener(command, payload)

    @callback
    def set_custom_settings_listener(
        self, custom_settings_listener: Callable[[], None]
    ) -> None:
        """Listen for updates to custom settings."""
        self._custom_settings_listener = custom_settings_listener

    @callback
    def set_custom_action_listener(
        self, custom_action_listener: Callable[[Any, Any], None]
    ) -> None:
        """Listen for stt updates."""
        self._custom_action_listener = custom_action_listener

    @callback
    def set_info_listener(self, info_listener: Callable[[], None]) -> None:
        """Listen for info updates."""
        self._info_listener = info_listener

    @callback
    def set_stt_listener(self, stt_listener: Callable[[str], None]) -> None:
        """Listen for stt updates."""
        self.stt_listener = stt_listener

    @callback
    def set_tts_listener(self, tts_listener: Callable[[str], None]) -> None:
        """Listen for stt updates."""
        self.tts_listener = tts_listener

    def has_light_sensor(self) -> bool:
        """Check if the device has a light sensor."""
        if self.capabilities and (sensors := self.capabilities.get("sensors")):
            for sensor in sensors:
                if sensor.get("type") == 5:  # Light sensor type
                    return True
        return False

    def supportBump(self) -> bool:
        """Check if the device supports bump proximity feature."""
        if self.capabilities and (sensors := self.capabilities.get("sensors")):
            for sensor in sensors:
                if sensor.get("type") == 1:  # Accelerometer type
                    return True
        return False

    def supportProximity(self) -> bool:
        """Check if the device supports bump proximity feature."""
        if self.capabilities and (sensors := self.capabilities.get("sensors")):
            for sensor in sensors:
                if sensor.get("type") == 8:  # Proximity type
                    return True
        return False
