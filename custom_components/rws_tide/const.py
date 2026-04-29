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
DEFAULT_LOCATION_KEY = "scheveningen"

KNOWN_RWS_LOCATIONS = {
    "borssele": "Borssele",
    "den_helder": "Den Helder",
    "harlingen": "Harlingen",
    "hoek_van_holland": "Hoek van Holland",
    "ijmuiden": "IJmuiden",
    "katwijk": "Katwijk",
    "laukwersoog": "Lauwersoog",
    "nes": "Nes",
    "scheveningen": "Scheveningen",
    "terneuzen": "Terneuzen",
    "vlissingen": "Vlissingen",
}

CONF_PARAMETER_CODE = "parameter_code"
CONF_METADATA_URL = "metadata_url"
CONF_FORECAST_URL = "forecast_url"
CONF_LOCATION_KEY = "location_key"
