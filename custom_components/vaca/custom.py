"""# Custom components for View Assist satellite integration with Wyoming events."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from wyoming.client import AsyncTcpClient
from wyoming.event import Event, Eventable

_CUSTOM_TYPE = "custom-settings"


class VAAsyncTcpClient(AsyncTcpClient):
    """Custom TCP client for Wyoming events."""

    def __init__(
        self, host: str, port: int, before_callback=None, after_callback=None
    ) -> None:
        """Initialize the custom TCP client."""
        super().__init__(host, port)
        self._before_callback = before_callback
        self._after_callback = after_callback

    async def write_event(self, event: Event) -> None:
        """Write an event to the server."""
        if self._before_callback:
            await self._before_callback(event)
        await super().write_event(event)
        if self._after_callback:
            await self._after_callback(event)


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
