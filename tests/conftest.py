"""Shared fixtures for the MCZ Maestro tests."""

from __future__ import annotations

import pytest

# Values read on a real stove's "Info" screen (17/11/2026 05:50).
REFERENCE_VALUES: dict[int, int] = {
    1: 15,  # state: power 5
    2: 6,  # room fan: auto
    5: 120,  # fumes °C
    6: 36,  # ambient 18.0 °C (x2)
    10: 0,  # igniter off
    11: 160,  # Active set
    12: 1886,  # fumes fan rpm
    13: 1400,  # auger rpm set
    14: 1350,  # auger rpm live
    17: 0,  # brazier OK
    18: 11,  # profile (raw)
    20: 1,  # Active mode
    21: 166,  # Active live
    22: 1,  # Dynamic
    23: 1,  # Eco
    24: 0,  # silent
    25: 1,  # chrono
    26: 38,  # setpoint 19.0 °C (x2)
    28: 46,  # motherboard 23.0 °C (x2)
    29: 15,  # power 5
    30: 181,  # firmware raw
    32: 5,  # hour
    33: 50,  # minute
    34: 17,  # day
    35: 11,  # month
    36: 2026,  # year
    37: 18_000 * 3600,  # total operating time (s)
    38: 1_000 * 3600,
    39: 2_000 * 3600,
    40: 3_000 * 3600,
    41: 4_000 * 3600,
    42: 8_000 * 3600,
    43: 660,  # hours before service
    44: 0,
    45: 1234,  # ignitions
    46: 0,
    47: 0,  # no pellet sensor
    49: 1,  # sounds
    51: 0,  # winter
    60: 0,  # antifreeze raw
}


def build_info_frame(overrides: dict[int, int] | None = None, length: int = 61) -> str:
    """Build a "01|..." info frame, every field hex encoded like the stove does."""
    values = dict(REFERENCE_VALUES)
    if overrides:
        values.update(overrides)
    fields = ["01"]
    for idx in range(1, length):
        fields.append(format(values.get(idx, 0), "x"))
    return "|".join(fields)


REFERENCE_FRAME = build_info_frame()
PARAMS_FRAME = "00|" + "|".join(format(i, "x") for i in range(1, 80))


@pytest.fixture
def reference_frame() -> str:
    """Info frame matching the stove's Info screen."""
    return REFERENCE_FRAME
