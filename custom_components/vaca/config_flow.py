"""Config flow for Wyoming integration."""

from __future__ import annotations

import logging

# pylint: disable-next=hass-component-root-import
from homeassistant.components.wyoming.config_flow import WyomingConfigFlow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VAWyomingConfigFlow(WyomingConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wyoming integration."""
