"""Constants for the MCZ Maestro (legacy app) integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "mcz_maestro"
MANUFACTURER: Final = "MCZ"
MODEL: Final = "Maestro"

CONF_SERIAL: Final = "serial"
CONF_MAC: Final = "mac"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_NAME: Final = "Poêle"
DEFAULT_URL: Final = "http://app.mcz.it:9000"
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 15
MAX_SCAN_INTERVAL: Final = 300

# A frame older than this makes every entity unavailable.
STALE_AFTER: Final = 180
# How long setup waits for the first info frame before retrying later.
FIRST_FRAME_TIMEOUT: Final = 30
# Parameters frame ("00") refresh period, kept raw for diagnostics.
PARAMS_INTERVAL: Final = 3600

EVENT_ALARM: Final = f"{DOMAIN}_alarm"

CARD_URL: Final = f"/{DOMAIN}/mcz-maestro-card.js"
