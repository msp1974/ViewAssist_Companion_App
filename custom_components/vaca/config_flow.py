"""Config flow for Wyoming integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

# pylint: disable-next=hass-component-root-import
from homeassistant.components.wyoming.config_flow import WyomingConfigFlow
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import CONF_HA_DASHBOARD, CONF_HA_URL, DOMAIN
from .dashboard import merge_options

_LOGGER = logging.getLogger(__name__)


class VAWyomingConfigFlow(WyomingConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wyoming integration."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VAOptionsFlowHandler:
        """Create the options flow."""
        return VAOptionsFlowHandler()


class VAOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for the Wyoming integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data=merge_options(self.config_entry.options, user_input)
            )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HA_URL,
                    description={
                        "suggested_value": self.config_entry.options.get(CONF_HA_URL)
                    },
                ): str,
                vol.Optional(
                    CONF_HA_DASHBOARD,
                    description={
                        "suggested_value": self.config_entry.options.get(
                            CONF_HA_DASHBOARD
                        )
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
