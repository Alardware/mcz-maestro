"""Safety guard: pure logic, no Home Assistant."""

from __future__ import annotations

from custom_components.mcz_maestro import protocol as p
from custom_components.mcz_maestro.safety import (
    RETRY_AFTER,
    SafetyAction,
    SafetyConfig,
    SafetyGuard,
)

from .conftest import build_info_frame

HOUR = 3600.0


def state(**overrides: int) -> p.MaestroState:
    """Info frame with overrides by field name."""
    idx = {"code": 1, "ambient2": 6, "dynamic": 22, "eco": 23}
    return p.parse_info(build_info_frame({idx[k]: v for k, v in overrides.items()}))


def guard(**cfg) -> SafetyGuard:
    base = {
        "revert": True,
        "delay": HOUR,
        "overheat": True,
        "overheat_temp": 27.0,
        "shutdown_temp": 30.0,
    }
    base.update(cfg)
    return SafetyGuard(SafetyConfig(**base))


def actions(result) -> list[tuple[SafetyAction, list[str]]]:
    return [(a.action, a.commands) for a in result]


def test_nothing_when_everything_is_normal() -> None:
    g = guard()
    assert g.evaluate(state(), 0) == []
    assert g.evaluate(state(), 10 * HOUR) == []


def test_eco_turned_back_on_after_delay() -> None:
    g = guard()
    off = state(eco=0)
    assert g.evaluate(off, 0) == []
    assert g.evaluate(off, HOUR - 1) == []
    assert actions(g.evaluate(off, HOUR)) == [(SafetyAction.ECO_RESTORED, [p.cmd_eco(True)])]


def test_eco_back_on_resets_the_timer() -> None:
    g = guard()
    g.evaluate(state(eco=0), 0)
    g.evaluate(state(eco=1), 1800)
    assert g.evaluate(state(eco=0), 2000) == []
    assert g.evaluate(state(eco=0), 2000 + HOUR - 1) == []
    assert actions(g.evaluate(state(eco=0), 2000 + HOUR))[0][0] is SafetyAction.ECO_RESTORED


def test_manual_back_to_dynamic_after_delay() -> None:
    g = guard()
    manual = state(dynamic=0)
    assert g.evaluate(manual, 0) == []
    assert actions(g.evaluate(manual, HOUR)) == [(SafetyAction.DYNAMIC_RESTORED, [p.cmd_dynamic(True)])]


def test_both_reverted_together() -> None:
    g = guard()
    s = state(eco=0, dynamic=0)
    g.evaluate(s, 0)
    assert [a for a, _ in actions(g.evaluate(s, HOUR))] == [
        SafetyAction.ECO_RESTORED,
        SafetyAction.DYNAMIC_RESTORED,
    ]


def test_revert_retries_only_after_retry_delay() -> None:
    g = guard()
    s = state(eco=0)
    g.evaluate(s, 0)
    assert g.evaluate(s, HOUR)
    assert g.evaluate(s, HOUR + RETRY_AFTER - 1) == []
    assert g.evaluate(s, HOUR + RETRY_AFTER)


def test_revert_disabled() -> None:
    g = guard(revert=False)
    s = state(eco=0, dynamic=0)
    g.evaluate(s, 0)
    assert g.evaluate(s, 10 * HOUR) == []
    assert g.deadlines(10 * HOUR) == (None, None)


def test_deadlines() -> None:
    g = guard()
    assert g.deadlines(0) == (None, None)
    g.evaluate(state(eco=0), 100)
    g.evaluate(state(eco=0, dynamic=0), 400)
    assert g.deadlines(400) == (HOUR - 300, HOUR)


def test_overheat_restores_eco_and_dynamic_immediately() -> None:
    g = guard()
    hot = state(ambient2=56, eco=0, dynamic=0)  # 28 °C
    assert actions(g.evaluate(hot, 0)) == [
        (SafetyAction.OVERHEAT, [p.cmd_eco(True), p.cmd_dynamic(True)])
    ]
    # No repeat before the retry delay, even if the stove still reports the old modes.
    assert g.evaluate(hot, RETRY_AFTER - 1) == []
    assert actions(g.evaluate(hot, RETRY_AFTER))[0][0] is SafetyAction.OVERHEAT


def test_overheat_only_sends_what_is_needed() -> None:
    g = guard()
    assert actions(g.evaluate(state(ambient2=56, dynamic=0), 0)) == [
        (SafetyAction.OVERHEAT, [p.cmd_dynamic(True)])
    ]


def test_overheat_ignored_when_modes_are_fine_or_stove_off() -> None:
    g = guard()
    assert g.evaluate(state(ambient2=56), 0) == []
    assert g.evaluate(state(ambient2=56, eco=0, code=0), 0) == []


def test_shutdown_above_limit() -> None:
    g = guard()
    very_hot = state(ambient2=60, eco=0, dynamic=0)  # 30 °C
    assert actions(g.evaluate(very_hot, 0)) == [(SafetyAction.SHUTDOWN, [p.cmd_power(False)])]
    assert g.evaluate(very_hot, RETRY_AFTER - 1) == []


def test_no_shutdown_when_already_stopping() -> None:
    g = guard()
    for code in (0, 40, 41, 50):
        assert all(
            a.action is not SafetyAction.SHUTDOWN for a in g.evaluate(state(ambient2=64, code=code), 0)
        ), code


def test_overheat_disabled() -> None:
    g = guard(overheat=False)
    assert g.evaluate(state(ambient2=70, eco=0, dynamic=0), 0) == []


def test_unknown_values_never_trigger() -> None:
    g = guard()
    blank = p.parse_info("01")
    assert g.evaluate(blank, 0) == []
    assert g.evaluate(blank, 10 * HOUR) == []


def test_reconfigure_keeps_timers() -> None:
    g = guard()
    g.evaluate(state(eco=0), 0)
    g.config = SafetyConfig(revert=True, delay=600, overheat=True, overheat_temp=27, shutdown_temp=30)
    assert actions(g.evaluate(state(eco=0), 600))[0][0] is SafetyAction.ECO_RESTORED
