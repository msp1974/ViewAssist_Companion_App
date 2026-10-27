"""Camera entity for VA Wyoming."""

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
        entities.append(WyomingStreamCamera(device))

    if entities:
        async_add_entities(entities)


class WyomingStreamCamera(VASatelliteEntity, Camera):
    """Represents a camera stream from the satellite."""

    entity_description = CameraEntityDescription(
        key="camera",
        translation_key="camera",
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
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_status_update",
                self.status_update,
            )
        )

    async def capabilities_update(self, data: dict[str, Any]) -> None:
        """Handle capabilities updates from the device."""
        # WebRTC provider (go2rtc) is only selected if it supports the stream
        # source, so re-evaluate in case it has changed.
        await self.async_refresh_providers()

    async def status_update(self, data: dict[str, Any]) -> None:
        """Handle status updates from the device."""
        if "rtsp_url" in data:
            await self.async_refresh_providers()
            self.async_write_ha_state()

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if rtsp_url := self._device.rtsp_url:
            return rtsp_url
        if capabilities := self._device.capabilities:
            return capabilities.get("rtsp_url") or None
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the stream."""
        # Use go2rtc for snapshot if it is providing the stream
        if (provider := self.webrtc_provider) and (
            image := await provider.async_get_image(self, width=width, height=height)
        ) is not None:
            return image

        if source := await self.stream_source():
            return await async_get_image(self.hass, source, width=width, height=height)

        return None
