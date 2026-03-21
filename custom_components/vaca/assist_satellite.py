"""Assist satellite entity for Wyoming integration."""

from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Any, Final
import wave

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Describe
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import RunSatellite

from homeassistant.components import assist_pipeline, ffmpeg, tts
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
from homeassistant.components import intent

from .client import VAAsyncTcpClient
from .const import DOMAIN, MIN_APK_VERSION, SAMPLE_CHANNELS, SAMPLE_WIDTH
from .custom import (
    ACTION_EVENT_TYPE,
    CAPABILITIES_EVENT_TYPE,
    SETTINGS_EVENT_TYPE,
    STATUS_EVENT_TYPE,
    CustomEvent,
    PipelineEnded,
    getIntegrationVersion,
    getVADashboardPath,
)
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

_LOGGER = logging.getLogger(__name__)

_SAMPLES_PER_CHUNK: Final = 1024
_RECONNECT_SECONDS: Final = 10
_RESTART_SECONDS: Final = 3
_PING_TIMEOUT: Final = 5
_PING_SEND_DELAY: Final = 2
_PIPELINE_FINISH_TIMEOUT: Final = 1
_TTS_SAMPLE_RATE: Final = 22050
_ANNOUNCE_CHUNK_BYTES: Final = 2048  # 1024 samples
_TTS_TIMEOUT_EXTRA: Final = 1.0


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

        if RunSatellite().is_type(event.type):
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
                    self.hass.config.internal_url
                    if self.hass.config.internal_url
                    else ""
                )
                home = getVADashboardPath(self.hass, self.device.satellite_id)
                self.device.custom_settings["ha_dashboard"] = home.removeprefix("/")
                # Send config event
            self._custom_settings_changed()

    async def on_after_send_event_callback(self, event: Event) -> None:
        """Allow injection of events after event sent."""
        if Describe().is_type(event.type) and self._client:
            await self._client.write_event(CustomEvent("capabilities").event())

    @callback
    def on_receive_event_callback(self, event: Event) -> tuple[bool, Event | None]:
        """Handle received custom events."""
        if event and AudioStop.is_type(event.type):
            self.stream_tts = False
            return not self.stream_tts, event

        if event and CustomEvent.is_type(event.type):
            # Custom event
            evt = CustomEvent.from_event(event)

            if evt.event_type == CAPABILITIES_EVENT_TYPE and evt.event_data:
                self.device.capabilities = evt.event_data.get("capabilities", {})

            elif evt.event_type in (STATUS_EVENT_TYPE, SETTINGS_EVENT_TYPE):
                _LOGGER.debug(
                    "Received %s event: %s",
                    evt.event_type,
                    evt.event_data,
                )

            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.device.device_id}_{evt.event_type}_update",
                evt.event_data,
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
            # Fix for error when running pipeline for ask question
            if event.data and not event.data.get("tts_output"):
                event.data["tts_output"] = {"token": ""}
        elif event.type == assist_pipeline.PipelineEventType.RUN_END:
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
            if event.data:
                _LOGGER.debug(
                    "Intent %s complete: %s",
                    event.type,
                    event.data,
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
                end_stage=PipelineStage.ASR,
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
                            SETTINGS_EVENT_TYPE: self.device.custom_settings
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

    async def _stream_tts(self, tts_result: tts.ResultStream) -> None:
        """Stream TTS WAV audio to satellite in chunks."""
        assert self._client is not None

        if tts_result.extension != "wav":
            raise ValueError(
                f"Cannot stream audio format to satellite: {tts_result.extension}"
            )

        # Track the total duration of TTS audio for response timeout
        total_seconds = 0.0
        start_time = time.monotonic()

        try:
            data = b"".join([chunk async for chunk in tts_result.async_stream_result()])

            with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                sample_channels = wav_file.getnchannels()
                _LOGGER.debug("Streaming %s TTS sample(s)", wav_file.getnframes())

                # Start audio stream - set flag to allow streaming
                self.stream_tts = True

                timestamp = 0
                await self._client.write_event(
                    AudioStart(
                        rate=sample_rate,
                        width=sample_width,
                        channels=sample_channels,
                        timestamp=timestamp,
                    ).event()
                )

                # Stream audio chunks
                while audio_bytes := wav_file.readframes(_SAMPLES_PER_CHUNK):
                    # If flag set to false, stop streaming
                    if not self.stream_tts:
                        _LOGGER.debug("TTS streaming interrupted")
                        break
                    chunk = AudioChunk(
                        rate=sample_rate,
                        width=sample_width,
                        channels=sample_channels,
                        audio=audio_bytes,
                        timestamp=timestamp,
                    )
                    await self._client.write_event(chunk.event())
                    timestamp += int(chunk.seconds)
                    total_seconds += chunk.seconds

                await self._client.write_event(AudioStop(timestamp=timestamp).event())
                _LOGGER.debug("TTS streaming complete")
        finally:
            send_duration = time.monotonic() - start_time
            timeout_seconds = max(0, total_seconds - send_duration + _TTS_TIMEOUT_EXTRA)

            if self._played_event_received is None:
                self._played_event_received = asyncio.Event()
            self._played_event_received.clear()

            self.config_entry.async_create_background_task(
                self.hass,
                self._tts_timeout(timeout_seconds, self._run_loop_id),
                name="wyoming TTS timeout",
            )

    async def _tts_timeout(
        self, timeout_seconds: float, run_loop_id: str | None
    ) -> None:
        """Force state change to IDLE in case TTS played event isn't received."""
        await asyncio.sleep(timeout_seconds + _TTS_TIMEOUT_EXTRA)

        if (
            self._played_event_received is not None
            and self._played_event_received.is_set()
        ):
            # Played event already received
            return

        if run_loop_id != self._run_loop_id:
            # On a different pipeline run now
            return

        self.tts_response_finished()

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
