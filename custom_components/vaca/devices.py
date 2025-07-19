"""Class to manage satellite devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.wyoming import SatelliteDevice
from homeassistant.components.wyoming.data import Info
from homeassistant.core import callback


@dataclass
class VASatelliteDevice(SatelliteDevice):
    """VACA Class to store device."""

    info: Info | None = None
    custom_settings: dict[str, Any] | None = None

    _custom_settings_listener: Callable[[], None] | None = None
    _custom_action_listener: Callable[[], None] | None = None
    stt_listener: Callable[[str], None] | None = None
    tts_listener: Callable[[str], None] | None = None

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
        self, custom_action_listener: Callable[[], None]
    ) -> None:
        """Listen for stt updates."""
        self._custom_action_listener = custom_action_listener

    @callback
    def set_stt_listener(self, stt_listener: Callable[[str], None]) -> None:
        """Listen for stt updates."""
        self.stt_listener = stt_listener

    @callback
    def set_tts_listener(self, tts_listener: Callable[[str], None]) -> None:
        """Listen for stt updates."""
        self.tts_listener = tts_listener
