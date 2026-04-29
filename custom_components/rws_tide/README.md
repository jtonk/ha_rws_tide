# RWS Tide Forecast integration

Add to `configuration.yaml`:

```yaml
sensor:
  - platform: rws_tide
    name: "RWS Tide (Rotterdam)"
    latitude: 51.9244
    longitude: 4.4777
    parameter_code: WATHTE
```

The sensor state is the number of forecast points available in the next 48h.

Attributes include:
- `requested_location` (original lat/lon)
- `selected_datapoint` (nearest RWS point)
- `distance_km`
- `time_adjustment_minutes`
- `forecasts` (adjusted time series)
