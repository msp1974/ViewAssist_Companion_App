"""Diagnostics support"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.wyoming import DomainDataItem
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .devices import VASatelliteDevice

TO_REDACT = [CONF_HOST]

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}

    diag["config"] = config_entry.as_dict()

    domain_data: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    if hasattr(domain_data, "device"):
        device: VASatelliteDevice = domain_data.device  # type: ignore[assignment]

        diag["device"]: Dict[str, Any] = {
            "custom_settings": device.custom_settings,
            "capabilities": device.capabilities,
        }

        if device.info is not None:
            info: Dict[str, Any] = {}
            info["asr"] = [item.to_dict() for item in device.info.asr] if device.info.asr else []
            info["tts"] = [item.to_dict() for item in device.info.tts] if device.info.tts else []
            info["handle"] = [item.to_dict() for item in device.info.handle] if device.info.handle else []
            info["intent"] = [item.to_dict() for item in device.info.intent] if device.info.intent else []
            info["wake"] = [item.to_dict() for item in device.info.wake] if device.info.wake else []
            info["mic"] = [item.to_dict() for item in device.info.mic] if device.info.mic else []
            info["snd"] = [item.to_dict() for item in device.info.snd] if device.info.snd else []
            info["satellite"] = device.info.satellite.to_dict() if device.info.satellite is not None else []
            diag["device"]["info"] = info

    return async_redact_data(diag, TO_REDACT)
