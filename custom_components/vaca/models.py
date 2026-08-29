"""Models for wyoming.

Copied here to fix issue in 2026.9.0 where the models were moved to homeassistant.components.wyoming and the import path changed, breaking this integration.
This file can be removed in 2026.12 when the minimum version of Home Assistant is 2026.9.0 or later.
"""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import WyomingInfoCoordinator
from .data import VAWyomingService
from .devices import SatelliteDevice


@dataclass
class DomainDataItem:
    """Domain data item."""

    service: VAWyomingService
    coordinator: WyomingInfoCoordinator
    device: SatelliteDevice | None = None


type WyomingConfigEntry = ConfigEntry[DomainDataItem]
