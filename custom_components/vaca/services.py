"""Services for the VACA integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    ATTR_EVENT_NAME,
    ATTR_EVENT_VALUE,
    DOMAIN,
    SEND_EVENT_NAMES,
    SERVICE_SEND_EVENT,
)
from .devices import VASatelliteDevice

_LOGGER = logging.getLogger(__name__)

SEND_EVENT_SCHEMA = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
        vol.Required(ATTR_EVENT_NAME): vol.In(SEND_EVENT_NAMES),
        vol.Required(ATTR_EVENT_VALUE): vol.All(dict, vol.Length(min=1)),
    }
)


async def _async_send_event(call: ServiceCall) -> None:
    """Send a custom event to the targeted devices."""
    hass = call.hass
    event_name: str = call.data[ATTR_EVENT_NAME]
    event_value: dict[str, Any] = call.data[ATTR_EVENT_VALUE]

    entry_ids = await async_extract_config_entry_ids(call)

    devices: list[VASatelliteDevice] = []
    for entry_id in entry_ids:
        item = hass.data.get(DOMAIN, {}).get(entry_id)
        if item is not None and item.device is not None:
            devices.append(item.device)

    if not devices:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_target_devices",
        )

    for device in devices:
        device.send_custom_action(event_name, event_value)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register VACA services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_EVENT,
        _async_send_event,
        schema=SEND_EVENT_SCHEMA,
    )
