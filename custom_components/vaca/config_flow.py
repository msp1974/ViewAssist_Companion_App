"""Config flow for ViewAssist Companion App (VACA)."""

from __future__ import annotations

import logging

# pylint: disable-next=hass-component-root-import
from homeassistant.components.wyoming.config_flow import WyomingConfigFlow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VACAConfigFlow(WyomingConfigFlow, domain=DOMAIN):
    """Handle a config flow for VACA integration."""
