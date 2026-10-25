"""Diagnostics support for VACA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_URL
from homeassistant.core import HomeAssistant

from .const import CONF_HA_URL, DOMAIN
from .devices import VASatelliteDevice

TO_REDACT = {CONF_HOST, CONF_URL, CONF_HA_URL, "rtsp_url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    item = hass.data[DOMAIN][entry.entry_id]
    device: VASatelliteDevice | None = item.device  # type: ignore[assignment]

    diagnostics: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
    }

    if device is not None:
        diagnostics["device"] = {
            "connected": device.connected,
            "info": device.info.event().data if device.info else None,
            "custom_settings": async_redact_data(
                device.custom_settings or {}, TO_REDACT
            ),
            "capabilities": device.capabilities,
            "rtsp_url_set": device.rtsp_url is not None,
        }

    return diagnostics
