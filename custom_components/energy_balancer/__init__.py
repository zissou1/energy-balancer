from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import EnergyBalancerCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _LOGGER.debug("async_setup called")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("async_setup_entry START entry_id=%s", entry.entry_id)

    coordinator = EnergyBalancerCoordinator(hass, entry)
    await coordinator.async_start()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("async_setup_entry DONE entry_id=%s", entry.entry_id)
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    _LOGGER.debug("update_listener called entry_id=%s", entry.entry_id)
    coordinator: EnergyBalancerCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    coordinator.reload_from_entry(entry)
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("async_unload_entry START entry_id=%s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: EnergyBalancerCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        await coordinator.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    _LOGGER.debug("async_unload_entry DONE entry_id=%s ok=%s", entry.entry_id, unload_ok)
    return unload_ok
