"""Safety guard: brings the stove back to a safe configuration.

Pure logic (no network, no Home Assistant). Fed with every info frame and a
monotonic clock, it returns the commands to send:

- Eco Stop off for longer than the delay      -> Eco Stop back on
- Manual mode for longer than the delay       -> back to Dynamic
- Room at or above the overheat limit         -> Eco Stop + Dynamic at once
- Room at or above the shutdown limit         -> stove switched off

A command is never repeated before RETRY_AFTER seconds, so a stove that does not
obey (or reports late) is not flooded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .protocol import MaestroState, cmd_dynamic, cmd_eco, cmd_power

RETRY_AFTER = 300.0


class SafetyAction(StrEnum):
    """What the guard did (also the event/notification key)."""

    ECO_RESTORED = "eco_restored"
    DYNAMIC_RESTORED = "dynamic_restored"
    OVERHEAT = "overheat"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class SafetyConfig:
    """User settings. delay in seconds, temperatures in °C."""

    revert: bool
    delay: float
    overheat: bool
    overheat_temp: float
    shutdown_temp: float


@dataclass(frozen=True, slots=True)
class SafetyResult:
    """One intervention: why, and the commands to send."""

    action: SafetyAction
    commands: list[str]
    temperature: float | None = None


class SafetyGuard:
    """Tracks how long risky modes last and decides when to step in."""

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config
        self._eco_off_since: float | None = None
        self._manual_since: float | None = None
        self._last_action: dict[SafetyAction, float] = {}

    # ------------------------------------------------------------- tracking
    @staticmethod
    def _track(since: float | None, risky: bool | None, now: float) -> float | None:
        if not risky:
            return None
        return now if since is None else since

    def _cooled_down(self, action: SafetyAction, now: float) -> bool:
        last = self._last_action.get(action)
        return last is None or now - last >= RETRY_AFTER

    def deadlines(self, now: float) -> tuple[float | None, float | None]:
        """Seconds left before Eco Stop / Dynamic are restored (None: nothing pending)."""
        if not self.config.revert:
            return None, None

        def left(since: float | None) -> float | None:
            return None if since is None else max(0.0, since + self.config.delay - now)

        return left(self._eco_off_since), left(self._manual_since)

    # ------------------------------------------------------------- decide
    def evaluate(self, state: MaestroState, now: float) -> list[SafetyResult]:
        """Return the interventions needed for this frame."""
        cfg = self.config
        eco_off = None if state.eco is None else not state.eco
        manual = None if state.dynamic is None else not state.dynamic
        self._eco_off_since = self._track(self._eco_off_since, eco_off, now)
        self._manual_since = self._track(self._manual_since, manual, now)

        results: list[SafetyResult] = []
        sent: set[str] = set()
        room = state.ambient_temp

        if cfg.overheat and room is not None and state.is_on:
            if room >= cfg.shutdown_temp:
                if self._cooled_down(SafetyAction.SHUTDOWN, now):
                    self._last_action[SafetyAction.SHUTDOWN] = now
                    results.append(SafetyResult(SafetyAction.SHUTDOWN, [cmd_power(False)], room))
                return results
            if room >= cfg.overheat_temp and self._cooled_down(SafetyAction.OVERHEAT, now):
                commands = []
                if eco_off:
                    commands.append(cmd_eco(True))
                if manual:
                    commands.append(cmd_dynamic(True))
                if commands:
                    self._last_action[SafetyAction.OVERHEAT] = now
                    sent.update(commands)
                    results.append(SafetyResult(SafetyAction.OVERHEAT, commands, room))

        if cfg.revert:
            for since_attr, action, command in (
                ("_eco_off_since", SafetyAction.ECO_RESTORED, cmd_eco(True)),
                ("_manual_since", SafetyAction.DYNAMIC_RESTORED, cmd_dynamic(True)),
            ):
                since = getattr(self, since_attr)
                if since is None or now - since < cfg.delay:
                    continue
                # Next attempt in RETRY_AFTER if the stove still reports the risky mode.
                setattr(self, since_attr, now - cfg.delay + RETRY_AFTER)
                if command in sent:
                    continue
                results.append(SafetyResult(action, [command], room))
        return results
