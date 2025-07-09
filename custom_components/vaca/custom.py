"""# Custom components for View Assist satellite integration with Wyoming events."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any

from wyoming.event import Event, Eventable

_LOGGER = logging.getLogger(__name__)

_CUSTOM_TYPE = "custom-settings"


@dataclass
class CustomSettings(Eventable):
    """Request pong message."""

    settings: dict[str, Any]
    """Text to copy to response."""

    @staticmethod
    def is_type(event_type: str) -> bool:
        """Check if the event type is a custom settings event."""
        return event_type == _CUSTOM_TYPE

    def event(self) -> Event:
        """Create an event for custom settings."""
        return Event(
            type=_CUSTOM_TYPE,
            data={"settings": self.settings},
        )

    @staticmethod
    def from_event(event: Event) -> "CustomSettings":
        """Create a CustomSettings instance from an event."""
        return CustomSettings(settings=event.data.get("settings"))


class MediaControlActions(StrEnum):
    """Actions for media control."""

    PLAY = "play"
    """Play media."""
    PAUSE = "pause"
    """Pause media."""
    STOP = "stop"
    """Stop media."""
    NEXT = "next"
    """Next media."""
    PREVIOUS = "previous"
    """Previous media."""
    VOLUME_UP = "volume_up"
    """Increase volume."""
    VOLUME_DOWN = "volume_down"
    """Decrease volume."""


@dataclass
class MediaPlayerControl(Eventable):
    """Media control event."""

    action: MediaControlActions
    """Action to perform on media."""

    value: str | float = None
    """Optional URL of the media to control."""

    @staticmethod
    def is_type(event_type: str) -> bool:
        """Check if the event type is a media control event."""
        return event_type == "media-control"

    def event(self) -> Event:
        """Create an event for media control."""
        return Event(
            type="media-control",
            data={"action": self.action, "value": self.value},
        )

    @staticmethod
    def from_event(event: Event) -> "MediaPlayerControl":
        """Create a MediaPlayerControl instance from an event."""
        return MediaPlayerControl(action=event.data.get("action"))
