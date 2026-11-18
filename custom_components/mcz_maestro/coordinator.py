"""Push coordinator bridging the MCZ cloud session and Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MaestroCloud, NotConnected
from .const import (
    CONF_MAC,
    CONF_OVERHEAT_TEMP,
    CONF_SAFETY_DELAY,
    CONF_SAFETY_NOTIFY,
    CONF_SAFETY_OVERHEAT,
    CONF_SAFETY_REVERT,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    CONF_SHUTDOWN_TEMP,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_URL,
    DOMAIN,
    EVENT_ALARM,
    EVENT_SAFETY,
    FIRST_FRAME_TIMEOUT,
    PARAMS_INTERVAL,
    SAFETY_DEFAULTS,
    STALE_AFTER,
)
from .protocol import MaestroState
from .safety import SafetyAction, SafetyConfig, SafetyGuard, SafetyResult

_LOGGER = logging.getLogger(__name__)

type MaestroConfigEntry = ConfigEntry[MaestroCoordinator]


def safety_options(options) -> dict:
    """Entry options with the safety defaults filled in."""
    return {**SAFETY_DEFAULTS, **options}


def safety_config(options) -> SafetyConfig:
    """Safety guard settings from the entry options."""
    opts = safety_options(options)
    return SafetyConfig(
        revert=bool(opts[CONF_SAFETY_REVERT]),
        delay=float(opts[CONF_SAFETY_DELAY]) * 60,
        overheat=bool(opts[CONF_SAFETY_OVERHEAT]),
        overheat_temp=float(opts[CONF_OVERHEAT_TEMP]),
        shutdown_temp=float(opts[CONF_SHUTDOWN_TEMP]),
    )


def _number(value: float | None) -> str:
    return "?" if value is None else f"{value:g}"


class MaestroCoordinator(DataUpdateCoordinator[MaestroState]):
    """Receives frames pushed by the cloud and asks for one every interval."""

    config_entry: MaestroConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MaestroConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.serial: str = entry.data[CONF_SERIAL]
        self.cloud = MaestroCloud(
            async_get_clientsession(hass),
            self.serial,
            entry.data[CONF_MAC],
            url=entry.data.get(CONF_URL, DEFAULT_URL),
            on_info=self._on_info,
            on_params=self._on_params,
            on_connection=self._on_connection,
        )
        self._first_frame = asyncio.Event()
        self._last_frame: float | None = None
        self._last_params_request: float | None = None
        self._last_alarm: int | None = None
        self._texts_cache: dict[tuple[str, str], dict[str, str]] = {}
        self.safety = SafetyGuard(safety_config(entry.options))
        self._safety_notify = bool(safety_options(entry.options)[CONF_SAFETY_NOTIFY])

    # ------------------------------------------------------------- lifecycle
    async def async_start(self) -> None:
        """Connect and wait for the first info frame."""
        await self.cloud.start()
        try:
            async with asyncio.timeout(FIRST_FRAME_TIMEOUT):
                await self._first_frame.wait()
        except TimeoutError as err:
            await self.cloud.stop()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="no_first_frame"
            ) from err
        self._last_params_request = self.hass.loop.time()

    async def async_stop(self) -> None:
        """Disconnect."""
        await self.cloud.stop()

    # ------------------------------------------------------------- callbacks
    @callback
    def _on_info(self, state: MaestroState) -> None:
        self._last_frame = self.hass.loop.time()
        self._first_frame.set()
        self._check_alarm(state)
        for result in self.safety.evaluate(state, self.hass.loop.time()):
            self.config_entry.async_create_background_task(
                self.hass, self._apply_safety(result), "mcz_maestro safety"
            )
        self.async_set_updated_data(state)

    @callback
    def _on_params(self, raw: str) -> None:
        _LOGGER.debug("Parameters frame received (%d fields)", raw.count("|"))

    @callback
    def _on_connection(self, up: bool) -> None:
        if up:
            _LOGGER.debug("MCZ cloud connected")
        else:
            _LOGGER.warning("MCZ cloud connection lost, reconnecting")
        self.async_update_listeners()

    @callback
    def _check_alarm(self, state: MaestroState) -> None:
        if not state.is_alarm:
            self._last_alarm = None
            return
        if state.state_code == self._last_alarm:
            return
        self._last_alarm = state.state_code
        _LOGGER.warning("Stove alarm: %s", state.alarm_label)
        self.config_entry.async_create_background_task(
            self.hass, self._fire_alarm(state), "mcz_maestro alarm event"
        )

    async def _texts(self, category: str) -> dict[str, str]:
        """Integration translations in Home Assistant's language (English fallback)."""
        key = (category, self.hass.config.language)
        if key not in self._texts_cache:
            self._texts_cache[key] = await async_get_translations(
                self.hass, key[1], category, {DOMAIN}
            )
        return self._texts_cache[key]

    async def _alarm_text(self, state: MaestroState) -> str:
        """Alarm label in Home Assistant's language (English when not translated)."""
        texts = await self._texts("entity")
        key = f"component.{DOMAIN}.entity.sensor.alarm.state.{state.alarm_key}"
        return texts.get(key) or state.alarm_label or ""

    async def _fire_alarm(self, state: MaestroState) -> None:
        device = dr.async_get(self.hass).async_get_device(
            identifiers={(DOMAIN, self.config_entry.entry_id)}
        )
        self.hass.bus.async_fire(
            EVENT_ALARM,
            {
                "device_id": device.id if device else None,
                "code": state.alarm_code,
                "state": state.state_key,
                "label": await self._alarm_text(state),
            },
        )

    # ------------------------------------------------------------- safety
    def _device_id(self) -> str | None:
        device = dr.async_get(self.hass).async_get_device(
            identifiers={(DOMAIN, self.config_entry.entry_id)}
        )
        return device.id if device else None

    async def _safety_texts(self, result: SafetyResult) -> tuple[str, str]:
        """(message, title) in Home Assistant's language."""
        texts = await self._texts("exceptions")
        cfg = self.safety.config
        limit = cfg.shutdown_temp if result.action is SafetyAction.SHUTDOWN else cfg.overheat_temp
        placeholders = {
            "minutes": _number(cfg.delay / 60),
            "temperature": _number(result.temperature),
            "limit": _number(limit),
        }

        def text(key: str) -> str:
            value = texts.get(f"component.{DOMAIN}.exceptions.{key}.message", key)
            for name, replacement in placeholders.items():
                value = value.replace("{" + name + "}", replacement)
            return value

        return text(f"safety_{result.action}"), text("safety_title")

    async def _apply_safety(self, result: SafetyResult) -> None:
        """Send the safety commands, then tell the user."""
        _LOGGER.warning(
            "Safety %s (room %s °C): %s", result.action, result.temperature, result.commands
        )
        try:
            for command in result.commands:
                await self.cloud.send(command)
        except NotConnected:
            _LOGGER.warning("Safety %s not applied: MCZ cloud offline, will retry", result.action)
            return
        message, title = await self._safety_texts(result)
        self.hass.bus.async_fire(
            EVENT_SAFETY,
            {
                "device_id": self._device_id(),
                "action": str(result.action),
                "label": message,
                "temperature": result.temperature,
            },
        )
        if self._safety_notify:
            persistent_notification.async_create(
                self.hass,
                message,
                title,
                notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_{result.action}",
            )

    def safety_restore_times(self) -> tuple[str | None, str | None]:
        """When Eco Stop / Dynamic will be restored (ISO, whole minutes), if pending."""
        now = dt_util.utcnow()

        def at(left: float | None) -> str | None:
            if left is None:
                return None
            moment = now + timedelta(seconds=left)
            if moment.second or moment.microsecond:
                moment = moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
            return moment.isoformat()

        eco, dynamic = self.safety.deadlines(self.hass.loop.time())
        return at(eco), at(dynamic)

    # ------------------------------------------------------------- polling
    @property
    def frame_age(self) -> float | None:
        """Seconds since the last info frame."""
        if self._last_frame is None:
            return None
        return self.hass.loop.time() - self._last_frame

    async def _async_update_data(self) -> MaestroState:
        age = self.frame_age
        if age is None or age > STALE_AFTER:
            self._request_quietly()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="stale",
                translation_placeholders={"seconds": str(int(age or 0))},
            )
        self._request_quietly()
        return self.data

    def _request_quietly(self) -> None:
        """Ask for fresh frames; the answer arrives through _on_info."""
        if not self.cloud.connected:
            return
        now = self.hass.loop.time()
        if self._last_params_request is None or now - self._last_params_request > PARAMS_INTERVAL:
            self._last_params_request = now
            self.config_entry.async_create_background_task(
                self.hass, self._safe(self.cloud.request_params()), "mcz_maestro params"
            )
        self.config_entry.async_create_background_task(
            self.hass, self._safe(self.cloud.request_info()), "mcz_maestro refresh"
        )

    @staticmethod
    async def _safe(coro) -> None:
        try:
            await coro
        except NotConnected:
            pass

    # ------------------------------------------------------------- commands
    async def async_send(self, command: str) -> None:
        """Send a command, as a Home Assistant error when offline."""
        try:
            await self.cloud.send(command)
        except NotConnected as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_connected"
            ) from err
