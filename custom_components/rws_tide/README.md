# RWS Tide Forecast integration

Home Assistant custom integration that fetches Rijkswaterstaat water level forecasts from the current RWS WaterWebservices API.

## HACS installation

1. In HACS, add this repository as a **Custom repository** of type **Integration**.
2. Install **RWS Tide Forecast**.
3. Restart Home Assistant.

## UI setup (recommended)

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **RWS Tide Forecast**.
3. Fill in:
   - Name
   - RWS location
   - Parameter code (default: `WATHTE`)
4. Save.

The location list is loaded live from the RWS catalog and only shows stations that currently expose `WATHTE` forecasts.

You can edit name, location, and parameter later via **Configure**.

## YAML setup (legacy)

```yaml
sensor:
  - platform: rws_tide
    name: "RWS Tide (Scheveningen)"
    location_key: scheveningen
    parameter_code: WATHTE
```

## Entity behavior

The sensor state is the timestamp of the last successful fetch.

Attributes:
- `requested_location`
- `selected_datapoint`
- `forecast_count`
- `forecasts`

The integration refreshes on startup or reload, then every 24 hours after that.
Each fetch requests a rolling window covering the last 24 hours and the next 48 hours.

## Troubleshooting: test the current RWS catalog

If you want to validate the upstream RWS response, run this POST from a machine that has direct internet access:

```bash
curl -sS \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: HomeAssistant-rws_tide' \
  -H 'X-API-KEY: HomeAssistant-rws_tide' \
  -X POST 'https://ddapi20-waterwebservices.rijkswaterstaat.nl/METADATASERVICES/OphalenCatalogus' \
  --data '{"CatalogusFilter":{"Compartimenten":true,"Grootheden":true,"ProcesTypes":true}}' > /tmp/rws_catalog.json
```

For a forecast fetch, use:

```bash
curl -sS \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: HomeAssistant-rws_tide' \
  -H 'X-API-KEY: HomeAssistant-rws_tide' \
  -X POST 'https://ddapi20-waterwebservices.rijkswaterstaat.nl/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen' \
  --data '{"Locatie":{"Code":"scheveningen"},"AquoPlusWaarnemingMetadata":{"AquoMetadata":{"Compartiment":{"Code":"OW"},"Grootheid":{"Code":"WATHTE"},"ProcesType":"verwachting"}},"Periode":{"Begindatumtijd":"2026-04-30T00:00:00.000+02:00","Einddatumtijd":"2026-05-02T23:59:59.000+02:00"}}'
```
