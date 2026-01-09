from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_COORDINATOR


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            EnergyBalancerOffsetSensor(coordinator),
            EnergyBalancerPricesSensor(coordinator),
        ],
        update_before_add=True,
    )


class EnergyBalancerOffsetSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Energy Balancer Offset"
    _attr_unique_id = "energy_balancer_offset"
    _attr_icon = "mdi:delta"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def native_value(self):
        return float((self.coordinator.data or {}).get("current_offset", 0.0))

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "slot_ms": data.get("slot_ms"),
            "raw_today": data.get("offsets_today", []),
            "raw_tomorrow": data.get("offsets_tomorrow", []),
        }


class EnergyBalancerPricesSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Energy Balancer Prices"
    _attr_unique_id = "energy_balancer_prices"
    _attr_icon = "mdi:currency-eur"
    _attr_native_unit_of_measurement = "ore"

    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("current_price")

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        prices_today = [
            {
                "start_ts": p.start_ts,
                "end_ts": p.end_ts,
                "value": float(p.value),
            }
            for p in data.get("prices_today", [])
        ]
        prices_tomorrow = [
            {
                "start_ts": p.start_ts,
                "end_ts": p.end_ts,
                "value": float(p.value),
            }
            for p in data.get("prices_tomorrow", [])
        ]
        return {
            "slot_ms": data.get("slot_ms"),
            "raw_today": prices_today,
            "raw_tomorrow": prices_tomorrow,
        }
