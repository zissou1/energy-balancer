from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HORIZON_HOURS,
    CONF_MAX_OFFSET,
    CONF_SMOOTHING_LEVEL,
    DATA_COORDINATOR,
    DOMAIN,
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            EnergyBalancerHorizonHoursNumber(entry, coordinator),
            EnergyBalancerMaxOffsetNumber(entry, coordinator),
            EnergyBalancerSmoothingLevelNumber(entry, coordinator),
        ],
        update_before_add=True,
    )


class EnergyBalancerMaxOffsetNumber(CoordinatorEntity, NumberEntity):
    _attr_name = "Energy Balancer Max Offset"
    _attr_unique_id = "energy_balancer_max_offset"
    _attr_icon = "mdi:arrow-expand-vertical"
    _attr_native_unit_of_measurement = "°C"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 5.0
    _attr_native_step = 0.5
    _attr_mode = "slider"

    def __init__(self, entry, coordinator):
        super().__init__(coordinator)
        self.entry = entry

    @property
    def native_value(self):
        return float(self.coordinator.max_offset)

    async def async_set_native_value(self, value: float) -> None:
        # Persist into options so it survives restarts
        new_options = dict(self.entry.options or {})
        new_options[CONF_MAX_OFFSET] = float(value)
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)

        await self.coordinator.async_set_max_offset(float(value))


class EnergyBalancerHorizonHoursNumber(CoordinatorEntity, NumberEntity):
    _attr_name = "Energy Balancer Horizon Hours"
    _attr_unique_id = "energy_balancer_horizon_hours"
    _attr_icon = "mdi:arrow-collapse-right"
    _attr_native_unit_of_measurement = "h"
    _attr_native_min_value = 1
    _attr_native_max_value = 24
    _attr_native_step = 1
    _attr_mode = "slider"

    def __init__(self, entry, coordinator):
        super().__init__(coordinator)
        self.entry = entry

    @property
    def native_value(self):
        return int(self.coordinator.horizon_hours)

    async def async_set_native_value(self, value: float) -> None:
        new_options = dict(self.entry.options or {})
        new_options[CONF_HORIZON_HOURS] = int(value)
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)

        await self.coordinator.async_set_horizon_hours(int(value))


class EnergyBalancerSmoothingLevelNumber(CoordinatorEntity, NumberEntity):
    _attr_name = "Energy Balancer Smoothing Level"
    _attr_unique_id = "energy_balancer_smoothing_level"
    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = "slider"

    def __init__(self, entry, coordinator):
        super().__init__(coordinator)
        self.entry = entry

    @property
    def native_value(self):
        return int(self.coordinator.smoothing_level)

    async def async_set_native_value(self, value: float) -> None:
        new_options = dict(self.entry.options or {})
        new_options[CONF_SMOOTHING_LEVEL] = int(value)
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)

        await self.coordinator.async_set_smoothing_level(int(value))
