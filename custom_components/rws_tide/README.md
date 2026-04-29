# RWS Tide Forecast integration

Home Assistant custom integration that fetches Rijkswaterstaat tide forecasts and shifts time based on your distance to the nearest RWS measurement point.

## HACS installation

1. In HACS, add this repository as a **Custom repository** of type **Integration**.
2. Install **RWS Tide Forecast**.
3. Restart Home Assistant.

## UI setup (recommended)

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **RWS Tide Forecast**.
3. Fill in:
   - Name
   - Latitude / Longitude (defaults to Home Assistant location)
   - Parameter code (default: `WATHTE`)
4. Save.

You can edit name/location/parameter later via **Configure**.

## YAML setup (legacy)

```yaml
sensor:
  - platform: rws_tide
    name: "RWS Tide (Rotterdam)"
    latitude: 51.9244
    longitude: 4.4777
    parameter_code: WATHTE
```

## Entity behavior

The sensor state is the number of forecast points available in the next 48 hours.

Attributes:
- `requested_location`
- `selected_datapoint`
- `distance_km`
- `time_adjustment_minutes`
- `forecasts`
