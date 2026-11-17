<p align="center"><img src="docs/emblem.svg" width="112" alt=""></p>

# MCZ Maestro (cloud) for Home Assistant

[![CI](https://github.com/Alardware/mcz-maestro/actions/workflows/validate.yml/badge.svg)](https://github.com/Alardware/mcz-maestro/actions)
[![HACS](https://img.shields.io/badge/HACS-custom%20repository-41bdf5)](https://hacs.xyz/docs/faq/custom_repositories/)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-support%20the%20project-ff5f5f?logo=ko-fi&logoColor=white)](https://ko-fi.com/alardware)

*Version française : [README.fr.md](README.fr.md)*

Home Assistant integration for MCZ pellet stoves fitted with the **first-generation Maestro**
module: the ones controlled with the legacy "MCZ Maestro" app, paired with a
**serial number + remote MAC address**.

> Stoves linked to an **account** in the newer MCZ app (Maestro+) are covered by another
> integration: [Robbe-B/maestro_mcz](https://github.com/Robbe-B/maestro_mcz).

- Goes through the MCZ cloud, like the app: no wiring, works from anywhere.
- No external Python dependency.
- Live updates (persistent connection) plus a refresh every 30 s.
- Lovelace card included (`custom:mcz-maestro-card`), installed automatically.
- Follows Home Assistant's language: entities, card and alerts in English, French, Italian
  or German (English for other languages).
- Its own icon in the integrations list (Home Assistant 2026.3+).

Community project, not affiliated with MCZ.

## Installation (HACS)

1. HACS → ⋮ menu → **Custom repositories** → add `https://github.com/Alardware/mcz-maestro`,
   category **Integration**.
2. Install **MCZ Maestro (cloud)**, then restart Home Assistant.
3. **Settings → Devices & services → Add integration → MCZ Maestro**.
4. Enter a name, the **serial number** and the **remote MAC address**. Both are shown in the
   MCZ app under **Device list** (the serial number is also on the stove's rating plate).

The integration checks that the stove answers before saving.

> 🔒 The serial number + MAC pair is enough to control the stove through the MCZ cloud.
> Do not publish it (GitHub issue, forum, screenshot). The integration keeps it inside
> Home Assistant and masks it in diagnostics.

Manual install: copy `custom_components/mcz_maestro` into `/config/custom_components/`.

## Entities

| Type | Entities |
|---|---|
| Thermostat | On/off, setpoint (0.5 °C steps), room temperature, **Dynamic** / **Manual** presets |
| Fan | Room fan: speeds 1–5 + Auto |
| Select | Power level 1–5 (used in Manual) |
| Switches | Eco Stop, Chrono, Silent, Active, Sounds |
| Sensors | State, alarm, room temperature, flue gas temperature, setpoint, motherboard temperature, current power, flue fan, auger (live / setpoint), Active (live / setpoint), hours before service, operating time (total + per power level), minutes before shutdown, ignitions, season, stove clock |
| Binary sensors | Heating, alarm, igniter, brazier to clean, pellets empty (if the stove has the sensor), MCZ cloud |
| Buttons | Reset alarm, sync stove clock, refresh |

Left out on purpose: technical menu, factory settings, motor diagnostics.
Chrono time slots are still edited in the MCZ app (the Chrono switch turns them on or off).

## Card

```yaml
type: custom:mcz-maestro-card
entity: climate.stove
# name: Living room   # optional
```

Dial (room temperature, setpoint ±0.5 °C), on/off, Dynamic/Manual, power level, fan,
Eco Stop / Chrono / Silent, details panel, alarm banner with reset.
It follows the Home Assistant theme (light/dark). Optional CSS variables:
`--mcz-accent`, `--mcz-heat-start`, `--mcz-heat-end`.

## Alarm on your phone

Every new alarm fires the `mcz_maestro_alarm` event
(`code`, `label` in Home Assistant's language, `state`, `device_id`):

```yaml
automation:
  - alias: Stove alarm
    triggers:
      - trigger: event
        event_type: mcz_maestro_alarm
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "Stove alarm"
          message: "{{ trigger.event.data.label }}"
```

## Options

**Configure** on the integration: refresh interval (15–300 s, default 30).
**Reconfigure**: change the remote MAC address (Wi-Fi module replaced).

## Troubleshooting

- Entities unavailable: no data from the stove for 3 minutes. Check that the MCZ app works;
  the integration reconnects on its own (5 s → 5 min).
- The **MCZ cloud** binary sensor shows the state of the cloud link.
- **Download diagnostics** (device page): decoded state + raw frames, without the serial
  number or MAC.

## Adding a setting (Eco Stop, room input, frost protection…)

Diagnostics hold the raw parameters frame (`frames.params`). To locate a setting: download
the diagnostics, change **one** setting in the MCZ app, wait an hour (or reload the
integration), download again and compare the two frames.

## Development

```bash
python -m venv venv && . venv/bin/activate
pip install pytest-homeassistant-custom-component
pytest                                   # 100+ tests against a built-in fake MCZ cloud
python tests/card/shoot.py               # card in Chrome (playwright), screenshots in tests/card/out
python tools/gen_translations.py         # regenerates strings.json and translations/*.json
```

The protocol (socket.io on `app.mcz.it:9000`, `C|RecuperoInfo` and
`C|WriteParametri|id|value` frames) was documented by the Jeedom / openHAB community;
the code in this repository is an independent rewrite.

## Support

This integration is developed in my spare time. If it is useful to you, a coffee
helps keep it alive:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/alardware)

## License

MIT
