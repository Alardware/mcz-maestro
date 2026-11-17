"""Diagnostics: decoded state plus raw frames, serial and MAC removed."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_MAC, CONF_SERIAL
from .coordinator import MaestroConfigEntry

REDACTED = "**REDACTED**"
TO_REDACT = {CONF_SERIAL, CONF_MAC, "unique_id", "serial_number"}


def _jsonable(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MaestroConfigEntry
) -> dict[str, Any]:
    """Everything needed to map new parameters, without the stove's keys."""
    coordinator = entry.runtime_data
    cloud = coordinator.cloud
    state = coordinator.data
    decoded: dict[str, Any] | None = None
    if state is not None:
        decoded = asdict(state)
        decoded.pop("raw", None)
        decoded.update(
            state_key=state.state_key,
            is_on=state.is_on,
            is_heating=state.is_heating,
            alarm=state.alarm_label,
        )
    age = coordinator.frame_age
    data = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "cloud": {
            "connected": cloud.connected,
            **cloud.transport_info,
            "frame_age_s": None if age is None else round(age, 1),
        },
        "frames": {"info": cloud.last_info_raw, "params": cloud.last_params_raw},
        "state": decoded,
    }
    # Belt and braces: scrub the identifiers wherever they could appear.
    text = json.dumps(data, default=_jsonable)
    for secret in {coordinator.serial, entry.data[CONF_MAC]}:
        for variant in {secret, secret.lower()}:
            text = text.replace(variant, REDACTED)
    return json.loads(text)
