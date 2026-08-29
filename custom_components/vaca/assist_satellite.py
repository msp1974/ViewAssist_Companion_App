"""Assist satellite entity for Wyoming integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.handle import Handled
from wyoming.info import Describe, Info
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import RunSatellite

from homeassistant.components import assist_pipeline, ffmpeg, intent
from homeassistant.components.assist_pipeline import PipelineEvent
from homeassistant.components.assist_satellite import (
    AssistSatelliteAnnouncement,
    AssistSatelliteEntityDescription,
    AssistSatelliteEntityFeature,
)
from homeassistant.components.wyoming import DomainDataItem, WyomingService

# pylint: disable-next=hass-component-root-import
from homeassistant.components.wyoming.assist_satellite import WyomingAssistSatellite
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import VAAsyncTcpClient
from .const import DOMAIN, MIN_APK_VERSION, SAMPLE_CHANNELS, SAMPLE_WIDTH
from .custom import (
    ACTION_EVENT_TYPE,
    SETTINGS_EVENT_TYPE,
    STATUS_EVENT_TYPE,
    Capabilities,
    CustomEvent,
    PipelineEnded,
    get_custom_files_data,
    getIntegrationVersion,
    getVADashboardPath,
)
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

_LOGGER = logging.getLogger(__name__)

_RECONNECT_SECONDS: Final = 10
_RESTART_SECONDS: Final = 3
_TTS_SAMPLE_RATE: Final = 22050
_ANNOUNCE_CHUNK_BYTES: Final = 2048  # 1024 samples


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wyoming Assist satellite entity."""
    domain_data: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    assert domain_data.device is not None

    device: VASatelliteDevice = domain_data.device  # type: ignore[assignment]

    async_add_entities(
        [ViewAssistSatelliteEntity(hass, domain_data.service, device, config_entry)]
    )


class ViewAssistSatelliteEntity(WyomingAssistSatellite, VASatelliteEntity):
    """View Assist satellite entity for Wyoming devices."""

    entity_description = AssistSatelliteEntityDescription(
        key="assist_satellite", translation_key="assist_satellite"
    )

    _attr_name = None
    _attr_supported_features = (
        AssistSatelliteEntityFeature.ANNOUNCE
        | AssistSatelliteEntityFeature.START_CONVERSATION
    )

    def __init__(
        self,
        hass: HomeAssistant,
        service: WyomingService,
        device: VASatelliteDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a View Assist satellite."""
        WyomingAssistSatellite.__init__(self, hass, service, device, config_entry)
        VASatelliteEntity.__init__(self, device)
        self._client: VAAsyncTcpClient | None = None
        self.device: VASatelliteDevice = device

        self.device.set_custom_settings_listener(self._custom_settings_changed)
        self.device.set_custom_action_listener(self._send_custom_action)

        # Make info accessible from entities
        self.device.info = service.info

        # Init custom settings
        self.device.custom_settings = {}

        # stream tts var to allow interupt and cancel remaining response
        self.stream_tts = False

    async def on_restart(self) -> None:
        """Block until pipeline loop will be restarted."""
        _LOGGER.warning(
            "Satellite %s has been disconnected. Reconnecting in %s second(s)",
            self.entity_id.replace("assist_satellite.", ""),
            _RECONNECT_SECONDS,
        )
        await asyncio.sleep(_RESTART_SECONDS)

    async def on_reconnect(self) -> None:
        """Block until a reconnection attempt should be made."""
        _LOGGER.debug(
            "Failed to connect to %s satellite. Reconnecting in %s second(s)",
            self.entity_id.replace("assist_satellite.", ""),
            _RECONNECT_SECONDS,
        )
        await asyncio.sleep(_RECONNECT_SECONDS)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        try:
            await super().async_will_remove_from_hass()
        except AssertionError as ex:
            _LOGGER.debug("Assertion error while stopping satellite: %s", ex)

    async def on_before_send_event_callback(self, event: Event) -> None:
        """Allow injection of events before event sent."""

    async def on_after_send_event_callback(self, event: Event) -> None:
        """Allow injection of events after event sent."""
        if Describe().is_type(event.type) and self._client:
            await self._client.write_event(Capabilities().event())

        elif RunSatellite().is_type(event.type):
            # integration version
            if self.device and self.device.custom_settings:
                self.device.custom_settings[
                    "integration_version"
                ] = await getIntegrationVersion(self.hass)
                self.device.custom_settings["min_required_apk_version"] = (
                    MIN_APK_VERSION
                )
                # Update url and port
                self.device.custom_settings["ha_port"] = (
                    self.hass.config.api.port if self.hass.config.api else 8123
                )
                self.device.custom_settings["ha_url"] = (
                    self.hass.config.internal_url or ""
                )
                home = getVADashboardPath(self.hass, self.device.satellite_id)
                self.device.custom_settings["ha_dashboard"] = home.removeprefix("/")

                # Add custom files data - commented out awaiting implementation
                self.device.custom_settings[
                    "custom_files"
                ] = await self.hass.async_add_executor_job(
                    get_custom_files_data, self.hass
                )

            # Send config event
            self._custom_settings_changed()

    async def on_handle_settings_request(self) -> None:
        """Handle settings request from satellite."""
        _LOGGER.debug(
            "Satellite %s requested settings update",
            self.entity_id.replace("assist_satellite.", ""),
        )
        # Add custom files data - commented out awaiting implementation
        self.device.custom_settings[
            "custom_files"
        ] = await self.hass.async_add_executor_job(get_custom_files_data, self.hass)
        # Send config event
        self._custom_settings_changed()

    @callback
    def on_receive_event_callback(self, event: Event) -> tuple[bool, Event | None]:
        """Handle received custom events."""
        if event and AudioStop.is_type(event.type):
            self.stream_tts = False
            return not self.stream_tts, event

        if event and Capabilities.is_type(event.type):
            self.device.capabilities = event.data
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.device.device_id}_capabilities_update",
                event.data or {},
            )
            return False, None

        if event and Info.is_type(event.type):
            self.device.info = Info.from_event(event)
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.device.device_id}_info_update",
                event.data or {},
            )
            return False, None

        if event and CustomEvent.is_type(event.type):
            # Custom event
            evt = CustomEvent.from_event(event)

            if evt.event_type in (STATUS_EVENT_TYPE, SETTINGS_EVENT_TYPE):
                _LOGGER.debug(
                    "Received %s event from %s: %s",
                    evt.event_type,
                    self.device.info.satellite.name,
                    evt.event_data,
                )
                if evt.event_type == SETTINGS_EVENT_TYPE and not evt.event_data:
                    # Handle settings request from satellite
                    self.hass.async_create_task(self.on_handle_settings_request())

            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.device.device_id}_{evt.event_type}_update",
                evt.event_data or {},
            )
            return False, None

        return True, event

    async def _connect(self) -> None:
        """Connect to satellite over TCP.  Uses custom TCP client to allow callbacks on send."""
        await self._disconnect()

        _LOGGER.debug(
            "Connecting VACA to satellite at %s:%s",
            self.service.host,
            self.service.port,
        )
        self._client = VAAsyncTcpClient(
            self.service.host,
            self.service.port,
            before_send_callback=self.on_before_send_event_callback,
            after_send_callback=self.on_after_send_event_callback,
            on_receive_callback=self.on_receive_event_callback,
        )
        await self._client.connect()

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle pipeline events from the assist pipeline.

        To allow additional functionality, this method is overridden to handle
        specific events such as STT and TTS updates. This is necessary to ensure
        that the satellite can respond to these events appropriately, such as
        updating listeners for speech-to-text and text-to-speech outputs.
        MSP - Added by MSP1974 2025-07-08
        """
        if event.type == assist_pipeline.PipelineEventType.RUN_START:
            if event.data and (tts_output := event.data.get("tts_output")):
                # Get stream token early.
                # If "tts_start_streaming" is True in INTENT_PROGRESS event, we
                # can start streaming TTS before the TTS_END event.
                self._tts_stream_token = tts_output["token"]
                self._is_tts_streaming = False
            return
        if event.type == assist_pipeline.PipelineEventType.RUN_END:
            # Pipeline ended
            if self._client is not None:
                self.config_entry.async_create_background_task(
                    self.hass,
                    self._client.write_event(PipelineEnded().event()),
                    "send pipeline ended event",
                )
        elif event.type == assist_pipeline.PipelineEventType.STT_END:
            # Speech-to-text transcript
            if event.data:
                # Inform client of transript
                stt_text = event.data["stt_output"]["text"]

                if self.device.stt_listener is not None:
                    self.device.stt_listener(stt_text)
        elif event.type == assist_pipeline.PipelineEventType.TTS_START:
            # Text-to-speech text
            if event.data:
                if self.device.tts_listener is not None:
                    self.device.tts_listener(event.data["tts_input"])
        elif event.type == assist_pipeline.PipelineEventType.INTENT_END:
            # Intent processing complete - update intent sensor
            # Remove speech slots as can contain datetime which will not transform to json
            event_data = event.data.copy() if event.data else {}
            if (
                event_data.get("intent_output", {})
                .get("response", {})
                .get("speech_slots")
            ):
                event_data["intent_output"]["response"].pop("speech_slots")

            if event_data:
                _LOGGER.debug("Intent %s complete: %s", event.type, event_data)
                # Update client with intent output structure
                self.config_entry.async_create_background_task(
                    self.hass,
                    self._client.write_event(
                        Handled(text=event.type, context=event_data).event(),
                    ),
                    f"{self.entity_id} {event.type}",
                )

                if (
                    event.data.get("intent_output", {})
                    .get("response", {})
                    .get("speech")
                ):
                    async_dispatcher_send(
                        self.hass,
                        f"{DOMAIN}_{self.device.device_id}_intent_output",
                        event.data,
                    )

        super().on_pipeline_event(event)

    async def async_announce(self, announcement: AssistSatelliteAnnouncement) -> None:
        """Announce media on the satellite.

        Should block until the announcement is done playing.
        MSP - Fixes that Wyoming announce does not play preannounce sound
        """
        assert self._client is not None

        if self._ffmpeg_manager is None:
            self._ffmpeg_manager = ffmpeg.get_ffmpeg_manager(self.hass)

        if self._played_event_received is None:
            self._played_event_received = asyncio.Event()

        self._played_event_received.clear()
        await self._client.write_event(
            AudioStart(
                rate=_TTS_SAMPLE_RATE,
                width=SAMPLE_WIDTH,
                channels=SAMPLE_CHANNELS,
                timestamp=0,
            ).event()
        )

        timestamp = 0

        # Play preannounce sound if set
        if announcement.preannounce_media_id:
            preannounce_proc = await asyncio.create_subprocess_exec(
                self._ffmpeg_manager.binary,
                "-i",
                announcement.preannounce_media_id,
                "-f",
                "s16le",
                "-ac",
                str(SAMPLE_CHANNELS),
                "-ar",
                str(_TTS_SAMPLE_RATE),
                "-nostats",
                "pipe:",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                close_fds=False,  # use posix_spawn in CPython < 3.13
            )
            assert preannounce_proc.stdout is not None
            while True:
                chunk_bytes = await preannounce_proc.stdout.read(_ANNOUNCE_CHUNK_BYTES)
                if not chunk_bytes:
                    break

                chunk = AudioChunk(
                    rate=_TTS_SAMPLE_RATE,
                    width=SAMPLE_WIDTH,
                    channels=SAMPLE_CHANNELS,
                    audio=chunk_bytes,
                    timestamp=timestamp,
                )
                await self._client.write_event(chunk.event())

                timestamp += chunk.milliseconds

        try:
            # Use ffmpeg to convert to raw PCM audio with the appropriate format
            proc = await asyncio.create_subprocess_exec(
                self._ffmpeg_manager.binary,
                "-i",
                announcement.media_id,
                "-f",
                "s16le",
                "-ac",
                str(SAMPLE_CHANNELS),
                "-ar",
                str(_TTS_SAMPLE_RATE),
                "-nostats",
                "pipe:",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                close_fds=False,  # use posix_spawn in CPython < 3.13
            )
            assert proc.stdout is not None
            while True:
                chunk_bytes = await proc.stdout.read(_ANNOUNCE_CHUNK_BYTES)
                if not chunk_bytes:
                    break

                chunk = AudioChunk(
                    rate=_TTS_SAMPLE_RATE,
                    width=SAMPLE_WIDTH,
                    channels=SAMPLE_CHANNELS,
                    audio=chunk_bytes,
                    timestamp=timestamp,
                )
                await self._client.write_event(chunk.event())

                timestamp += chunk.milliseconds
        finally:
            await self._client.write_event(AudioStop().event())
            if timestamp > 0:
                # Wait the length of the audio or until we receive a played event
                audio_seconds = timestamp / 1000
                try:
                    async with asyncio.timeout(audio_seconds + 0.5):
                        await self._played_event_received.wait()
                except TimeoutError:
                    # Older satellite clients will wait longer than necessary
                    _LOGGER.debug("Did not receive played event for announcement")

    async def async_start_conversation(
        self, start_announcement: AssistSatelliteAnnouncement
    ) -> None:
        """Start a conversation from the satellite."""
        await self.async_announce(start_announcement)
        self._run_pipeline_once(
            RunPipeline(
                start_stage=PipelineStage.ASR,
                end_stage=PipelineStage.TTS,
                restart_on_end=False,
            )
        )

    def _custom_settings_changed(
        self, setting: str | None = None, value: Any = None
    ) -> None:
        """Run when device screen settings change."""
        if self._client is not None and self._client.can_write_event():
            self.config_entry.async_create_background_task(
                self.hass,
                self._client.write_event(
                    CustomEvent(
                        SETTINGS_EVENT_TYPE,
                        {
                            SETTINGS_EVENT_TYPE: dict(
                                sorted(self.device.custom_settings.items())
                            )
                            if setting is None
                            else {setting: value}
                        },
                    ).event()
                ),
                "custom settings event",
            )

    def _send_custom_action(
        self, command: str, payload: str | float | None = None
    ) -> None:
        """Send a media player command to the satellite."""
        if self._client is not None and self._client.can_write_event():
            self.config_entry.async_create_background_task(
                self.hass,
                self._client.write_event(
                    CustomEvent(
                        ACTION_EVENT_TYPE,
                        {"action": command, "payload": payload},
                    ).event()
                ),
                "media player command",
            )

    @callback
    def _handle_timer(
        self, event_type: intent.TimerEventType, timer: intent.TimerInfo
    ) -> None:
        """Forward timer events to view assist."""
        super()._handle_timer(event_type, timer)
        # Send timer event to custom listeners
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_{self.device.device_id}_timer_event",
            self.device.device_id,
            event_type,
            timer,
        )
