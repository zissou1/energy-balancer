# Energy Balancer (Home Assistant Custom Integration)

Energy Balancer computes a temperature offset for a heating system based on electricity price variations while keeping total energy neutral over a rolling window. The offset is positive when prices are low (pre-heating) and negative when prices are high (letting temperature float down).

This integration is GUI-only and uses a Nordpool sensor to locate the Nordpool config entry, then calls the Nordpool service to fetch price data.

## Features

- Computes a current offset and an offset forecast for today/tomorrow
- Energy-neutral rolling window with optional smoothing
- Step-size snapping (e.g., 0.1 / 0.5 / 1.0)
- Daily fetch of tomorrow prices at 13:30 Stockholm time
- Midnight roll-over to avoid gaps
- Optional VAT inclusion per area

## Requirements

- Home Assistant
- Nordpool integration installed and configured

## Installation

1. Copy `custom_components/energy_balancer` into your HA `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via the UI (Settings -> Devices & Services -> Add Integration -> Energy Balancer).

## Configuration (UI)

Required:
- Nordpool sensor entity
- Area (e.g., SE1)
- Currency (e.g., SEK)
- Include VAT (checkbox)

## Entities

Sensors:
- `sensor.energy_balancer_offset`
  - State: current offset (degC)
  - Attributes:
    - `slot_ms`
    - `raw_today` / `raw_tomorrow` (offset forecast)
- `sensor.energy_balancer_prices`
  - State: current price
  - Attributes:
    - `slot_ms`
    - `raw_today` / `raw_tomorrow` (price forecast)

Helpers:
- `number.energy_balancer_max_offset` (degC)
- `number.energy_balancer_horizon_hours` (hours)
- `number.energy_balancer_smoothing_level` (0-10)
- `select.energy_balancer_step_size` (0.1 / 0.5 / 1.0)

## Scheduling and Data Flow

- On startup, the integration immediately fetches today prices and retries every 10 seconds for up to 1 minute if needed.
- At 13:30 Stockholm time, it fetches tomorrow prices (retrying until 13:40).
- At 00:00:10 Stockholm time, tomorrow data is rolled into today (and a fetch is attempted if missing).

## VAT

When "Include VAT" is enabled, prices are multiplied by `(1 + VAT)` for the selected area. VAT is applied after the internal `/10` scaling.

Configured VAT rates include:
- AT 20%, BE 21%, BG 20%, DK1/DK2 25%, EE 24%, FI 25.5%, FR 20%, GER 19%, LT 21%, LV 21%, NL 21%, PL 23%, NO1-5 25%, SE1-4 25%

## Recorder note

The forecast arrays can be large. If you see recorder warnings, you can exclude the price/offset sensors from the recorder database.

## Development notes

- The integration calls the Nordpool service `nordpool.get_prices_for_date` using the Nordpool config entry ID.
- Prices are normalized to the internal format with timestamps in epoch ms.

## License

MIT (or update if you use a different license)
