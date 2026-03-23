"""Switch entities for ViewAssist Companion App (VACA)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import restore_state
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .custom import CustomActions
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
        VACAMicSwitch(device),
        VACAScreenSwitch(device),
        VACASwipeToRefreshSwitch(device),
        VACAScreenAutoBrightnessSwitch(device),
        VACAScreenAlwaysOnSwitch(device),
        VACADarkModeSwitch(device),
        VACADiagnosticsSwitch(device),
        VACAAlarmSwitch(device),
        VACAScreenOnWakeWordSwitch(device),
        VACAScreenSaverSwitch(device),
    ]

    # Optional switches based on capabilities
    if capabilities := device.capabilities:
        if capabilities.get("has_dnd"):
            entities.append(VACADNDSwitch(device))

    if device.supportBump():
        entities.append(VACAScreenOnBumpSwitch(device))

    if device.supportProximity():
        entities.append(VACAScreenOnProximitySwitch(device))

    if device.capabilities and device.capabilities.get("has_front_camera"):
        entities.append(VACAEnableMotionDetectionSwitch(device))
        entities.append(VACAScreenOnMotionSwitch(device))

    if entities:
        async_add_entities(entities)


class BaseSwitch(VASatelliteEntity, restore_state.RestoreEntity, SwitchEntity):
    """Base class for all VACA switch entities where HA is the source of truth."""

    entity_description: SwitchEntityDescription
    default_on = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()

        # Set restore state or default if available
        if state is not None:
             self._attr_is_on = state.state == STATE_ON
             # Push restored state to device settings store immediately
             await self.do_switch(self._attr_is_on, send_to_device=True)
        elif self.default_on is not None:
             self._attr_is_on = self.default_on
             # Populate settings store with default
             await self.do_switch(self._attr_is_on, send_to_device=True)

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
                self.entity_description.key, self._attr_is_on
            )


class BaseFeedbackSwitch(BaseSwitch):
    """Base class for switches where the device is the source of truth (lazy init)."""

    _listener_class = "settings_update"
    default_on = None # Wait for device feedback

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        # For feedback switches, we override to avoid redundant pushing of restored state
        await super(BaseSwitch, self).async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
             self._attr_is_on = state.state == STATE_ON
             # We rely on initial device status sync later
             await self.do_switch(self._attr_is_on, send_to_device=False)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._device.device_id}_{self._listener_class}",
                self.status_update,
            )
        )

    @callback
    def status_update(self, data: dict[str, Any] | None) -> None:
        """Handle status update."""
        if not data:
            return
        update_key = self.entity_description.key

        # Check settings or sensors depending on listener class
        if self._listener_class == "settings_update":
            update_source = "settings"
        elif self._listener_class == "status_update":
            update_source = "sensors"
        else:
            return

        if updates := data.get(update_source):
            if update_key in updates:
                self._attr_is_on = bool(updates[update_key])
                self.async_write_ha_state()


class VACAScreenSwitch(BaseFeedbackSwitch):
    """Entity to control screen on/off for VACA satellite (Feedback powered)."""

    _listener_class = "status_update"

    entity_description = SwitchEntityDescription(
        key="screen_on",
        translation_key="screen_on",
        icon="mdi:monitor",
    )

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:monitor" if self._attr_is_on else "mdi:monitor-off"

    async def do_switch(self, value: bool, send_to_device: bool = True) -> None:
        """Perform the switch action."""
        self._attr_is_on = value
        self.async_write_ha_state()
        if send_to_device:
            if value:
                self._device.send_custom_action(CustomActions.SCREEN_WAKE)
            else:
                self._device.send_custom_action(CustomActions.SCREEN_SLEEP)


class VACAMicSwitch(BaseSwitch):
    """Entity to represent if VACA satellite microphone is enabled (HA mastered)."""

    entity_description = SwitchEntityDescription(key="mic", translation_key="mic")
    default_on = True

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:microphone" if self._attr_is_on else "mdi:microphone-off"


class VACASwipeToRefreshSwitch(BaseSwitch):
    """Entity to control swipe to refresh on VACA satellite."""

    entity_description = SwitchEntityDescription(
        key="swipe_refresh",
        translation_key="swipe_refresh",
        icon="mdi:web-refresh",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class VACAScreenAutoBrightnessSwitch(BaseFeedbackSwitch):
    """Entity to control screen auto brightness on VACA satellite (device feedback)."""

    entity_description = SwitchEntityDescription(
        key="screen_auto_brightness",
        translation_key="screen_auto_brightness",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.CONFIG,
    )


class VACAScreenAlwaysOnSwitch(BaseSwitch):
    """Entity to control screen always on status for VACA satellite."""

    entity_description = SwitchEntityDescription(
        key="screen_always_on",
        translation_key="screen_always_on",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class VACADarkModeSwitch(BaseSwitch):
    """Entity to control dark mode for VACA satellite."""

    entity_description = SwitchEntityDescription(
        key="dark_mode",
        translation_key="dark_mode",
        icon="mdi:compare",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class VACADNDSwitch(BaseFeedbackSwitch):
    """Entity to control do not disturb for VACA satellite (Feedback powered)."""

    entity_description = SwitchEntityDescription(
        key="do_not_disturb",
        translation_key="do_not_disturb",
        icon="mdi:minus-circle",
    )


class VACADiagnosticsSwitch(BaseSwitch):
    """Entity to control diagnostics overlay on VACA satellite."""

    entity_description = SwitchEntityDescription(
        key="diagnostics_enabled",
        translation_key="diagnostics_enabled",
        icon="mdi:microphone-question",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    default_on = False


class VACAAlarmSwitch(BaseFeedbackSwitch):
    """Entity to control alarm for VACA satellite (Feedback powered)."""

    entity_description = SwitchEntityDescription(
        key="alarm",
        translation_key="alarm",
        icon="mdi:alarm-bell",
    )

    async def do_switch(self, value: bool, send_to_device: bool = True) -> None:
        """Perform the switch action."""
        self._attr_is_on = value
        self.async_write_ha_state()
        if send_to_device:
            self._device.send_custom_action(
                self.entity_description.key,
                {
                    "activate": self._attr_is_on,
                    "url": "",
                },
            )


class VACAScreenOnWakeWordSwitch(BaseSwitch):
    """Entity to control screen wake on wake word detection."""

    entity_description = SwitchEntityDescription(
        key="screen_on_wake_word",
        translation_key="screen_on_wake_word",
        icon="mdi:monitor-eye",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = True


class VACAScreenOnBumpSwitch(BaseSwitch):
    """Entity to control screen wake on bump detection."""

    entity_description = SwitchEntityDescription(
        key="screen_on_bump",
        translation_key="screen_on_bump",
        icon="mdi:gesture-tap",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class VACAScreenOnProximitySwitch(BaseSwitch):
    """Entity to control screen wake on proximity detection."""

    entity_description = SwitchEntityDescription(
        key="screen_on_proximity",
        translation_key="screen_on_proximity",
        icon="mdi:radar",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class VACAEnableMotionDetectionSwitch(BaseSwitch):
    """Entity to control motion detection status."""

    entity_description = SwitchEntityDescription(
        key="enable_motion_detection",
        translation_key="enable_motion_detection",
        icon="mdi:motion-sensor",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class VACAScreenOnMotionSwitch(BaseSwitch):
    """Entity to control screen wake on motion detection."""

    entity_description = SwitchEntityDescription(
        key="screen_on_motion",
        translation_key="screen_on_motion",
        icon="mdi:motion-sensor",
        entity_category=EntityCategory.CONFIG,
    )
    default_on = False


class VACAScreenSaverSwitch(BaseFeedbackSwitch):
    """Entity to control screen saver for VACA satellite (Feedback powered)."""

    entity_description = SwitchEntityDescription(
        key="screen_saver",
        translation_key="screen_saver",
        icon="mdi:monitor-shimmer",
    )
