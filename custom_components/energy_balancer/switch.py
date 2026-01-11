from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NIGHT_CAP, DATA_COORDINATOR, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([EnergyBalancerNightCapSwitch(entry, coordinator)], update_before_add=True)


class EnergyBalancerNightCapSwitch(CoordinatorEntity, SwitchEntity):
    _attr_name = "Energy Balancer Night Cap"
    _attr_unique_id = "energy_balancer_night_cap"

    def __init__(self, entry, coordinator):
        super().__init__(coordinator)
        self.entry = entry

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.night_cap)

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set_value(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set_value(False)

    async def _async_set_value(self, value: bool) -> None:
        new_options = dict(self.entry.options or {})
        new_options[CONF_NIGHT_CAP] = bool(value)
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.coordinator.async_set_night_cap(bool(value))
