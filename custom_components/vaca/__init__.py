"""The ViewAssist Companion App (VACA) integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.wyoming import (
    DomainDataItem,
    WyomingService,
    async_register_websocket_api,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .client import AsyncTcpClient
from .const import ATTR_SPEAKER, DOMAIN
from .custom import CustomEvent
from .devices import VASatelliteDevice

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SATELLITE_PLATFORMS = [
    Platform.ASSIST_SATELLITE,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SENSOR,
]

__all__ = [
    "ATTR_SPEAKER",
    "DOMAIN",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]


class VACAError(HomeAssistantError):
    """Base class for VACA errors."""


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the VACA integration."""
    async_register_websocket_api(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load VACA."""
    service = await WyomingService.create(entry.data["host"], entry.data["port"])

    if service is None:
        raise ConfigEntryNotReady("Unable to connect")

    item = DomainDataItem(service=service)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = item

    await hass.config_entries.async_forward_entry_setups(entry, service.platforms)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    if (satellite_info := service.info.satellite) is not None:
        # Create satellite device
        dev_reg = dr.async_get(hass)

        # Use config entry id since only one satellite per entry is supported
        satellite_id = entry.entry_id
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, satellite_id)},
            name=satellite_info.name,
            suggested_area=satellite_info.area,
        )

        item.device = VASatelliteDevice(
            satellite_id=satellite_id,
            device_id=device.id,
        )
        item.device.capabilities = await get_device_capabilities(item)

        # Update device info with capabilities
        if item.device.capabilities:
            app_version = item.device.capabilities.get("app_version")
            android_version = item.device.capabilities.get("release")
            manufacturer = item.device.capabilities.get("manufacturer")
            model = item.device.capabilities.get("model")

            sw_version = (
                f"View Assist Companion App {app_version}" if app_version else None
            )
            hw_version = f"Android {android_version}" if android_version else None

            dev_reg.async_update_device(
                device.id,
                manufacturer=manufacturer,
                model=model,
                sw_version=sw_version,
                hw_version=hw_version,
            )

        # Set up satellite entity, sensors, switches, etc.
        await hass.config_entries.async_forward_entry_setups(entry, SATELLITE_PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload VACA."""
    item: DomainDataItem = hass.data[DOMAIN][entry.entry_id]

    platforms = list(item.service.platforms)
    if item.device is not None:
        platforms += SATELLITE_PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok


async def get_device_capabilities(item: DomainDataItem):
    """Get device capabilities."""
    capabilities: dict[str, Any] | None = None

    for attempt in range(4):
        try:
            async with (
                AsyncTcpClient(item.service.host, item.service.port) as client,
                asyncio.timeout(2),
            ):
                # Describe -> Info
                await client.write_event(CustomEvent("capabilities").event())
                while True:
                    event = await client.read_event()
                    if event is None:
                        raise VACAError(  # noqa: TRY301
                            "Connection closed unexpectedly",
                        )

                    if CustomEvent.is_type(event.type) and (
                        event_data := CustomEvent.from_event(event).event_data
                    ):
                        capabilities = event_data.get("capabilities")
                        break  # while

                if capabilities is not None:
                    break  # for
        except (TimeoutError, OSError, VACAError) as ex:
            _LOGGER.debug(
                "Attempt %s/4: Error getting device capabilities at %s:%s: %s",
                attempt + 1,
                item.service.host,
                item.service.port,
                ex,
            )
            # Sleep and try again
            await asyncio.sleep(1)

    if capabilities is None:
        _LOGGER.warning(
            "Failed to get device capabilities for satellite at %s:%s after 4 attempts",
            item.service.host,
            item.service.port,
        )

    return capabilities
