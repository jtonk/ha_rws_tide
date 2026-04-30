"""Constants for the RWS Tide integration."""

DOMAIN = "rws_tide"
DEFAULT_NAME = "RWS Tide Forecast"
DEFAULT_PARAMETER_CODE = "WATHTE"
DEFAULT_METADATA_URL = (
    "https://ddapi20-waterwebservices.rijkswaterstaat.nl/METADATASERVICES/OphalenCatalogus"
)
DEFAULT_FORECAST_URL = (
    "https://ddapi20-waterwebservices.rijkswaterstaat.nl/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"
)
DEFAULT_LOCATION_KEY = "scheveningen"

CONF_PARAMETER_CODE = "parameter_code"
CONF_METADATA_URL = "metadata_url"
CONF_FORECAST_URL = "forecast_url"
CONF_LOCATION_KEY = "location_key"
