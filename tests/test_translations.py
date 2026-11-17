"""Every translation key used in code exists in English and French."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.mcz_maestro.binary_sensor import BINARY_SENSORS, PELLETS
from custom_components.mcz_maestro.button import BUTTONS
from custom_components.mcz_maestro.protocol import STATE_OPTIONS
from custom_components.mcz_maestro.sensor import ALARM_OPTIONS, SENSORS
from custom_components.mcz_maestro.switch import SWITCHES

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "mcz_maestro"


def _load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _keys(tree: dict, prefix: str = "") -> set[str]:
    out = set()
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        out |= _keys(value, path) if isinstance(value, dict) else {path}
    return out


@pytest.mark.parametrize("lang", ["strings.json", "translations/en.json", "translations/fr.json"])
def test_all_entity_keys_translated(lang) -> None:
    entity = _load(lang)["entity"]
    for desc in SENSORS:
        assert entity["sensor"][desc.translation_key]["name"], desc.key
    for desc in (*BINARY_SENSORS, PELLETS):
        assert entity["binary_sensor"][desc.translation_key]["name"]
    assert entity["binary_sensor"]["cloud"]["name"]
    for desc in SWITCHES:
        assert entity["switch"][desc.translation_key]["name"]
    for desc in BUTTONS:
        assert entity["button"][desc.translation_key]["name"]
    assert entity["fan"]["room_fan"]["name"]
    assert entity["select"]["power_level"]["name"]
    assert set(entity["climate"]["stove"]["state_attributes"]["preset_mode"]["state"]) == {"dynamic", "manual"}
    assert set(entity["sensor"]["state"]["state"]) == set(STATE_OPTIONS)
    assert set(entity["sensor"]["alarm"]["state"]) == set(ALARM_OPTIONS)


def test_french_matches_english_structure() -> None:
    assert _keys(_load("translations/fr.json")) == _keys(_load("translations/en.json"))
    assert _load("strings.json") == _load("translations/en.json")


def test_icons_reference_known_keys() -> None:
    icons = _load("icons.json")["entity"]
    strings = _load("strings.json")["entity"]
    for platform, entries in icons.items():
        for key in entries:
            if platform == "climate":
                continue
            assert key in strings[platform], f"{platform}.{key}"


def test_manifest() -> None:
    manifest = _load("manifest.json")
    assert list(manifest)[:2] == ["domain", "name"]
    rest = list(manifest)[2:]
    assert rest == sorted(rest)
    assert manifest["domain"] == "mcz_maestro"
    assert manifest["requirements"] == []
    assert manifest["iot_class"] == "cloud_push"
    for key in ("codeowners", "config_flow", "documentation", "issue_tracker", "version"):
        assert key in manifest
    card = (ROOT / "frontend" / "mcz-maestro-card.js").read_text(encoding="utf-8")
    assert f'const CARD_VERSION = "{manifest["version"]}"' in card
