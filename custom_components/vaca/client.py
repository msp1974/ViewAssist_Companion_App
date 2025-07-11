"""Custom AsyncTCPClient for Wyoming events."""

from wyoming.client import AsyncTcpClient
from wyoming.event import Event


class VAAsyncTcpClient(AsyncTcpClient):
    """Custom TCP client for Wyoming events."""

    def __init__(
        self,
        host: str,
        port: int,
        before_send_callback=None,
        after_send_callback=None,
        on_receive_callback=None,
    ) -> None:
        """Initialize the custom TCP client."""
        super().__init__(host, port)
        self._before_send_callback = before_send_callback
        self._after_send_callback = after_send_callback
        self._on_receive_callback = on_receive_callback

    async def write_event(self, event: Event) -> None:
        """Write an event to the server."""
        if self._before_send_callback:
            await self._before_send_callback(event)
        if self.can_write_event():
            await super().write_event(event)
        if self._after_send_callback:
            await self._after_send_callback(event)

    async def read_event(self) -> Event:
        """Read an event from the server."""
        event = await super().read_event()
        if self._on_receive_callback:
            await self._on_receive_callback(event)
        return event

    def can_write_event(self) -> bool:
        """Check if the client can write an event."""
        return self._writer is not None and not self._writer.is_closing()
