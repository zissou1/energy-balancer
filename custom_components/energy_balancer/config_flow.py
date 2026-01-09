from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    AREAS,
    CURRENCIES,
    CONF_AREA,
    CONF_CURRENCY,
    CONF_HORIZON_HOURS,
    CONF_INCLUDE_VAT,
    CONF_PRICE_ENTITY,
    DEFAULT_AREA,
    DEFAULT_CURRENCY,
    DEFAULT_INCLUDE_VAT,
    DOMAIN,
)


class EnergyBalancerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # One instance is enough for now; if you want multiple instances later,
            # remove this unique_id constraint and allow multiple entries.
            await self.async_set_unique_id("energy_balancer_singleton")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Energy Balancer",
                data=user_input,
                options={},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_PRICE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_AREA, default=DEFAULT_AREA): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=AREAS)
                ),
                vol.Required(CONF_CURRENCY, default=DEFAULT_CURRENCY): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=CURRENCIES)
                ),
                vol.Optional(CONF_INCLUDE_VAT, default=DEFAULT_INCLUDE_VAT): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return EnergyBalancerOptionsFlow(config_entry)


class EnergyBalancerOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            new_data = dict(self.entry.data)
            new_data[CONF_PRICE_ENTITY] = user_input[CONF_PRICE_ENTITY]
            new_data[CONF_AREA] = user_input[CONF_AREA]
            new_data[CONF_CURRENCY] = user_input[CONF_CURRENCY]
            new_data[CONF_INCLUDE_VAT] = user_input.get(CONF_INCLUDE_VAT, DEFAULT_INCLUDE_VAT)
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

            return self.async_create_entry(title="", data=dict(self.entry.options or {}))

        schema = vol.Schema(
            {
                vol.Required(CONF_PRICE_ENTITY, default=self.entry.data.get(CONF_PRICE_ENTITY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_AREA, default=self.entry.data.get(CONF_AREA, DEFAULT_AREA)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=AREAS)
                ),
                vol.Required(CONF_CURRENCY, default=self.entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=CURRENCIES)
                ),
                vol.Optional(CONF_INCLUDE_VAT, default=self.entry.data.get(CONF_INCLUDE_VAT, DEFAULT_INCLUDE_VAT)): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
