from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import partial
from statistics import mean
import asyncio
from typing import Any
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    AREAS,
    CURRENCIES,
    CURRENCY_UNITS,
    CONF_AREA,
    CONF_CURRENCY,
    CONF_HORIZON_HOURS,
    CONF_INCLUDE_VAT,
    CONF_MAX_OFFSET,
    CONF_NIGHT_CAP,
    CONF_PRICE_ENTITY,
    CONF_STEP_SIZE,
    CONF_SMOOTHING_LEVEL,
    DEFAULT_AREA,
    DEFAULT_CURRENCY,
    DEFAULT_HORIZON_HOURS,
    DEFAULT_INCLUDE_VAT,
    DEFAULT_MAX_OFFSET,
    DEFAULT_NIGHT_CAP,
    DEFAULT_STEP_SIZE,
    DEFAULT_SMOOTHING_LEVEL,
    DOMAIN,
    VAT_BY_AREA,
)
from .helpers import (
    Point,
    clamp,
    infer_slot_ms,
    moving_average,
    normalize_raw_points,
    quantize_step,
)


class EnergyBalancerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=f"{DOMAIN}:{entry.entry_id}",
            update_interval=timedelta(minutes=1),
        )
        self.entry = entry
        self._tz = dt_util.get_time_zone("Europe/Stockholm")
        self._prices_today: list[Point] = []
        self._prices_tomorrow: list[Point] = []
        self._prices_today_date: date | None = None
        self._prices_tomorrow_date: date | None = None
        self._nordpool_entry_id: str | None = None
        self._daily_unsub = None
        self._midnight_unsub = None
        self._retry_unsub = None
        self.reload_from_entry(entry)

    def reload_from_entry(self, entry: ConfigEntry) -> None:
        self.price_entity: str = entry.data[CONF_PRICE_ENTITY]
        area = str(entry.data.get(CONF_AREA, DEFAULT_AREA)).upper()
        currency = str(entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)).upper()
        self.include_vat: bool = bool(entry.data.get(CONF_INCLUDE_VAT, DEFAULT_INCLUDE_VAT))
        if area not in AREAS:
            area = DEFAULT_AREA
        if currency not in CURRENCIES:
            currency = DEFAULT_CURRENCY
        self.area = area
        self.currency = currency
        self._nordpool_entry_id = None

        opts = entry.options or {}
        self.horizon_hours: int = int(opts.get(CONF_HORIZON_HOURS, entry.data.get(CONF_HORIZON_HOURS, DEFAULT_HORIZON_HOURS)))
        self.max_offset: float = float(opts.get(CONF_MAX_OFFSET, entry.data.get(CONF_MAX_OFFSET, DEFAULT_MAX_OFFSET)))
        self.night_cap: bool = bool(opts.get(CONF_NIGHT_CAP, entry.data.get(CONF_NIGHT_CAP, DEFAULT_NIGHT_CAP)))
        self.step_size: float = float(opts.get(CONF_STEP_SIZE, entry.data.get(CONF_STEP_SIZE, DEFAULT_STEP_SIZE)))
        self.smoothing_level: int = int(opts.get(CONF_SMOOTHING_LEVEL, entry.data.get(CONF_SMOOTHING_LEVEL, DEFAULT_SMOOTHING_LEVEL)))

        # derived smoothing window in slots (0..10 -> 1..(something))
        # 0 => no smoothing, 1..10 => 3..21 slots (odd windows)
        if self.smoothing_level <= 0:
            self.smoothing_slots = 1
        else:
            self.smoothing_slots = 1 + 2 * self.smoothing_level  # 3,5,7..21


    async def _async_update_data(self) -> dict[str, Any]:
        self._roll_prices_if_needed()

        prices_today = self._prices_today
        prices_tomorrow = self._prices_tomorrow
        prices_all = [*prices_today, *prices_tomorrow]
        if not prices_all:
            return self._empty()

        slot_ms = infer_slot_ms(prices_all)

        # Compute offsets for all known points using a rolling forward window (horizon_hours)
        horizon_slots = max(1, int(round((self.horizon_hours * 60 * 60 * 1000) / slot_ms)))

        offsets_all = self._compute_offsets(prices_all, horizon_slots)

        # Split back into today / tomorrow
        offsets_today = offsets_all[: len(prices_today)]
        offsets_tomorrow = offsets_all[len(prices_today) :]

        # Current offset for "now" slot
        now_ms = int(dt_util.utcnow().timestamp() * 1000)
        current_offset = 0.0
        current_price = None
        for p, o in zip(prices_all, offsets_all):
            if p.start_ts <= now_ms < p.end_ts:
                current_offset = float(o)
                current_price = float(p.value)
                break

        # Forecast attributes in ApexCharts-friendly format
        raw_today = [
            {
                "start_ts": p.start_ts,
                "end_ts": p.end_ts,
                "value": float(o),
            }
            for p, o in zip(prices_today, offsets_today)
        ]
        raw_tomorrow = [
            {
                "start_ts": p.start_ts,
                "end_ts": p.end_ts,
                "value": float(o),
            }
            for p, o in zip(prices_tomorrow, offsets_tomorrow)
        ]

        return {
            "slot_ms": slot_ms,
            "current_offset": float(current_offset),
            "current_price": current_price,
            "currency_unit": CURRENCY_UNITS.get(self.currency, self.currency),
            "offsets_today": raw_today,
            "offsets_tomorrow": raw_tomorrow,
            "prices_today": prices_today,
            "prices_tomorrow": prices_tomorrow,
        }

    def _empty(self) -> dict[str, Any]:
        return {
            "slot_ms": None,
            "current_offset": 0.0,
            "offsets_today": [],
            "offsets_tomorrow": [],
            "prices_today": [],
            "prices_tomorrow": [],
        }

    def _compute_offsets(self, prices: list[Point], horizon_slots: int) -> list[float]:
        n = len(prices)
        if n == 0:
            return []

        if self.max_offset <= 0:
            return [0.0] * n

        offsets: list[float] = [0.0] * n

        # Rolling forward window: for each slot i, compute avg within [i, i+horizon_slots)
        for i in range(n):
            window = prices[i : min(n, i + horizon_slots)]
            if len(window) < 2:
                offsets[i] = 0.0
                continue

            avg_price = mean([p.value for p in window])

            # diffs sum to 0 over the window by construction
            diffs = [avg_price - p.value for p in window]
            max_abs = max(abs(d) for d in diffs) if diffs else 0.0

            if max_abs <= 0:
                offsets[i] = 0.0
                continue

            k = self.max_offset / max_abs
            raw = k * (avg_price - prices[i].value)

            offsets[i] = clamp(raw, -self.max_offset, self.max_offset)

        # Optional smoothing (moving average) over offsets
        offsets = moving_average(offsets, self.smoothing_slots)

        # Keep within bounds after smoothing
        offsets = [clamp(o, -self.max_offset, self.max_offset) for o in offsets]

        # Apply step size snapping after smoothing and clamp again
        if self.step_size > 0:
            offsets = [quantize_step(o, self.step_size) for o in offsets]
            offsets = [clamp(o, -self.max_offset, self.max_offset) for o in offsets]

        # Optional night cap (22:30-05:00 Stockholm time)
        offsets = self._apply_night_cap(offsets, prices, horizon_slots)

        # Re-apply step size after night cap to keep consistent increments
        if self.step_size > 0:
            offsets = [quantize_step(o, self.step_size) for o in offsets]
            offsets = [clamp(o, -self.max_offset, self.max_offset) for o in offsets]
        return offsets

    async def async_start(self) -> None:
        self._schedule_next_tomorrow_fetch()
        self._schedule_midnight_roll()
        await self.async_refresh_prices(startup=True)

    async def async_refresh_prices(self, startup: bool = False) -> None:
        now_local = self._now_stockholm()
        today = now_local.date()

        if startup:
            startup_deadline = now_local + timedelta(minutes=2)
            await self._attempt_fetch_with_retry(today, startup_deadline, "today", retry_interval_seconds=10)
        else:
            await self._attempt_fetch_with_retry(today, now_local + timedelta(minutes=1), "today")

        if now_local.time() >= time(13, 30):
            tomorrow = today + timedelta(days=1)
            if startup:
                # On restart, always retry tomorrow for 1 minute if time is past release.
                await asyncio.sleep(5)
                await self._attempt_fetch_with_retry(
                    tomorrow,
                    now_local + timedelta(minutes=2),
                    "tomorrow",
                    retry_interval_seconds=10,
                )
                # After tomorrow succeeds, try today once more in case it missed earlier.
                await self._attempt_fetch_with_retry(
                    today,
                    now_local + timedelta(minutes=2),
                    "today",
                    retry_interval_seconds=10,
                )
                return

            deadline = datetime.combine(today, time(13, 40), tzinfo=self._tz)
            if now_local > deadline:
                await self._fetch_prices_for_date(tomorrow)
                return
            await self._attempt_fetch_with_retry(tomorrow, deadline, "tomorrow")

    def _roll_prices_if_needed(self) -> None:
        today = self._now_stockholm().date()
        if self._prices_today_date == today:
            return
        if self._prices_tomorrow_date == today:
            self._prices_today = self._prices_tomorrow
            self._prices_today_date = self._prices_tomorrow_date
            self._prices_tomorrow = []
            self._prices_tomorrow_date = None

    def _now_stockholm(self) -> datetime:
        return datetime.now(self._tz)

    def _next_stockholm_datetime(self, hour: int, minute: int, second: int) -> datetime:
        now = self._now_stockholm()
        target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        return target

    def _next_stockholm_time(self, hour: int, minute: int) -> datetime:
        now = self._now_stockholm()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        return target

    def _schedule_next_tomorrow_fetch(self) -> None:
        next_run = self._next_stockholm_time(13, 30)
        when_utc = dt_util.as_utc(next_run)
        if self._daily_unsub:
            self._daily_unsub()
        self._daily_unsub = async_track_point_in_time(self.hass, self._handle_tomorrow_fetch, when_utc)

    def _schedule_midnight_roll(self) -> None:
        next_run = self._next_stockholm_datetime(0, 0, 10)
        when_utc = dt_util.as_utc(next_run)
        if self._midnight_unsub:
            self._midnight_unsub()
        self._midnight_unsub = async_track_point_in_time(self.hass, self._handle_midnight_roll, when_utc)

    async def _handle_tomorrow_fetch(self, _now: datetime) -> None:
        today = self._now_stockholm().date()
        tomorrow = today + timedelta(days=1)
        deadline = datetime.combine(today, time(13, 40), tzinfo=self._tz)
        await self._attempt_fetch_with_retry(tomorrow, deadline, "tomorrow")
        self._schedule_next_tomorrow_fetch()

    async def _handle_midnight_roll(self, _now: datetime) -> None:
        self._roll_prices_if_needed()
        today = self._now_stockholm().date()
        if not self._prices_today:
            await self._attempt_fetch_with_retry(
                today,
                self._now_stockholm() + timedelta(minutes=1),
                "today",
                retry_interval_seconds=10,
            )
        await self.async_request_refresh()
        self._schedule_midnight_roll()

    def _schedule_retry(
        self,
        when_utc: datetime,
        target_date: date,
        deadline_local: datetime,
        label: str,
        retry_interval_seconds: int,
    ) -> None:
        if self._retry_unsub:
            self._retry_unsub()
        self._retry_unsub = async_track_point_in_time(
            self.hass,
            partial(self._handle_retry, target_date, deadline_local, label, retry_interval_seconds),
            when_utc,
        )

    async def _handle_retry(
        self,
        target_date: date,
        deadline_local: datetime,
        label: str,
        retry_interval_seconds: int,
        _now: datetime,
    ) -> None:
        await self._attempt_fetch_with_retry(target_date, deadline_local, label, retry_interval_seconds)

    async def _attempt_fetch_with_retry(
        self,
        target_date: date,
        deadline_local: datetime,
        label: str,
        retry_interval_seconds: int = 60,
    ) -> bool:
        ok = await self._fetch_prices_for_date(target_date)
        if ok:
            if self._retry_unsub:
                self._retry_unsub()
                self._retry_unsub = None
            await self.async_request_refresh()
            return True

        now_utc = dt_util.utcnow()
        deadline_utc = dt_util.as_utc(deadline_local)
        if now_utc < deadline_utc:
            self._schedule_retry(
                now_utc + timedelta(seconds=retry_interval_seconds),
                target_date,
                deadline_local,
                label,
                retry_interval_seconds,
            )
            return False

        self.logger.error(
            "Failed to fetch %s prices before %s",
            label,
            deadline_local.isoformat(),
        )
        return False

    async def _fetch_prices_for_date(self, asked_date: date) -> bool:
        if not self.hass.services.has_service("nordpool", "get_prices_for_date"):
            return False

        config_entry_id = self._get_nordpool_config_entry_id()
        if not config_entry_id:
            return False

        service_data = {
            "config_entry": config_entry_id,
            "date": asked_date,
            "areas": self.area,
            "currency": self.currency,
        }

        try:
            response = await self.hass.services.async_call(
                "nordpool",
                "get_prices_for_date",
                service_data,
                blocking=True,
                return_response=True,
            )
        except ServiceValidationError:
            return False
        except Exception:  # noqa: BLE001
            return False

        if not isinstance(response, dict):
            return False

        area_key = self.area.upper()
        points = normalize_raw_points(response.get(area_key))
        if points:
            vat_rate = VAT_BY_AREA.get(area_key, 0.0) if self.include_vat else 0.0
            points = [
                Point(
                    p.start_ts,
                    p.end_ts,
                    round((p.value / 1000.0) * (1.0 + vat_rate), 2),
                )
                for p in points
            ]
        if not points:
            return False

        today = self._now_stockholm().date()
        if asked_date == today:
            self._prices_today = points
            self._prices_today_date = asked_date
        else:
            self._prices_tomorrow = points
            self._prices_tomorrow_date = asked_date

        return True

    def _get_nordpool_config_entry_id(self) -> str | None:
        if self._nordpool_entry_id:
            return self._nordpool_entry_id

        registry = async_get_entity_registry(self.hass)
        entity = registry.async_get(self.price_entity)
        if entity is None or entity.config_entry_id is None:
            return None

        self._nordpool_entry_id = entity.config_entry_id
        return self._nordpool_entry_id

    async def async_set_max_offset(self, value: float) -> None:
        self.max_offset = float(value)
        await self.async_refresh()

    async def async_set_smoothing_level(self, value: int) -> None:
        self.smoothing_level = int(value)
        if self.smoothing_level <= 0:
            self.smoothing_slots = 1
        else:
            self.smoothing_slots = 1 + 2 * self.smoothing_level
        await self.async_refresh()

    async def async_set_step_size(self, value: float) -> None:
        self.step_size = float(value)
        await self.async_refresh()

    async def async_set_horizon_hours(self, value: int) -> None:
        self.horizon_hours = int(value)
        await self.async_refresh()

    async def async_set_night_cap(self, value: bool) -> None:
        self.night_cap = bool(value)
        await self.async_refresh()

    async def async_stop(self) -> None:
        """Stop any background timers/tasks created by this coordinator.

        DataUpdateCoordinator's own update_interval tracking is handled by HA,
        but if we add our own tasks later, we cancel them here.
        """
        # Example future-proofing:
        # if getattr(self, "_task", None):
        #     self._task.cancel()
        #     self._task = None
        if self._daily_unsub:
            self._daily_unsub()
            self._daily_unsub = None
        if self._midnight_unsub:
            self._midnight_unsub()
            self._midnight_unsub = None
        if self._retry_unsub:
            self._retry_unsub()
            self._retry_unsub = None
        return

    def _apply_night_cap(
        self,
        offsets: list[float],
        prices: list[Point],
        horizon_slots: int,
    ) -> list[float]:
        if not self.night_cap or not offsets:
            return offsets

        night_mask = [self._is_night_slot(p.start_ts) for p in prices]
        out = offsets[:]

        for i, is_night in enumerate(night_mask):
            if is_night and out[i] > 0:
                out[i] = 0.0

        # Rebalance overall sum to keep net energy neutral without per-window oscillations
        for _ in range(3):
            total = sum(out)
            if abs(total) < 1e-6:
                break
            adjustable = [
                j
                for j in range(len(out))
                if not night_mask[j] and -self.max_offset < out[j] < self.max_offset
            ]
            if not adjustable:
                break
            correction = total / len(adjustable)
            for j in adjustable:
                out[j] = clamp(out[j] - correction, -self.max_offset, self.max_offset)

        return out

    def _is_night_slot(self, start_ts_ms: int) -> bool:
        dt_local = datetime.fromtimestamp(start_ts_ms / 1000.0, tz=dt_util.UTC).astimezone(self._tz)
        t = dt_local.time()
        return t >= time(22, 30) or t < time(5, 0)

