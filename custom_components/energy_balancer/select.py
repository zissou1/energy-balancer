from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STEP_SIZE, DATA_COORDINATOR, DOMAIN, DEFAULT_STEP_SIZE


STEP_SIZE_OPTIONS = ["0.1", "0.5", "1.0"]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([EnergyBalancerStepSizeSelect(entry, coordinator)], update_before_add=True)


class EnergyBalancerStepSizeSelect(CoordinatorEntity, SelectEntity):
    _attr_name = "Energy Balancer Step Size"
    _attr_unique_id = "energy_balancer_step_size"
    _attr_icon = "mdi:stairs"
    _attr_options = STEP_SIZE_OPTIONS

    def __init__(self, entry, coordinator):
        super().__init__(coordinator)
        self.entry = entry

    @property
    def current_option(self):
        value = float(getattr(self.coordinator, "step_size", DEFAULT_STEP_SIZE))
        return _format_step_size(value)

    async def async_select_option(self, option: str) -> None:
        if option not in STEP_SIZE_OPTIONS:
            return
        value = float(option)

        new_options = dict(self.entry.options or {})
        new_options[CONF_STEP_SIZE] = value
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)

        await self.coordinator.async_set_step_size(value)


def _format_step_size(value: float) -> str:
    if value >= 0.75:
        return "1.0"
    if value >= 0.3:
        return "0.5"
    return "0.1"
