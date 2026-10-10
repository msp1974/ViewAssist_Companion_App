"""Wyoming switch entities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .devices import VASatelliteDevice
from .entity import VASatelliteEntity

if TYPE_CHECKING:
    from homeassistant.components.wyoming import DomainDataItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    device: VASatelliteDevice = item.device  # type: ignore[assignment]

    # Setup is only forwarded for satellites
    assert device is not None
    entities = [
        WyomingSatelliteMuteSwitch(device),
        WyomingSatelliteScreenSwitch(device),
        WyomingSatelliteQuickActionsSheetSwitch(device),
        WyomingSatelliteScreenAutoBrightnessSwitch(device),
        WyomingSatelliteScreenAlwaysOnSwitch(device),
        WyomingSatelliteDarkModeSwitch(device),
        WyomingSatelliteDiagnosticsSwitch(device),
        WyomingSatelliteContinueConversationSwitch(device),
        WyomingSatelliteAlarmSwitch(device),
        WyomingSatelliteScreenOnWakeWordSwitch(device),
        WyomingSatelliteScreenSaverSwitch(device),
    ]

    if capabilities := device.capabilities:
        if capabilities.get("has_dnd"):
            entities.append(WyomingSatelliteDNDSwitch(device))

    if device.supportBump():
        entities.append(WyomingSatelliteScreenOnBumpSwitch(device))

    if device.supportProximity():
        entities.append(WyomingSatelliteScreenOnProximitySwitch(device))

    if device.supports_motion_detection():
        entities.append(WyomingSatelliteScreenOnMotionSwitch(device))

    if entities:
        async_add_entities(entities)


class BaseSwitch(VASatelliteEntity, restore_state.RestoreEntity, SwitchEntity):
    """Base class for all switch entities."""

    entity_description: SwitchEntityDescription
    default_on = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()

        # Set restore state or default
        if state is None:
            self._attr_is_on = self.default_on
        else:
            self._attr_is_on = state.state == STATE_ON

        await self.do_switch(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.do_switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.do_switch(False)

    async def do_switch(self, value: bool, send_to_device: bool = True) -> None:
        """Perform the switch action."""
        self._attr_is_on = value
        self.async_write_ha_state()
        if send_to_device:
            _LOGGER.debug(
                "Setting %s to %s", self.entity_description.key, self._attr_is_on
            )
        self._device.set_custom_setting(
            self.entity_description.key, self._attr_is_on, send_to_device
        )


class BaseFeedbackSwitch(BaseSwitch):
    """Base class for switches that receive feedback from device."""

    _listener_class = "settings_update"

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self.status_update,
            )
        )

    async def status_update(self, data: dict[str, Any]) -> None:
        """Handle status update."""
        if settings := data.get("settings"):
            if self.entity_description.key in settings:
                setting_state = settings[self.entity_description.key]
                await self.do_switch(setting_state, send_to_device=False)


class WyomingSatelliteScreenSwitch(BaseFeedbackSwitch):
    """Entity to control screen on/off."""

    entity_description = SwitchEntityDescription(
        key="screen_on",
        translation_key="screen_on",
        icon="mdi:monitor",
    )
    default_on = True

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:monitor" if self._attr_is_on else "mdi:monitor-off"


class WyomingSatelliteMuteSwitch(BaseSwitch):
    """Entity to represent if satellite is muted."""

    entity_description = SwitchEntityDescription(key="mute", translation_key="mute")
    default_on = False

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:microphone-off" if self._attr_is_on else "mdi:microphone"


class WyomingSatelliteQuickActionsSheetSwitch(BaseSwitch):
    """Entity to control quick actions sheet."""

    entity_description = SwitchEntityDescription(
        key="quick_actions",
        translation_key="quick_actions",
        icon="mdi:gesture-tap-button",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class WyomingSatelliteScreenAutoBrightnessSwitch(BaseSwitch):
    """Entity to control screen auto brightness."""

    entity_description = SwitchEntityDescription(
        key="screen_auto_brightness",
        translation_key="screen_auto_brightness",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class WyomingSatelliteScreenAlwaysOnSwitch(BaseSwitch):
    """Entity to control screen always on."""

    entity_description = SwitchEntityDescription(
        key="screen_always_on",
        translation_key="screen_always_on",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class WyomingSatelliteDarkModeSwitch(BaseSwitch):
    """Entity to control screen always on."""

    entity_description = SwitchEntityDescription(
        key="dark_mode",
        translation_key="dark_mode",
        icon="mdi:compare",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class WyomingSatelliteDNDSwitch(BaseFeedbackSwitch):
    """Entity to control screen always on."""

    entity_description = SwitchEntityDescription(
        key="do_not_disturb",
        translation_key="do_not_disturb",
        icon="mdi:do-not-disturb",
    )
    default_on = False


class WyomingSatelliteDiagnosticsSwitch(BaseSwitch):
    """Entity to control diagnostics overlay on/off."""

    entity_description = SwitchEntityDescription(
        key="diagnostics_enabled",
        translation_key="diagnostics_enabled",
        icon="mdi:microphone-question",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    default_on = False


class WyomingSatelliteContinueConversationSwitch(BaseSwitch):
    """Entity to control continue conversation on/off."""

    entity_description = SwitchEntityDescription(
        key="continue_conversation",
        translation_key="continue_conversation",
        icon="mdi:message-bulleted",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class WyomingSatelliteAlarmSwitch(BaseFeedbackSwitch):
    """Entity to control alarm on/off."""

    entity_description = SwitchEntityDescription(
        key="alarm",
        translation_key="alarm",
        icon="mdi:alarm-bell",
    )
    default_on = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.hass.bus.async_listen(
                "va_alarm_start",
                self._handle_alarm_start_event,
            ),
        )
        self.async_on_remove(
            self.hass.bus.async_listen(
                "va_alarm_stop",
                self._handle_alarm_stop_event,
            ),
        )

    async def _handle_alarm_start_event(self, event) -> None:
        """Handle alarm event."""
        _LOGGER.debug("Received alarm sound event: %s", event.data)
        device_id = event.data.get("device_id")
        if device_id != self._device.device_id:
            return

        await self.do_switch(True, send_to_device=True)

    async def _handle_alarm_stop_event(self, event) -> None:
        """Handle alarm event."""
        _LOGGER.debug("Received alarm stop event: %s", event.data)
        device_id = event.data.get("device_id")
        if device_id != self._device.device_id:
            return

        await self.do_switch(False, send_to_device=True)

    async def do_switch(self, value: bool, send_to_device: bool = True) -> None:
        """Perform the switch action."""
        self._attr_is_on = value
        self.async_write_ha_state()
        if not value:
            self.hass.bus.async_fire(
                "vaca_alarm_stop",
                {
                    "device_id": self._device.device_id,
                },
            )

        if send_to_device:
            self._device.send_custom_action(
                self.entity_description.key,
                {
                    "activate": self._attr_is_on,
                    "url": "",
                },
            )


class WyomingSatelliteScreenOnWakeWordSwitch(BaseSwitch):
    """Entity to control screen on/off with wake word."""

    entity_description = SwitchEntityDescription(
        key="screen_on_wake_word",
        translation_key="screen_on_wake_word",
        icon="mdi:monitor-eye",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class WyomingSatelliteScreenOnBumpSwitch(BaseSwitch):
    """Entity to control screen on with bump."""

    entity_description = SwitchEntityDescription(
        key="screen_on_bump",
        translation_key="screen_on_bump",
        icon="mdi:gesture-tap",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class WyomingSatelliteScreenOnProximitySwitch(BaseSwitch):
    """Entity to control screen on with proximity."""

    entity_description = SwitchEntityDescription(
        key="screen_on_proximity",
        translation_key="screen_on_proximity",
        icon="mdi:radar",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class WyomingSatelliteScreenOnMotionSwitch(BaseSwitch):
    """Entity to control screen on with motion."""

    entity_description = SwitchEntityDescription(
        key="screen_on_motion",
        translation_key="screen_on_motion",
        icon="mdi:motion-sensor",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class WyomingSatelliteScreenSaverSwitch(BaseFeedbackSwitch):
    """Entity to control screen saver setting."""

    entity_description = SwitchEntityDescription(
        key="screen_saver",
        translation_key="screen_saver",
        icon="mdi:monitor-shimmer",
    )
    default_on = False
