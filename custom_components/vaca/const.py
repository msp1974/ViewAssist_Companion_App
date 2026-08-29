"""Constants for the Wyoming integration."""

DOMAIN = "vaca"
MIN_APK_VERSION = "0.12.1"

CONF_HA_URL = "ha_url"

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
SAMPLE_CHANNELS = 1

# For multi-speaker voices, this is the name of the selected speaker.
ATTR_SPEAKER = "speaker"

INTENT_EVENT = f"{DOMAIN}_intent_event"

URL_BASE = DOMAIN
CUSTOM_PATH = "custom"
MWW_PATH = "microwakeword"
OWW_PATH = "openwakeword"
WW_SOUNDS_PATH = "wakeword_sounds"
ALARMS_PATH = "alarms"
SUB_DIRS = [MWW_PATH, OWW_PATH, WW_SOUNDS_PATH, ALARMS_PATH]
