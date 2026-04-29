"""Constants for the RWS Tide integration."""

DOMAIN = "rws_tide"
DEFAULT_NAME = "RWS Tide Forecast"
DEFAULT_PARAMETER_CODE = "WATHTE"
DEFAULT_METADATA_URL = (
    "https://waterwebservices.rijkswaterstaat.nl/METADATASERVICES_DBO/OphalenCatalogus"
)
DEFAULT_FORECAST_URL = (
    "https://waterwebservices.rijkswaterstaat.nl/ONLINEWAARNEMINGENSERVICES_DBO/OphalenVerwachtingen"
)
TIDE_SPEED_M_S = 12.0

CONF_PARAMETER_CODE = "parameter_code"
CONF_METADATA_URL = "metadata_url"
CONF_FORECAST_URL = "forecast_url"
