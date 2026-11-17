"""Config, options and reconfigure flows."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mcz_maestro.api import stove_id
from custom_components.mcz_maestro.const import (
    CONF_MAC,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

SERIAL = "1234567890123"
MAC = "0A1B2C3D4E5F"
USER_INPUT = {CONF_NAME: "Poêle", CONF_SERIAL: SERIAL, CONF_MAC: "0a:1b:2c:3d:4e:5f"}


@pytest.fixture(autouse=True)
def no_setup():
    with patch("custom_components.mcz_maestro.async_setup_entry", return_value=True) as mock:
        yield mock


def _url(url: str):
    return patch("custom_components.mcz_maestro.config_flow.DEFAULT_URL", url)


async def test_user_flow_success(hass: HomeAssistant, fake_cloud) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with _url(fake_cloud.url):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Poêle"
    assert result["data"] == {CONF_SERIAL: SERIAL, CONF_MAC: MAC}
    assert result["result"].unique_id == stove_id(SERIAL)
    assert SERIAL not in result["result"].unique_id
    assert fake_cloud.joins[0] == {"serialNumber": SERIAL, "macAddress": MAC, "type": "Android-App"}


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [(CONF_SERIAL, "123", "invalid_serial"), (CONF_MAC, "0A1B2C", "invalid_mac")],
)
async def test_user_flow_invalid_input(hass: HomeAssistant, field, value, error) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, field: value}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}


async def test_user_flow_cannot_connect_then_recovers(
    hass: HomeAssistant, dead_url, fake_cloud
) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    with _url(dead_url):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}
    with _url(fake_cloud.url):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_no_response(hass: HomeAssistant, fake_cloud_factory) -> None:
    cloud = await fake_cloud_factory(respond=False)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    with (
        _url(cloud.url),
        patch("custom_components.mcz_maestro.config_flow.VALIDATE_TIMEOUT", 0.5),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "no_response"}


async def test_user_flow_unexpected_error(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    with patch(
        "custom_components.mcz_maestro.config_flow.async_validate", side_effect=RuntimeError
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=stove_id(SERIAL), data={CONF_SERIAL: SERIAL, CONF_MAC: MAC}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=stove_id(SERIAL), data={CONF_SERIAL: SERIAL, CONF_MAC: MAC})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_INTERVAL: 60}


async def test_options_flow_rejects_out_of_range(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=stove_id(SERIAL), data={CONF_SERIAL: SERIAL, CONF_MAC: MAC})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: 5})


async def test_reconfigure_mac(hass: HomeAssistant, fake_cloud) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=stove_id(SERIAL), title="Poêle", data={CONF_SERIAL: SERIAL, CONF_MAC: "000000000000"}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    with _url(fake_cloud.url):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_MAC: "0A-1B-2C-3D-4E-5F"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_MAC] == MAC


async def test_reconfigure_invalid_mac(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=stove_id(SERIAL), data={CONF_SERIAL: SERIAL, CONF_MAC: MAC})
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MAC: "zz"})
    assert result["errors"] == {CONF_MAC: "invalid_mac"}
