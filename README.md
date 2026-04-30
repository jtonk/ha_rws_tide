# Rijkswaterstaat Tide Forecast for Home Assistant

Custom Home Assistant integration that fetches Rijkswaterstaat water level forecasts from the current RWS WaterWebservices API.

## Features

- Config flow support through Home Assistant UI
- Live station list loaded from the RWS catalog
- Water level forecast data exposed through a sensor
- HACS-compatible repository layout
- Optional legacy YAML platform support

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository with type `Integration`.
3. Install `Rijkswaterstaat Tide Forecast`.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/rws_tide` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration

### UI setup

1. Go to `Settings -> Devices & Services`.
2. Select `Add Integration`.
3. Search for `Rijkswaterstaat Tide Forecast`.
4. Fill in:
   - `Name`
   - `RWS location`
   - `Parameter code`
5. Save the integration.

The location list is loaded live from the current RWS catalog. By default the integration uses parameter code `WATHTE`.

After setup, you can change the name, location, and parameter code through the integration options dialog.

### YAML setup (legacy)

```yaml
sensor:
  - platform: rws_tide
    name: "RWS Tide (Scheveningen)"
    location_key: scheveningen
    parameter_code: WATHTE
```

## Sensor behavior

This integration creates a single sensor.

- The sensor state is the timestamp of the last successful refresh.
- Forecast values are stored in the sensor attributes.
- The integration refreshes every 24 hours.
- Each refresh requests a rolling window from 24 hours back to 48 hours ahead.

### Sensor attributes

- `requested_location`
- `selected_datapoint`
- `forecast_count`
- `forecasts`

`selected_datapoint` includes the resolved RWS station code, name, latitude, and longitude.

`forecasts` is a list of forecast records in this shape:

```json
[
  {
    "time": "2026-04-30T10:00:00+00:00",
    "value": 123
  }
]
```

## Notes

- The integration uses the live RWS metadata catalog to determine which stations support the selected parameter.
- If the configured location cannot be resolved during an update, the current code falls back to `Scheveningen` when available.
- This integration currently uses the `sensor` platform only.

## Development

Useful local files:

- [`custom_components/rws_tide/api.py`](/Users/jasper/Documents/Github/ha_rws_tide/custom_components/rws_tide/api.py)
- [`custom_components/rws_tide/config_flow.py`](/Users/jasper/Documents/Github/ha_rws_tide/custom_components/rws_tide/config_flow.py)
- [`custom_components/rws_tide/sensor.py`](/Users/jasper/Documents/Github/ha_rws_tide/custom_components/rws_tide/sensor.py)
