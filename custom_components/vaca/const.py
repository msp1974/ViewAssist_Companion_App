"""Constants for the Wyoming integration."""

DOMAIN = "vaca"
MIN_APK_VERSION = "0.14.0-beta1"

CONF_HA_URL = "ha_url"

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
SAMPLE_CHANNELS = 1

# For multi-speaker voices, this is the name of the selected speaker.
ATTR_SPEAKER = "speaker"

CONF_DEFAULT_DASHBOARD = "default_dashboard"

SERVICE_SEND_EVENT = "send_event"
ATTR_EVENT_NAME = "event_name"
ATTR_EVENT_VALUE = "event_value"
SEND_EVENT_NAMES = [
    "navigate",
    "alarm",
    "toast-message",
    "refresh",
    "wake",
    "interrupt",
    "get-logs",
]

INTENT_EVENT = f"{DOMAIN}_intent_event"

URL_BASE = DOMAIN
CUSTOM_PATH = "custom"
LOGS_PATH = "logs"
MWW_PATH = "microwakeword"
OWW_PATH = "openwakeword"
WW_SOUNDS_PATH = "wakeword_sounds"
ALARMS_PATH = "alarms"
SUB_DIRS = [MWW_PATH, OWW_PATH, WW_SOUNDS_PATH, ALARMS_PATH]
