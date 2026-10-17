"""Camera entity for VA Wyoming."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.components.ffmpeg import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up camera entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    device: VASatelliteDevice = item.device  # type: ignore[assignment]

    # Setup is only forwarded for satellites
    assert item.device is not None

    entities = []

    if device.capabilities and device.capabilities.get("has_rtsp"):
        entities.append(WyomingRTSPCamera(device))

    if entities:
        async_add_entities(entities)


class WyomingRTSPCamera(VASatelliteEntity, Camera):
    """Represents an RTSP camera stream from the satellite."""

    entity_description = CameraEntityDescription(
        key="rtsp_camera",
        translation_key="rtsp_camera",
    )

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, device: VASatelliteDevice) -> None:
        """Initialize camera."""
        VASatelliteEntity.__init__(self, device)
        Camera.__init__(self)

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_capabilities_update",
                self.capabilities_update,
            )
        )

    async def capabilities_update(self, data: dict[str, Any]) -> None:
        """Handle capabilities updates from the device."""
        rtsp_url = await self.stream_source()

        # Restart any running stream on the new source
        if self.stream and rtsp_url and self.stream.source != rtsp_url:
            self.stream.update_source(rtsp_url)

        # WebRTC provider (go2rtc) is only selected if it supports the stream
        # source, so re-evaluate in case it has changed.
        await self.async_refresh_providers()

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if not self._device.capabilities:
            return None
        return self._device.capabilities.get("rtsp_url")

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the stream."""
        # Use go2rtc for snapshot if it is providing the stream
        if (provider := self.webrtc_provider) and (
            image := await provider.async_get_image(self, width=width, height=height)
        ) is not None:
            return image

        if not (rtsp_url := await self.stream_source()):
            return None
        return await async_get_image(self.hass, rtsp_url, width=width, height=height)
