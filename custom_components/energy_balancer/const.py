from __future__ import annotations

DOMAIN = "energy_balancer"

PLATFORMS: list[str] = ["sensor", "number", "select"]

CONF_PRICE_ENTITY = "Price Entity"
CONF_AREA = "area"
CONF_INCLUDE_VAT = "Include VAT"
CONF_CURRENCY = "currency"
CONF_HORIZON_HOURS = "horizon_hours"
CONF_MAX_OFFSET = "max_offset"
CONF_STEP_SIZE = "step_size"
CONF_SMOOTHING_LEVEL = "smoothing_level"

AREAS = [
    "EE",
    "LT",
    "LV",
    "AT",
    "BE",
    "BG",
    "FR",
    "GER",
    "NL",
    "PL",
    "DK1",
    "DK2",
    "FI",
    "NO1",
    "NO2",
    "NO3",
    "NO4",
    "NO5",
    "SE1",
    "SE2",
    "SE3",
    "SE4",
    "SYS",
    "TEL",
]
CURRENCIES = ["DKK", "EUR", "NOK", "PLN", "SEK"]

DEFAULT_HORIZON_HOURS = 12
DEFAULT_MAX_OFFSET = 1.0
DEFAULT_STEP_SIZE = 0.1
DEFAULT_SMOOTHING_LEVEL = 1  # 0..10
DEFAULT_AREA = "SE1"
DEFAULT_CURRENCY = "SEK"
DEFAULT_INCLUDE_VAT = False

VAT_BY_AREA = {
    "AT": 0.20,
    "BE": 0.21,
    "BG": 0.20,
    "DK1": 0.25,
    "DK2": 0.25,
    "EE": 0.24,
    "FI": 0.255,
    "FR": 0.20,
    "GER": 0.19,
    "LT": 0.21,
    "LV": 0.21,
    "NL": 0.21,
    "PL": 0.23,
    "NO1": 0.25,
    "NO2": 0.25,
    "NO3": 0.25,
    "NO4": 0.25,
    "NO5": 0.25,
    "SE1": 0.25,
    "SE2": 0.25,
    "SE3": 0.25,
    "SE4": 0.25,
}

# Coordinator key
DATA_COORDINATOR = "coordinator"
