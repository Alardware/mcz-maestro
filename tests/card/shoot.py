"""Render the card in a real browser: screenshots + interaction checks.

Usage: python tests/card/shoot.py [--chrome /usr/bin/google-chrome]
Writes PNGs to tests/card/out/ and exits non-zero on any failed check.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
HARNESS = (HERE / "harness.html").as_uri()
OUT = HERE / "out"

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        FAILURES.append(message)


def open_card(browser, scenario: str, theme: str = "dark", width: int = 390, wrap: str | None = None, lang: str | None = None):
    page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=2)
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    url = f"{HARNESS}?scenario={scenario}&theme={theme}"
    if wrap:
        url += f"&wrap={wrap}"
    if lang:
        url += f"&lang={lang}"
    page.goto(url)
    page.wait_for_selector("mcz-maestro-card .head")
    page.wait_for_timeout(250)
    return page, errors


def calls(page) -> list:
    return page.evaluate("window.__calls")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome", default="/usr/bin/google-chrome")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chrome, args=["--no-sandbox"])

        print("screenshots")
        for theme in ("dark", "light"):
            for scenario in ("dynamic", "manual", "off", "alarm", "offline", "cloud_down"):
                page, errors = open_card(browser, scenario, theme)
                if scenario == "dynamic":
                    page.click("mcz-maestro-card summary")
                    page.wait_for_timeout(200)
                page.locator("mcz-maestro-card").screenshot(path=str(OUT / f"{theme}-{scenario}-mobile.png"))
                check(not errors, f"{theme}/{scenario}: no JS error {errors or ''}")
                page.close()
            page, errors = open_card(browser, "dynamic", theme, width=1100, wrap="760px")
            page.click("mcz-maestro-card summary")
            page.wait_for_timeout(200)
            page.locator("mcz-maestro-card").screenshot(path=str(OUT / f"{theme}-dynamic-wide.png"))
            check(not errors, f"{theme}/wide: no JS error")
            page.close()

        print("interactions (dynamic)")
        page, _ = open_card(browser, "dynamic")
        card = "mcz-maestro-card"
        check(page.locator(f"{card} .sub").inner_text() == "Puissance 5", "subtitle shows translated state")
        check(page.locator(f"{card} .temp").inner_text().replace("\n", "") == "18,0°", "big temperature in French format")
        page.click(f"{card} .pwr")
        check(calls(page)[-1] == ["climate", "turn_off", {"entity_id": "climate.poele"}], "power button turns off")
        page.click(f'{card} [data-a="sp"][data-v="1"]')
        page.click(f'{card} [data-a="sp"][data-v="1"]')
        check(page.locator(f"{card} .sp .v").inner_text().startswith("20,0°"), "setpoint shows pending 20,0°")
        check(len(calls(page)) == 1, "setpoint not sent before debounce")
        page.wait_for_timeout(1300)
        check(
            calls(page)[-1] == ["climate", "set_temperature", {"entity_id": "climate.poele", "temperature": 20}],
            "setpoint sent once after debounce",
        )
        page.evaluate(
            "() => { const h = window.__hass; h.states = {...h.states, 'sensor.poele_fumees': {state: '121', attributes: {unit_of_measurement: '°C'}, last_updated: 'y'}}; window.__card.hass = {...h}; }"
        )
        page.wait_for_timeout(50)
        check(page.locator(f"{card} .sp .v").inner_text().startswith("20,0°"), "sent setpoint kept until the stove confirms")
        page.click(f'{card} [data-a="mode"][data-v="manual"]')
        check(
            calls(page)[-1] == ["climate", "set_preset_mode", {"entity_id": "climate.poele", "preset_mode": "manual"}],
            "mode switch to manual",
        )
        n = len(calls(page))
        page.click(f'{card} [data-a="level"][data-v="2"]', force=True)
        check(len(calls(page)) == n, "power bars read-only in Dynamic")
        page.click(f'{card} [data-a="fan"][data-v="2"]')
        check(
            calls(page)[-1] == ["fan", "set_percentage", {"entity_id": "fan.poele_ventilateur", "percentage": 40}],
            "fan speed 2",
        )
        page.click(f'{card} [data-a="fan"][data-v="auto"]')
        check(
            calls(page)[-1] == ["fan", "set_preset_mode", {"entity_id": "fan.poele_ventilateur", "preset_mode": "auto"}],
            "fan auto",
        )
        page.click(f'{card} [data-a="toggle"][data-v="switch.eco"]')
        check(calls(page)[-1] == ["switch", "toggle", {"entity_id": "switch.poele_eco"}], "eco chip toggles")
        check(page.locator(f'{card} [data-a="toggle"][data-v="switch.eco"].busy').count() == 1, "chip shows busy state")
        page.evaluate(
            "() => { const h = window.__hass; h.states = {...h.states, 'switch.poele_eco': {state: 'off', attributes: {}, last_updated: 'x'}}; window.__card.hass = {...h}; }"
        )
        page.wait_for_timeout(50)
        check(page.locator(f"{card} .busy").count() == 0, "busy cleared on state change")
        page.close()

        print("interactions (manual / alarm / offline)")
        page, _ = open_card(browser, "manual")
        page.click(f'{card} [data-a="level"][data-v="4"]')
        check(
            calls(page)[-1] == ["select", "select_option", {"entity_id": "select.poele_puissance", "option": "4"}],
            "power level 4 in Manual",
        )
        check(page.locator(f'{card} [data-a="sp"]').first.is_disabled(), "setpoint disabled in Manual")
        check(page.locator(f'{card} [data-a="fan"][data-v="3"]').get_attribute("aria-pressed") == "true", "fan 3 shown")
        page.close()

        page, _ = open_card(browser, "alarm")
        check("A01" in page.locator(f"{card} .banner.alarm").inner_text(), "alarm banner shows code")
        page.click(f'{card} [data-a="reset"]')
        check(calls(page)[-1] == ["button", "press", {"entity_id": "button.poele_reset"}], "reset alarm")
        page.close()

        page, _ = open_card(browser, "offline")
        check(page.locator(f"{card} .sub").inner_text() == "Poêle injoignable", "offline subtitle")
        check(page.locator(f"{card} .pwr").is_disabled(), "power disabled when unavailable")
        page.close()

        print("language follows Home Assistant")
        for lang, power, offline in (
            ("fr", "Puissance", "Poêle injoignable"),
            ("en", "Power", "Stove unreachable"),
            ("it", "Potenza", "Stufa non raggiungibile"),
            ("de", "Leistung", "Ofen nicht erreichbar"),
            ("es", "Power", "Stove unreachable"),
        ):
            page, errors = open_card(browser, "dynamic", lang=lang)
            check(page.locator(f"{card} .row-h b").first.inner_text() == power, f"{lang}: power label '{power}'")
            check(not errors, f"{lang}: no JS error")
            page.close()
            page, _ = open_card(browser, "offline", lang=lang)
            check(page.locator(f"{card} .sub").inner_text() == offline, f"{lang}: offline text '{offline}'")
            page.close()

        page, _ = open_card(browser, "dynamic")
        stub = page.evaluate("customElements.get('mcz-maestro-card').getStubConfig(window.__hass)")
        check(stub == {"entity": "climate.poele"}, "stub config picks the stove")
        check(page.evaluate("window.customCards.some(c => c.type === 'mcz-maestro-card')"), "card listed in picker")
        page.close()
        browser.close()

    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
