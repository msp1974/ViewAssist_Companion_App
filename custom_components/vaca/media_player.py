"""Media player entity for VA Wyoming."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .custom import CustomActions
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media_player entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.device is not None

    async_add_entities([WyomingMediaPlayer(item.device)])


class WyomingMediaPlayer(VASatelliteEntity, MediaPlayerEntity):
    """Represents a hassmic media player."""

    entity_description = MediaPlayerEntityDescription(
        key="media_player",
        translation_key="media_player",
        device_class=MediaPlayerDeviceClass.SPEAKER,
        name="Media player",
    )

    _attr_state = MediaPlayerState.IDLE
    _attr_volume_level = 0.9
    _attr_supported_features = (
        MediaPlayerEntityFeature(0)
        | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        # | MediaPlayerEntityFeature.MEDIA_ENQUEUE
        # | MediaPlayerEntityFeature.NEXT_TRACK
    )

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ):
        """Play a piece of media."""
        _LOGGER.info(
            "Playing media: type=%s, id=%s, enq=%s, announce=%s, args=%s",
            media_type,
            media_id,
            enqueue,
            announce,
            kwargs,
        )

        # resolve a media_source_id into a URL
        # https://developers.home-assistant.io/docs/core/entity/media-player/#play-media

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        _LOGGER.info("Playing media: '%s'", media_id)
        self._device.send_custom_action(
            command=CustomActions.MEDIA_PLAY_MEDIA,
            payload={"url": media_id, "volume": self._attr_volume_level * 100},
        )
        self._attr_state = MediaPlayerState.PLAYING

        # Handle metadata if available
        meta_data = {}
        if "extra" in kwargs:
            extra = kwargs["extra"]
            meta_data = extra.get("metadata", {})

        await self.async_process_metadata(metadata=meta_data)

        self.async_write_ha_state()

    async def async_media_play(self):
        """Send a play command."""
        _LOGGER.info("Playing")
        self._device.send_custom_action(
            command=CustomActions.MEDIA_PLAY,
            payload={"volume": self._attr_volume_level * 100},
        )
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self):
        """Send a pause command."""
        _LOGGER.info("Pausing playback")
        self._device.send_custom_action(
            command=CustomActions.MEDIA_PAUSE,
        )
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self):
        """Send a stop command."""
        _LOGGER.info("Stopping playback")
        self._device.send_custom_action(
            command=CustomActions.MEDIA_STOP,
        )
        self._attr_state = MediaPlayerState.IDLE
        await self.async_process_metadata({})
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        _LOGGER.info("Setting playback volume to %f", volume)
        self._device.send_custom_action(
            command=CustomActions.MEDIA_SET_VOLUME,
            payload={"volume": volume * 100},
        )
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Increase the volume level."""
        return await self.async_set_volume_level(self._attr_volume_level + 0.1)

    async def async_volume_down(self):
        """Decrease the volume level."""
        return await self.async_set_volume_level(self._attr_volume_level - 0.1)

    # https://developers.home-assistant.io/docs/core/entity/media-player/#browse-media
    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_process_metadata(self, metadata: dict[str, Any]) -> None:
        """Process metadata from the media player."""
        _LOGGER.info("Processing metadata: %s", metadata)
        self._attr_media_title = metadata.get("title")
        self._attr_media_artist = metadata.get("artist")
        self._attr_media_album_name = metadata.get("albumName")
        self._attr_entity_picture = metadata.get("imageURL")
        self.async_write_ha_state()
