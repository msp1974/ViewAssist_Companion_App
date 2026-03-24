"""Focused logic tests for VACA integration modules."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
VACA_DIR = ROOT / "custom_components" / "vaca"


@pytest.fixture(autouse=True)
def _restore_stubbed_modules():
    """Avoid leaking stub modules across tests."""
    snapshot = dict(sys.modules)
    yield

    prefixes = ("custom_components", "homeassistant", "wyoming")
    for name in list(sys.modules):
        if name.startswith(prefixes) and name not in snapshot:
            del sys.modules[name]
    for name, module in snapshot.items():
        if name.startswith(prefixes):
            sys.modules[name] = module


def _ensure_package_modules() -> None:
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    vaca_pkg = types.ModuleType("custom_components.vaca")
    vaca_pkg.__path__ = [str(VACA_DIR)]
    sys.modules["custom_components"] = custom_components
    sys.modules["custom_components.vaca"] = vaca_pkg


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_common_homeassistant_stubs() -> None:
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    config_entries = types.ModuleType("homeassistant.config_entries")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    helpers_cv = types.ModuleType("homeassistant.helpers.config_validation")
    helpers_dr = types.ModuleType("homeassistant.helpers.device_registry")
    helpers_typing = types.ModuleType("homeassistant.helpers.typing")
    exceptions = types.ModuleType("homeassistant.exceptions")
    const = types.ModuleType("homeassistant.const")

    class _Platform:
        ASSIST_SATELLITE = "assist_satellite"
        BINARY_SENSOR = "binary_sensor"
        BUTTON = "button"
        SELECT = "select"
        SWITCH = "switch"
        MEDIA_PLAYER = "media_player"
        NUMBER = "number"
        SENSOR = "sensor"

    class _HomeAssistantError(Exception):
        pass

    class _ConfigEntryNotReady(Exception):
        pass

    const.Platform = _Platform
    helpers_cv.empty_config_schema = lambda _domain: {}
    helpers_dr.async_get = lambda _hass: Mock()
    helpers_typing.ConfigType = dict
    exceptions.HomeAssistantError = _HomeAssistantError
    exceptions.ConfigEntryNotReady = _ConfigEntryNotReady
    core.HomeAssistant = object

    def callback(func):
        return func

    core.callback = callback
    config_entries.ConfigEntry = object

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.config_validation"] = helpers_cv
    sys.modules["homeassistant.helpers.device_registry"] = helpers_dr
    sys.modules["homeassistant.helpers.typing"] = helpers_typing
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.const"] = const


def _install_init_module_stubs(fake_client_cls):
    _ensure_package_modules()
    _install_common_homeassistant_stubs()

    wyoming_mod = types.ModuleType("homeassistant.components.wyoming")
    wyoming_mod.DomainDataItem = object
    wyoming_mod.WyomingService = object
    wyoming_mod.async_register_websocket_api = lambda _hass: None
    sys.modules["homeassistant.components.wyoming"] = wyoming_mod

    client_mod = types.ModuleType("custom_components.vaca.client")
    client_mod.AsyncTcpClient = fake_client_cls
    sys.modules["custom_components.vaca.client"] = client_mod

    const_mod = types.ModuleType("custom_components.vaca.const")
    const_mod.ATTR_SPEAKER = "speaker"
    const_mod.DOMAIN = "vaca"
    sys.modules["custom_components.vaca.const"] = const_mod

    class _CustomEvent:
        def __init__(self, event_type: str, event_data=None):
            self.event_type = event_type
            self.event_data = event_data

        def event(self):
            return types.SimpleNamespace(
                type="custom-vaca",
                data={"event_type": self.event_type, "data": self.event_data},
            )

        @staticmethod
        def is_type(event_type: str) -> bool:
            return event_type == "custom-vaca"

        @staticmethod
        def from_event(event):
            return types.SimpleNamespace(event_data=event.data.get("data"))

    custom_mod = types.ModuleType("custom_components.vaca.custom")
    custom_mod.CustomEvent = _CustomEvent
    sys.modules["custom_components.vaca.custom"] = custom_mod

    devices_mod = types.ModuleType("custom_components.vaca.devices")
    devices_mod.VASatelliteDevice = object
    sys.modules["custom_components.vaca.devices"] = devices_mod


def _install_assist_module_stubs():
    _ensure_package_modules()
    _install_common_homeassistant_stubs()

    # Wyoming event/audio/pipeline stubs
    wyoming_pkg = types.ModuleType("wyoming")
    wyoming_audio = types.ModuleType("wyoming.audio")
    wyoming_event = types.ModuleType("wyoming.event")
    wyoming_info = types.ModuleType("wyoming.info")
    wyoming_pipeline = types.ModuleType("wyoming.pipeline")
    wyoming_satellite = types.ModuleType("wyoming.satellite")

    class Event:
        def __init__(self, type: str, data=None):
            self.type = type
            self.data = data or {}

    class AudioStop:
        @staticmethod
        def is_type(event_type: str) -> bool:
            return event_type == "audio-stop"

        def event(self):
            return Event("audio-stop", {})

    class AudioStart:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def event(self):
            return Event("audio-start", self.kwargs)

    class AudioChunk:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.milliseconds = 20
            self.seconds = 0.02

        def event(self):
            return Event("audio-chunk", self.kwargs)

    class Describe:
        def is_type(self, event_type: str) -> bool:
            return event_type == "describe"

    class PipelineStage:
        ASR = "asr"
        TTS = "tts"

    class RunPipeline:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class RunSatellite:
        def is_type(self, event_type: str) -> bool:
            return event_type == "run-satellite"

    wyoming_audio.AudioChunk = AudioChunk
    wyoming_audio.AudioStart = AudioStart
    wyoming_audio.AudioStop = AudioStop
    wyoming_event.Event = Event
    wyoming_info.Describe = Describe
    wyoming_pipeline.PipelineStage = PipelineStage
    wyoming_pipeline.RunPipeline = RunPipeline
    wyoming_satellite.RunSatellite = RunSatellite

    sys.modules["wyoming"] = wyoming_pkg
    sys.modules["wyoming.audio"] = wyoming_audio
    sys.modules["wyoming.event"] = wyoming_event
    sys.modules["wyoming.info"] = wyoming_info
    sys.modules["wyoming.pipeline"] = wyoming_pipeline
    sys.modules["wyoming.satellite"] = wyoming_satellite

    # Home Assistant component stubs used by assist_satellite module.
    ha_components = sys.modules["homeassistant.components"]
    assist_pipeline_mod = types.ModuleType("homeassistant.components.assist_pipeline")
    ffmpeg_mod = types.ModuleType("homeassistant.components.ffmpeg")
    tts_mod = types.ModuleType("homeassistant.components.tts")
    intent_mod = types.ModuleType("homeassistant.components.intent")
    assist_satellite_mod = types.ModuleType("homeassistant.components.assist_satellite")
    wyoming_component_mod = types.ModuleType("homeassistant.components.wyoming")
    wyoming_assist_mod = types.ModuleType(
        "homeassistant.components.wyoming.assist_satellite"
    )

    class PipelineEventType:
        RUN_START = "run_start"
        RUN_END = "run_end"
        STT_END = "stt_end"
        TTS_START = "tts_start"
        INTENT_END = "intent_end"

    class PipelineEvent:
        def __init__(self, event_type: str, data=None):
            self.type = event_type
            self.data = data

    class AssistSatelliteEntityFeature:
        ANNOUNCE = 1
        START_CONVERSATION = 2

    class AssistSatelliteEntityDescription:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class AssistSatelliteAnnouncement:
        pass

    class WyomingAssistSatellite:
        def on_pipeline_event(self, _event):
            return None

    assist_pipeline_mod.PipelineEvent = PipelineEvent
    assist_pipeline_mod.PipelineEventType = PipelineEventType
    assist_satellite_mod.AssistSatelliteAnnouncement = AssistSatelliteAnnouncement
    assist_satellite_mod.AssistSatelliteEntityDescription = (
        AssistSatelliteEntityDescription
    )
    assist_satellite_mod.AssistSatelliteEntityFeature = AssistSatelliteEntityFeature
    wyoming_component_mod.DomainDataItem = object
    wyoming_component_mod.WyomingService = object
    wyoming_assist_mod.WyomingAssistSatellite = WyomingAssistSatellite
    intent_mod.TimerEventType = object
    intent_mod.TimerInfo = object

    ha_components.assist_pipeline = assist_pipeline_mod
    ha_components.ffmpeg = ffmpeg_mod
    ha_components.tts = tts_mod
    ha_components.intent = intent_mod

    sys.modules["homeassistant.components.assist_pipeline"] = assist_pipeline_mod
    sys.modules["homeassistant.components.ffmpeg"] = ffmpeg_mod
    sys.modules["homeassistant.components.tts"] = tts_mod
    sys.modules["homeassistant.components.intent"] = intent_mod
    sys.modules["homeassistant.components.assist_satellite"] = assist_satellite_mod
    sys.modules["homeassistant.components.wyoming"] = wyoming_component_mod
    sys.modules["homeassistant.components.wyoming.assist_satellite"] = wyoming_assist_mod

    helpers_dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    helpers_dispatcher.async_dispatcher_send = Mock()
    helpers_entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    helpers_entity_platform.AddConfigEntryEntitiesCallback = object
    sys.modules["homeassistant.helpers.dispatcher"] = helpers_dispatcher
    sys.modules["homeassistant.helpers.entity_platform"] = helpers_entity_platform

    # Local integration module stubs referenced by assist_satellite.
    client_mod = types.ModuleType("custom_components.vaca.client")
    client_mod.VAAsyncTcpClient = object
    sys.modules["custom_components.vaca.client"] = client_mod

    const_mod = types.ModuleType("custom_components.vaca.const")
    const_mod.DOMAIN = "vaca"
    const_mod.MIN_APK_VERSION = "0.10.0"
    const_mod.SAMPLE_CHANNELS = 1
    const_mod.SAMPLE_WIDTH = 2
    sys.modules["custom_components.vaca.const"] = const_mod

    class PipelineEnded:
        def __init__(self, continue_conversation: bool = False):
            self.continue_conversation = continue_conversation

        def event(self):
            return Event(
                "pipeline-ended",
                {"continue_conversation": self.continue_conversation},
            )

    class CustomEvent:
        def __init__(self, event_type: str, event_data=None):
            self.event_type = event_type
            self.event_data = event_data

        def event(self):
            data = {"event_type": self.event_type}
            if self.event_data is not None:
                data["data"] = self.event_data
            return Event("custom-vaca", data)

        @staticmethod
        def is_type(event_type: str) -> bool:
            return event_type == "custom-vaca"

        @staticmethod
        def from_event(event):
            return types.SimpleNamespace(
                event_type=event.data.get("event_type"),
                event_data=event.data.get("data"),
            )

    custom_mod = types.ModuleType("custom_components.vaca.custom")
    custom_mod.ACTION_EVENT_TYPE = "action"
    custom_mod.CAPABILITIES_EVENT_TYPE = "capabilities"
    custom_mod.SETTINGS_EVENT_TYPE = "settings"
    custom_mod.STATUS_EVENT_TYPE = "status"
    custom_mod.CustomEvent = CustomEvent
    custom_mod.PipelineEnded = PipelineEnded
    custom_mod.getIntegrationVersion = AsyncMock(return_value="0.10.0")
    custom_mod.getVADashboardPath = Mock(return_value="")
    sys.modules["custom_components.vaca.custom"] = custom_mod

    devices_mod = types.ModuleType("custom_components.vaca.devices")
    devices_mod.VASatelliteDevice = object
    sys.modules["custom_components.vaca.devices"] = devices_mod

    entity_mod = types.ModuleType("custom_components.vaca.entity")
    entity_mod.VASatelliteEntity = object
    sys.modules["custom_components.vaca.entity"] = entity_mod


def test_get_device_capabilities_retries_then_succeeds():
    class FakeClient:
        attempts = 0

        def __init__(self, *_args, **_kwargs):
            self._events = []

        async def __aenter__(self):
            FakeClient.attempts += 1
            return self

        async def __aexit__(self, *_args):
            return False

        async def write_event(self, _event):
            return None

        async def read_event(self):
            if FakeClient.attempts == 1:
                raise OSError("temporary")
            return types.SimpleNamespace(
                type="custom-vaca",
                data={
                    "event_type": "capabilities",
                    "data": {"capabilities": {"model": "Pixel"}},
                },
            )

    _install_init_module_stubs(FakeClient)
    module = _load_module("custom_components.vaca", VACA_DIR / "__init__.py")
    module.asyncio.sleep = AsyncMock()

    item = types.SimpleNamespace(service=types.SimpleNamespace(host="127.0.0.1", port=10700))
    result = asyncio.run(module.get_device_capabilities(item))

    assert result == {"model": "Pixel"}
    assert FakeClient.attempts == 2


def test_get_device_capabilities_returns_none_after_failures():
    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def write_event(self, _event):
            return None

        async def read_event(self):
            return None

    _install_init_module_stubs(FakeClient)
    module = _load_module("custom_components.vaca", VACA_DIR / "__init__.py")
    module.asyncio.sleep = AsyncMock()

    item = types.SimpleNamespace(service=types.SimpleNamespace(host="127.0.0.1", port=10700))
    result = asyncio.run(module.get_device_capabilities(item))

    assert result is None


def test_on_receive_event_ping_sends_pong_and_swallow():
    _install_assist_module_stubs()
    module = _load_module(
        "custom_components.vaca.assist_satellite", VACA_DIR / "assist_satellite.py"
    )

    entity = object.__new__(module.VACASatelliteAssistEntity)
    entity.hass = object()
    recorded_tasks = []

    class _Entry:
        def async_create_background_task(self, _hass, coro, _name):
            recorded_tasks.append(coro)

    class _Client:
        def can_write_event(self):
            return True

        async def write_event(self, event):
            self.last_event = event

    entity.config_entry = _Entry()
    entity._client = _Client()
    entity.device = types.SimpleNamespace(device_id="abc")
    entity.stream_tts = True

    forward, event = entity.on_receive_event_callback(module.Event("ping", {}))

    assert forward is False
    assert event is None
    assert len(recorded_tasks) == 1
    asyncio.run(recorded_tasks[0])
    assert entity._client.last_event.type == "pong"


def test_on_receive_custom_event_updates_capabilities_and_dispatches():
    _install_assist_module_stubs()
    module = _load_module(
        "custom_components.vaca.assist_satellite", VACA_DIR / "assist_satellite.py"
    )
    module.async_dispatcher_send = Mock()

    entity = object.__new__(module.VACASatelliteAssistEntity)
    entity.hass = object()
    entity.device = types.SimpleNamespace(device_id="dev-1", capabilities={})
    entity._client = None

    evt = module.Event(
        "custom-vaca",
        {
            "event_type": "capabilities",
            "data": {"capabilities": {"release": "14"}},
        },
    )
    forward, returned = entity.on_receive_event_callback(evt)

    assert forward is False
    assert returned is None
    assert entity.device.capabilities == {"release": "14"}
    module.async_dispatcher_send.assert_called_once()


def test_on_receive_audio_stop_disables_stream_and_forwards():
    _install_assist_module_stubs()
    module = _load_module(
        "custom_components.vaca.assist_satellite", VACA_DIR / "assist_satellite.py"
    )

    entity = object.__new__(module.VACASatelliteAssistEntity)
    entity.hass = object()
    entity.device = types.SimpleNamespace(device_id="dev-1", capabilities={})
    entity._client = None
    entity.stream_tts = True

    audio_stop = module.Event("audio-stop", {})
    forward, returned = entity.on_receive_event_callback(audio_stop)

    assert entity.stream_tts is False
    assert forward is True
    assert returned is audio_stop


def test_on_pipeline_event_run_start_and_run_end_behaviour():
    _install_assist_module_stubs()
    module = _load_module(
        "custom_components.vaca.assist_satellite", VACA_DIR / "assist_satellite.py"
    )

    entity = object.__new__(module.VACASatelliteAssistEntity)
    entity.hass = object()
    entity._continue_conversation = True
    entity._client = types.SimpleNamespace(write_event=AsyncMock())
    entity.device = types.SimpleNamespace(device_id="abc")
    entity.stream_tts = False
    recorded_tasks = []

    class _Entry:
        def async_create_background_task(self, _hass, coro, _name):
            recorded_tasks.append(coro)

    entity.config_entry = _Entry()

    run_start_event = module.assist_pipeline.PipelineEvent(
        module.assist_pipeline.PipelineEventType.RUN_START,
        data={"run": True},
    )
    entity.on_pipeline_event(run_start_event)
    assert run_start_event.data["tts_output"] == {"token": ""}

    run_end_event = module.assist_pipeline.PipelineEvent(
        module.assist_pipeline.PipelineEventType.RUN_END,
        data={},
    )
    entity.on_pipeline_event(run_end_event)
    assert entity._continue_conversation is False
    assert len(recorded_tasks) == 1

    asyncio.run(recorded_tasks[0])
    sent_event = entity._client.write_event.await_args.args[0]
    assert sent_event.type == "pipeline-ended"
    assert sent_event.data["continue_conversation"] is True
