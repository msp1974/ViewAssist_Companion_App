"""Media player entity for ViewAssist Companion App (VACA)."""

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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .custom import CustomActions
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
    """Set up media_player entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    device: VASatelliteDevice = item.device  # type: ignore[assignment]

    # Setup is only forwarded for satellites
    assert item.device is not None

    async_add_entities([VACAMediaPlayer(device)])


class VACAMediaPlayer(VASatelliteEntity, MediaPlayerEntity, RestoreEntity):
    """Represents a VACA media player."""

    entity_description = MediaPlayerEntityDescription(
        key="media_player",
        translation_key="media_player",
        device_class=MediaPlayerDeviceClass.SPEAKER,
        name="Media player",
    )

    _attr_state = MediaPlayerState.IDLE
    _attr_volume_level: float | None = None  # Lazy init
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

        # Restore last volume state if available
        if (state := await self.async_get_last_state()) and state.attributes.get(
            "volume_level"
        ) is not None:
            try:
                self._attr_volume_level = float(state.attributes["volume_level"])
                # Seed the device settings store so it's pushed on connection
                self._device.set_custom_setting("media_player_gain", int(self._attr_volume_level * 100))
            except (ValueError, TypeError):
                self._attr_volume_level = 0.9

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_settings_update",
                self.status_update,
            )
        )

    async def status_update(self, data: dict[str, Any]) -> None:
        """Handle status update."""
        if settings := data.get("settings"):
            if "media_player_gain" in settings:
                self._attr_volume_level = float(settings["media_player_gain"]) / 100.0
                self.async_write_ha_state()

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ):
        """Play a piece of media."""
        _LOGGER.debug(
            "Playing media: type=%s, id=%s, announce=%s",
            media_type,
            media_id,
            announce,
        )

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        payload: dict[str, Any] = {"url": media_id}
        if self._attr_volume_level is not None:
            payload["volume"] = self._attr_volume_level * 100

        self._device.send_custom_action(
            command=CustomActions.MEDIA_PLAY_MEDIA,
            payload=payload,
        )
        self._attr_state = MediaPlayerState.PLAYING

        meta_data = {}
        if "extra" in kwargs:
            extra = kwargs["extra"]
            meta_data = extra.get("metadata", {})

        await self.async_process_metadata(metadata=meta_data)
        self.async_write_ha_state()

    async def async_media_play(self):
        """Send a play command."""
        payload: dict[str, Any] = {}
        if self._attr_volume_level is not None:
            payload["volume"] = self._attr_volume_level * 100

        self._device.send_custom_action(
            command=CustomActions.MEDIA_PLAY,
            payload=payload,
        )
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self):
        """Send a pause command."""
        self._device.send_custom_action(
            command=CustomActions.MEDIA_PAUSE,
        )
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self):
        """Send a stop command."""
        self._device.send_custom_action(
            command=CustomActions.MEDIA_STOP,
        )
        self._attr_state = MediaPlayerState.IDLE
        await self.async_process_metadata({})
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        self._device.send_custom_action(
            command=CustomActions.MEDIA_SET_VOLUME,
            payload={"volume": volume * 100},
        )
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Increase the volume level."""
        if self._attr_volume_level is None:
            return
        return await self.async_set_volume_level(
            min(1.0, self._attr_volume_level + 0.1)
        )

    async def async_volume_down(self):
        """Decrease the volume level."""
        if self._attr_volume_level is None:
            return
        return await self.async_set_volume_level(
            max(0.0, self._attr_volume_level - 0.1)
        )

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
        self._attr_media_title = metadata.get("title")
        self._attr_media_artist = metadata.get("artist")
        self._attr_media_album_name = metadata.get("albumName")
        self._attr_entity_picture = metadata.get("imageURL")
        self.async_write_ha_state()
