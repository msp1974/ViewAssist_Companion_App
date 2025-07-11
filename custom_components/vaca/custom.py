"""# Custom components for View Assist satellite integration with Wyoming events."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any

from wyoming.event import Event, Eventable

_LOGGER = logging.getLogger(__name__)

_CUSTOM_SETTINGS_TYPE = "custom-settings"
_CUSTOM_ACTION_TYPE = "custom-action"


@dataclass
class CustomSettings(Eventable):
    """Custom settings event."""

    settings: dict[str, Any]
    """Text to copy to response."""

    @staticmethod
    def is_type(event_type: str) -> bool:
        """Check if the event type is a custom settings event."""
        return event_type == _CUSTOM_SETTINGS_TYPE

    def event(self) -> Event:
        """Create an event for custom settings."""
        return Event(
            type=_CUSTOM_SETTINGS_TYPE,
            data={"settings": self.settings},
        )

    @staticmethod
    def from_event(event: Event) -> "CustomSettings":
        """Create a CustomSettings instance from an event."""
        return CustomSettings(settings=event.data.get("settings"))


class CustomActions(StrEnum):
    """Actions for media control."""

    GET_DEVICE_INFO = "get-device-info"
    TOAST_MESSAGE = "toast-message"
    MEDIA_PLAY_MEDIA = "play-media"
    MEDIA_PLAY = "play"
    MEDIA_PAUSE = "pause"
    MEDIA_STOP = "stop"
    MEDIA_SET_VOLUME = "set-volume"


@dataclass
class CustomAction(Eventable):
    """Custom action event."""

    action: CustomActions
    """Action to perform."""

    payload: dict[str, Any] | None = None
    """Optional payload for the action."""

    @staticmethod
    def is_type(event_type: str) -> bool:
        """Check if the event type is a custom action event."""
        return event_type == _CUSTOM_ACTION_TYPE

    def event(self) -> Event:
        """Create an event for custom action."""
        return Event(
            type=_CUSTOM_ACTION_TYPE,
            data={"action": self.action, "payload": self.payload},
        )

    @staticmethod
    def from_event(event: Event) -> "CustomAction":
        """Create a CustomAction instance from an event."""
        return CustomAction(
            action=event.data.get("action"), payload=event.data.get("payload")
        )
