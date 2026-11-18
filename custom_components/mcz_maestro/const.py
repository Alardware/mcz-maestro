"""Constants for the MCZ Maestro (legacy app) integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "mcz_maestro"
MANUFACTURER: Final = "MCZ"
MODEL: Final = "Maestro"

CONF_SERIAL: Final = "serial"
CONF_MAC: Final = "mac"
CONF_SCAN_INTERVAL: Final = "scan_interval"
# Internal override of the cloud URL (tests); never asked in the UI.
CONF_URL: Final = "url"

DEFAULT_NAME: Final = "Poêle"
DEFAULT_URL: Final = "http://app.mcz.it:9000"
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 15
MAX_SCAN_INTERVAL: Final = 300

# A frame older than this makes every entity unavailable.
STALE_AFTER: Final = 180
# How long the config flow waits for the stove to answer.
VALIDATE_TIMEOUT: Final = 20
# How long setup waits for the first info frame before retrying later.
FIRST_FRAME_TIMEOUT: Final = 30
# Parameters frame ("00") refresh period, kept raw for diagnostics.
PARAMS_INTERVAL: Final = 3600

EVENT_ALARM: Final = f"{DOMAIN}_alarm"
EVENT_SAFETY: Final = f"{DOMAIN}_safety"

# Safety options (see safety.py). Enabled by default.
CONF_SAFETY_REVERT: Final = "safety_revert"
CONF_SAFETY_DELAY: Final = "safety_delay"
CONF_SAFETY_OVERHEAT: Final = "safety_overheat"
CONF_OVERHEAT_TEMP: Final = "overheat_temp"
CONF_SHUTDOWN_TEMP: Final = "shutdown_temp"
CONF_SAFETY_NOTIFY: Final = "safety_notify"
DEFAULT_SAFETY_DELAY: Final = 60  # minutes
DEFAULT_OVERHEAT_TEMP: Final = 27.0
DEFAULT_SHUTDOWN_TEMP: Final = 30.0
SAFETY_DEFAULTS: Final = {
    CONF_SAFETY_REVERT: True,
    CONF_SAFETY_DELAY: DEFAULT_SAFETY_DELAY,
    CONF_SAFETY_OVERHEAT: True,
    CONF_OVERHEAT_TEMP: DEFAULT_OVERHEAT_TEMP,
    CONF_SHUTDOWN_TEMP: DEFAULT_SHUTDOWN_TEMP,
    CONF_SAFETY_NOTIFY: True,
}

CARD_URL: Final = f"/{DOMAIN}/mcz-maestro-card.js"
