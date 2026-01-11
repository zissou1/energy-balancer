# Roadmap

## Now
- Reduce coordinator update interval (evaluate 5 min vs 15 min) and confirm no slot-lag issues.
- Decide on MILP/optimization approach (solver availability vs analytic fallback).
- Keep chart attributes manageable (recorder exclusions or slimmer attributes).

## Next
- Add option to toggle price arrays on/off to avoid recorder warnings.
- Add diagnostics sensor/attributes (last price fetch time, last update time).
- Consider time-based refresh at slot boundaries instead of fixed interval.

## Later
- Optional: add multi-instance support (remove singleton config flow constraint).
- Optional: expose additional sensors (e.g., neutrality window sum).
- Improve docs and examples (ApexCharts config samples).
