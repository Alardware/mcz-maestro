/*
 * mcz-maestro-card — Lovelace card for the MCZ Maestro (legacy app) integration.
 * Vanilla web component, no external dependency. Served by the integration.
 */
const CARD_VERSION = "0.1.0";
const DOMAIN = "mcz_maestro";
const SCALE_MIN = 10;
const SCALE_MAX = 30;
const SETPOINT_DEBOUNCE_MS = 1000;
const BUSY_TIMEOUT_MS = 10000;

const I18N = {
  fr: {
    setpoint: "Consigne",
    manual_setpoint: "Inactive en Manuel",
    power: "Puissance",
    power_auto: "Réglée par le poêle",
    fan: "Ventilation",
    auto: "Auto",
    dynamic: "Dynamic",
    manual: "Manuel",
    eco: "Éco Stop",
    chrono: "Chrono",
    silent: "Silence",
    info: "Infos",
    fumes: "Fumées",
    auger: "Vis sans fin",
    fumes_fan: "Extracteur",
    active: "Active",
    board: "Carte mère",
    service: "Avant entretien",
    total: "Fonctionnement",
    ignitions: "Allumages",
    reset: "Réinitialiser",
    unavailable: "Poêle injoignable",
    cloud_down: "Cloud MCZ déconnecté",
    turn_on: "Allumer le poêle",
    turn_off: "Éteindre le poêle",
    lower: "Baisser la consigne",
    raise: "Monter la consigne",
    pick_entity: "Choisis l'entité climate du poêle MCZ Maestro.",
    missing: "Entité introuvable",
  },
  en: {
    setpoint: "Setpoint",
    manual_setpoint: "Unused in Manual",
    power: "Power",
    power_auto: "Set by the stove",
    fan: "Fan",
    auto: "Auto",
    dynamic: "Dynamic",
    manual: "Manual",
    eco: "Eco Stop",
    chrono: "Chrono",
    silent: "Silent",
    info: "Details",
    fumes: "Flue gas",
    auger: "Auger",
    fumes_fan: "Flue fan",
    active: "Active",
    board: "Board",
    service: "Before service",
    total: "Operating time",
    ignitions: "Ignitions",
    reset: "Reset",
    unavailable: "Stove unreachable",
    cloud_down: "MCZ cloud disconnected",
    turn_on: "Turn the stove on",
    turn_off: "Turn the stove off",
    lower: "Lower setpoint",
    raise: "Raise setpoint",
    pick_entity: "Pick the MCZ Maestro stove climate entity.",
    missing: "Entity not found",
  },
};

/* Small original line icons (24×24, stroke = currentColor). */
const ICONS = {
  power:
    '<path d="M12 3v8"/><path d="M6.6 6.6a8 8 0 1 0 10.8 0"/>',
  flame:
    '<path d="M12 21c-3.9 0-6.5-2.6-6.5-6.2 0-3.3 2.2-5.2 3.6-7.4.5 1.8 1.6 2.9 2.6 3.3-.2-2.8 1-5.6 3.3-7.7.1 3.1 1.6 5 3 6.9 1 1.4 1.5 3 1.5 4.9C19.5 18.4 16 21 12 21Z"/><path d="M12 21c-1.7 0-3-1.2-3-2.9 0-1.6 1.2-2.6 2-3.8.8 1.5 3.9 2.3 3.9 4 0 1.6-1.2 2.7-2.9 2.7Z"/>',
  auto:
    '<path d="M12 21c-3.9 0-6.5-2.6-6.5-6.2 0-3.3 2.2-5.2 3.6-7.4.5 1.8 1.6 2.9 2.6 3.3-.2-2.8 1-5.6 3.3-7.7.1 3.1 1.6 5 3 6.9 1 1.4 1.5 3 1.5 4.9C19.5 18.4 16 21 12 21Z"/><path d="m9.6 18.2 2.4-6 2.4 6"/><path d="M10.4 16.2h3.2"/>',
  hand:
    '<path d="M8 12V5.5a1.5 1.5 0 0 1 3 0V11"/><path d="M11 10.5v-6a1.5 1.5 0 0 1 3 0v6"/><path d="M14 10.5V6a1.5 1.5 0 0 1 3 0v7.5"/><path d="M8 11.5 6.6 10a1.6 1.6 0 0 0-2.4 2.1L8 17.2c1.3 1.9 3 3.3 5.6 3.3 3.4 0 5.4-2.6 5.4-6V9.8a1.5 1.5 0 0 0-3 0"/>',
  fan:
    '<circle cx="12" cy="12" r="1.6"/><path d="M12 10.4c-.6-3.1.6-6.4 3.2-6.4 2 0 2.6 2.3 1.2 3.9-1.2 1.4-2.8 2-4.4 2.5"/><path d="M13.4 12.8c2.4 2 3.6 5.3 1.4 6.6-1.7 1-3.4-.7-3-2.8.3-1.8 1.4-3.1 1.6-3.8"/><path d="M10.6 12.8c-3 1.1-6.4.5-6.4-2.1 0-2 2.3-2.5 3.8-1.3 1.4 1.2 2.1 2.8 2.6 3.4"/>',
  leaf:
    '<path d="M5 19c0-8 5-13 14-14 0 9-5 14-12 14"/><path d="M5 19c3-4 6-6.5 9-8"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  mute:
    '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="m16 9.5 4.5 5"/><path d="m20.5 9.5-4.5 5"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  alert:
    '<path d="M12 4 2.8 19.5h18.4Z"/><path d="M12 10v4.2"/><path d="M12 17.1v.1"/>',
  cloud_off:
    '<path d="M7.5 18.5H17a3.5 3.5 0 0 0 .9-6.9A5.5 5.5 0 0 0 7.6 10 4.3 4.3 0 0 0 7.5 18.5Z"/><path d="m4 4 16 16"/>',
  minus: '<path d="M6 12h12"/>',
  plus: '<path d="M6 12h12"/><path d="M12 6v12"/>',
};

const icon = (name, cls = "") =>
  `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/* Keys are `${domain}.${translation_key}` of the stove's entities. */
const SIBLINGS = [
  "sensor.state",
  "sensor.alarm",
  "sensor.fumes_temp",
  "sensor.auger_rpm",
  "sensor.fumes_fan_rpm",
  "sensor.active_live",
  "sensor.board_temp",
  "sensor.hours_to_service",
  "sensor.total_hours",
  "sensor.ignitions",
  "sensor.power",
  "binary_sensor.alarm",
  "binary_sensor.heating",
  "binary_sensor.cloud",
  "select.power_level",
  "fan.room_fan",
  "switch.eco",
  "switch.chrono",
  "switch.silent",
  "button.reset_alarm",
];

const INFO_TILES = [
  ["sensor.fumes_temp", "fumes"],
  ["sensor.auger_rpm", "auger"],
  ["sensor.fumes_fan_rpm", "fumes_fan"],
  ["sensor.active_live", "active"],
  ["sensor.board_temp", "board"],
  ["sensor.hours_to_service", "service"],
  ["sensor.total_hours", "total"],
  ["sensor.ignitions", "ignitions"],
];

const STYLE = `
:host { display: block; }
ha-card, .card {
  --_heat-1: var(--mcz-heat-start, #ffb547);
  --_heat-2: var(--mcz-heat-end, #ef4d2f);
  --_accent: var(--mcz-accent, var(--primary-color, #c9396d));
  --_text: var(--primary-text-color, #e7edf3);
  --_muted: var(--secondary-text-color, #8a9bb0);
  --_surface: color-mix(in srgb, var(--_text) 6%, transparent);
  --_surface-2: color-mix(in srgb, var(--_text) 10%, transparent);
  --_line: color-mix(in srgb, var(--_text) 12%, transparent);
  --_danger: var(--error-color, #e5484d);
  --_radius: var(--ha-card-border-radius, 18px);
  display: block;
  container-type: inline-size;
  padding: 18px;
  color: var(--_text);
  font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif));
  -webkit-font-smoothing: antialiased;
  box-sizing: border-box;
}
* { box-sizing: border-box; }
button { font: inherit; color: inherit; border: 0; background: none; padding: 0; cursor: pointer; -webkit-tap-highlight-color: transparent; }
button:focus-visible { outline: 2px solid var(--_accent); outline-offset: 2px; }
button[disabled] { cursor: default; }
.ic { width: 20px; height: 20px; flex: none; display: block; }

.head { display: flex; align-items: center; gap: 12px; }
.badge { width: 42px; height: 42px; border-radius: 13px; display: grid; place-items: center; background: var(--_surface); color: var(--_muted); flex: none; transition: background .3s, color .3s; }
.badge .ic { width: 22px; height: 22px; }
.heating .badge { background: linear-gradient(145deg, var(--_heat-1), var(--_heat-2)); color: #fff; box-shadow: 0 6px 18px -6px color-mix(in srgb, var(--_heat-2) 70%, transparent); }
.heating .badge .ic { animation: flicker 2.4s ease-in-out infinite; transform-origin: 50% 90%; }
.titles { min-width: 0; flex: 1; }
.name { font-size: 16px; font-weight: 600; letter-spacing: .01em; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sub { font-size: 13px; color: var(--_muted); line-height: 1.3; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pwr { width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center; background: var(--_surface); color: var(--_muted); transition: background .25s, color .25s, transform .15s; flex: none; }
.pwr .ic { width: 22px; height: 22px; }
.pwr:active { transform: scale(.94); }
.on .pwr { background: var(--_accent); color: #fff; box-shadow: 0 6px 18px -8px var(--_accent); }

.banner { display: flex; align-items: center; gap: 10px; margin-top: 14px; padding: 10px 10px 10px 12px; border-radius: 14px; font-size: 13.5px; line-height: 1.35; }
.banner.alarm { background: color-mix(in srgb, var(--_danger) 16%, transparent); color: var(--_danger); }
.banner.warn { background: var(--_surface); color: var(--_muted); }
.banner .txt { flex: 1; min-width: 0; font-weight: 500; }
.banner button { padding: 8px 12px; border-radius: 10px; background: var(--_danger); color: #fff; font-weight: 600; font-size: 13px; }

.body { display: grid; gap: 16px; margin-top: 8px; }
.dial { position: relative; width: min(100%, 264px); aspect-ratio: 1; margin: 0 auto -22px; }
.dial svg { width: 100%; height: 100%; display: block; overflow: visible; }
.track { stroke: var(--_surface-2); }
.value { transition: stroke-dashoffset .8s cubic-bezier(.2,.8,.2,1); }
.knob { fill: var(--_text); stroke: var(--ha-card-background, var(--card-background-color, #1e2d3d)); stroke-width: 4; transition: cx .4s, cy .4s; }
.heating .value { filter: drop-shadow(0 0 6px color-mix(in srgb, var(--_heat-2) 55%, transparent)); }
.center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding-top: 6px; }
.label { font-size: 12px; text-transform: uppercase; letter-spacing: .12em; color: var(--_muted); }
.temp { font-size: 60px; font-weight: 300; line-height: 1; letter-spacing: -.03em; margin: 6px 0 10px; font-variant-numeric: tabular-nums; }
.temp small { font-size: 26px; font-weight: 400; letter-spacing: 0; vertical-align: top; margin-left: 2px; }
.sp { display: flex; align-items: center; gap: 6px; }
.sp button { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; background: var(--_surface); }
.sp button:active { background: var(--_surface-2); }
.sp .v { min-width: 72px; font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }
.sp .v span { display: block; font-size: 11px; font-weight: 500; color: var(--_muted); letter-spacing: .04em; }
.sp.off { opacity: .55; }
.sp.off button { visibility: hidden; }
.pending .v { color: var(--_accent); }
.offline .dial, .offline .ctl { opacity: .35; pointer-events: none; filter: grayscale(1); }

.ctl { display: grid; gap: 14px; align-content: start; }
.seg { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 4px; padding: 4px; border-radius: 14px; background: var(--_surface); }
.seg button { display: flex; align-items: center; justify-content: center; gap: 8px; height: 40px; border-radius: 11px; font-size: 14px; font-weight: 500; color: var(--_muted); transition: background .2s, color .2s; }
.seg button[aria-pressed="true"] { background: var(--ha-card-background, var(--card-background-color, #1e2d3d)); color: var(--_text); box-shadow: 0 1px 2px rgba(0,0,0,.18), 0 2px 10px -4px rgba(0,0,0,.25); }
.row-h { display: flex; align-items: baseline; justify-content: space-between; margin: 0 2px 8px; }
.row-h b { font-size: 13px; font-weight: 600; }
.row-h span { font-size: 12px; color: var(--_muted); }
.bars { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; align-items: end; height: 46px; }
.bars button { border-radius: 8px; background: var(--_surface-2); transition: background .25s; height: 100%; }
.bars button:nth-child(1) { height: 36%; } .bars button:nth-child(2) { height: 52%; } .bars button:nth-child(3) { height: 68%; } .bars button:nth-child(4) { height: 84%; }
.bars button.lit { background: linear-gradient(180deg, var(--_heat-1), var(--_heat-2)); }
.bars.ro button { cursor: default; }
.bars.ro button.lit { opacity: .8; }
.fan button { height: 38px; font-variant-numeric: tabular-nums; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 7px; height: 36px; padding: 0 14px 0 11px; border-radius: 999px; background: var(--_surface); color: var(--_muted); font-size: 13.5px; font-weight: 500; transition: background .2s, color .2s; }
.chip .ic { width: 18px; height: 18px; }
.chip[aria-pressed="true"] { background: color-mix(in srgb, var(--_accent) 18%, transparent); color: var(--_text); }
.chip[aria-pressed="true"] .ic { color: var(--_accent); }
.busy { animation: pulse 1.1s ease-in-out infinite; }

details { border-top: 1px solid var(--_line); margin-top: 4px; }
summary { list-style: none; display: flex; align-items: center; justify-content: space-between; cursor: pointer; padding: 14px 2px 2px; font-size: 13px; font-weight: 600; color: var(--_muted); }
summary::-webkit-details-marker { display: none; }
summary .ic { width: 18px; height: 18px; transition: transform .2s; }
details[open] summary .ic { transform: rotate(180deg); }
.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 12px; }
.tile { padding: 10px 12px; border-radius: 12px; background: var(--_surface); min-width: 0; }
.tile span { display: block; font-size: 11.5px; color: var(--_muted); }
.tile b { display: block; font-size: 15px; font-weight: 600; margin-top: 2px; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msg { padding: 8px 0; color: var(--_muted); font-size: 14px; }

@container (min-width: 560px) {
  .body { grid-template-columns: minmax(220px, 280px) 1fr; align-items: center; gap: 24px; }
  .dial { margin-bottom: 0; }
  .grid { grid-template-columns: repeat(4, 1fr); }
}
@keyframes flicker { 0%,100% { transform: scale(1) rotate(0); } 30% { transform: scale(1.06,.96) rotate(-2deg); } 60% { transform: scale(.97,1.05) rotate(2deg); } }
@keyframes pulse { 50% { opacity: .45; } }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
`;

class McZMaestroCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._sig = "";
    this._busy = new Map();
    this._pendingSetpoint = null;
    this._timer = null;
    this._infoOpen = false;
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("toggle", (ev) => {
      if (ev.target.tagName === "DETAILS") this._infoOpen = ev.target.open;
    }, true);
  }

  static getConfigElement() {
    return document.createElement("mcz-maestro-card-editor");
  }

  static getStubConfig(hass) {
    const entry = Object.values(hass?.entities || {}).find(
      (e) => e.platform === DOMAIN && e.entity_id.startsWith("climate.")
    );
    return { entity: entry ? entry.entity_id : "" };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("entity: climate entity of the MCZ Maestro stove");
    this._config = { ...config };
    this._sig = "";
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    this._resolve();
    const sig = this._signature();
    if (sig === this._sig) return;
    if (this._sig) this._busy.clear();
    this._sig = sig;
    this._render();
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  /* ------------------------------------------------------------- helpers */
  _t(key) {
    const lang = (this._hass?.locale?.language || this._hass?.language || "fr").slice(0, 2);
    return (I18N[lang] || I18N.fr)[key] ?? I18N.fr[key] ?? key;
  }

  _resolve() {
    const climateId = this._config.entity;
    const entities = this._hass.entities || {};
    if (this._ids && this._idsFor === climateId && this._entitiesRef === entities) return;
    this._entitiesRef = entities;
    const deviceId = entities[climateId]?.device_id;
    const ids = {};
    if (deviceId) {
      for (const e of Object.values(entities)) {
        if (e.device_id !== deviceId || e.platform !== DOMAIN || !e.translation_key) continue;
        ids[`${e.entity_id.split(".")[0]}.${e.translation_key}`] = e.entity_id;
      }
    }
    this._ids = ids;
    this._idsFor = deviceId ? climateId : null;
  }

  _st(key) {
    const id = key === "climate" ? this._config.entity : this._ids?.[key];
    return id ? this._hass.states[id] : undefined;
  }

  _signature() {
    const parts = [this._config.entity, this._hass.locale?.language];
    for (const key of ["climate", ...SIBLINGS]) {
      const s = this._st(key);
      parts.push(s ? `${s.state}|${s.last_updated}` : "-");
    }
    return parts.join(";");
  }

  _fmt(stateObj) {
    if (!stateObj) return "—";
    if (["unavailable", "unknown"].includes(stateObj.state)) return "—";
    if (typeof this._hass.formatEntityState === "function") return this._hass.formatEntityState(stateObj);
    const unit = stateObj.attributes?.unit_of_measurement;
    return unit ? `${stateObj.state} ${unit}` : stateObj.state;
  }

  _num(value, digits = 1) {
    const lang = this._hass?.locale?.language || "fr";
    return new Intl.NumberFormat(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  }

  _call(domain, service, data, busyKey) {
    if (busyKey) {
      this._busy.set(busyKey, Date.now());
      setTimeout(() => {
        if (this._busy.get(busyKey) && Date.now() - this._busy.get(busyKey) >= BUSY_TIMEOUT_MS) {
          this._busy.delete(busyKey);
          this._render();
        }
      }, BUSY_TIMEOUT_MS);
      this._render();
    }
    return this._hass.callService(domain, service, data);
  }

  _isBusy(key) {
    return this._busy.has(key) ? " busy" : "";
  }

  /* ------------------------------------------------------------- actions */
  _onClick(ev) {
    const el = ev.target.closest("[data-a]");
    if (!el || el.disabled) return;
    const a = el.dataset.a;
    const v = el.dataset.v;
    const climate = this._config.entity;
    switch (a) {
      case "power": {
        const on = this._st("climate")?.state !== "off";
        this._call("climate", on ? "turn_off" : "turn_on", { entity_id: climate }, "power");
        break;
      }
      case "sp": {
        const st = this._st("climate");
        const step = st?.attributes?.target_temp_step || 0.5;
        const min = st?.attributes?.min_temp ?? 5;
        const max = st?.attributes?.max_temp ?? 35;
        const base = this._pendingSetpoint ?? st?.attributes?.temperature ?? 20;
        this._pendingSetpoint = Math.min(max, Math.max(min, Math.round((base + Number(v) * step) * 2) / 2));
        clearTimeout(this._timer);
        this._timer = setTimeout(() => {
          const value = this._pendingSetpoint;
          this._pendingSetpoint = null;
          this._sentSetpoint = { value, at: Date.now() };
          this._call("climate", "set_temperature", { entity_id: climate, temperature: value }, "sp");
        }, SETPOINT_DEBOUNCE_MS);
        this._render();
        break;
      }
      case "mode":
        this._call("climate", "set_preset_mode", { entity_id: climate, preset_mode: v }, "mode");
        break;
      case "level":
        this._call("select", "select_option", { entity_id: this._ids["select.power_level"], option: v }, "level");
        break;
      case "fan": {
        const fan = this._ids["fan.room_fan"];
        if (v === "auto") this._call("fan", "set_preset_mode", { entity_id: fan, preset_mode: "auto" }, "fan");
        else this._call("fan", "set_percentage", { entity_id: fan, percentage: Number(v) * 20 }, "fan");
        break;
      }
      case "toggle":
        this._call("switch", "toggle", { entity_id: this._ids[v] }, v);
        break;
      case "reset":
        this._call("button", "press", { entity_id: this._ids["button.reset_alarm"] }, "reset");
        break;
      default:
    }
  }

  /* ------------------------------------------------------------- render */
  _dial(ambient, setpoint, heating) {
    const R = 84;
    const C = 100;
    const START = 135;
    const SWEEP = 270;
    const frac = (t) => Math.min(1, Math.max(0, (t - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)));
    const pt = (deg) => {
      const r = (deg * Math.PI) / 180;
      return [C + R * Math.cos(r), C + R * Math.sin(r)];
    };
    const [x0, y0] = pt(START);
    const [x1, y1] = pt(START + SWEEP);
    const arc = `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${R} ${R} 0 1 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
    const length = (2 * Math.PI * R * SWEEP) / 360;
    const shown = ambient == null ? 0 : frac(ambient);
    const knob = setpoint == null ? "" : (() => {
      const [kx, ky] = pt(START + SWEEP * frac(setpoint));
      return `<circle class="knob" cx="${kx.toFixed(2)}" cy="${ky.toFixed(2)}" r="7"/>`;
    })();
    const stroke = heating ? "url(#mczHeat)" : "var(--_muted)";
    return `
      <svg viewBox="0 0 200 200" role="img" aria-hidden="true">
        <defs>
          <linearGradient id="mczHeat" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stop-color="var(--_heat-1)"/>
            <stop offset="1" stop-color="var(--_heat-2)"/>
          </linearGradient>
        </defs>
        <path class="track" d="${arc}" fill="none" stroke-width="12" stroke-linecap="round"/>
        <path class="value" d="${arc}" fill="none" stroke="${stroke}" stroke-width="12" stroke-linecap="round"
          stroke-dasharray="${length.toFixed(2)}" stroke-dashoffset="${(length * (1 - shown)).toFixed(2)}"/>
        ${knob}
      </svg>`;
  }

  _render() {
    if (!this._hass || !this._config) return;
    const climate = this._st("climate");
    const name = this._config.name || climate?.attributes?.friendly_name || "Poêle";
    if (!climate) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card class="card"><div class="msg">${esc(this._t("missing"))} : ${esc(this._config.entity)}</div></ha-card>`;
      return;
    }
    const a = climate.attributes || {};
    const unavailable = climate.state === "unavailable";
    const on = climate.state !== "off" && !unavailable;
    const heating = on && a.hvac_action === "heating";
    const dynamic = a.preset_mode !== "manual";
    const stateObj = this._st("sensor.state");
    const subtitle = unavailable ? this._t("unavailable") : this._fmt(stateObj);
    const alarmOn = this._st("binary_sensor.alarm")?.state === "on";
    const cloud = this._st("binary_sensor.cloud");
    const sent = this._sentSetpoint;
    if (sent && (a.temperature === sent.value || Date.now() - sent.at > BUSY_TIMEOUT_MS)) this._sentSetpoint = null;
    const pending = this._pendingSetpoint != null;
    const setpoint = pending ? this._pendingSetpoint : this._sentSetpoint ? this._sentSetpoint.value : a.temperature;
    const ambient = typeof a.current_temperature === "number" ? a.current_temperature : null;
    const [whole, frac] = ambient == null ? ["—", ""] : this._num(ambient).split(/[.,]/);
    const sep = ambient == null ? "" : this._num(0.5).replace(/[0-9]/g, "");
    const power = Number(this._st("select.power_level")?.state) || Number(this._st("sensor.power")?.state) || 0;
    const fanSt = this._st("fan.room_fan");
    const fanAuto = fanSt?.attributes?.preset_mode === "auto";
    const fanLevel = fanSt?.attributes?.percentage ? Math.round(fanSt.attributes.percentage / 20) : 0;

    let banner = "";
    if (alarmOn) {
      banner = `<div class="banner alarm" role="alert">${icon("alert")}<div class="txt">${esc(this._fmt(this._st("sensor.alarm")))}</div>
        ${this._ids["button.reset_alarm"] ? `<button data-a="reset" class="${this._isBusy("reset")}">${esc(this._t("reset"))}</button>` : ""}</div>`;
    } else if (cloud && cloud.state === "off") {
      banner = `<div class="banner warn">${icon("cloud_off")}<div class="txt">${esc(this._t("cloud_down"))}</div></div>`;
    }

    const chip = (key, ic, label) => {
      const s = this._st(key);
      if (!s) return "";
      return `<button class="chip${this._isBusy(key)}" data-a="toggle" data-v="${key}" aria-pressed="${s.state === "on"}">${icon(ic)}${esc(this._t(label))}</button>`;
    };

    const bars = [1, 2, 3, 4, 5]
      .map((n) => `<button data-a="level" data-v="${n}" class="${on && n <= power ? "lit" : ""}" ${dynamic ? "disabled" : ""}
          aria-label="${esc(this._t("power"))} ${n}" aria-pressed="${n === power}"></button>`)
      .join("");

    const fanButtons = fanSt
      ? `<div><div class="row-h"><b>${esc(this._t("fan"))}</b></div>
          <div class="seg fan${this._isBusy("fan")}">
            <button data-a="fan" data-v="auto" aria-pressed="${fanAuto}">${esc(this._t("auto"))}</button>
            ${[1, 2, 3, 4, 5].map((n) => `<button data-a="fan" data-v="${n}" aria-pressed="${!fanAuto && fanLevel === n}">${n}</button>`).join("")}
          </div></div>`
      : "";

    const tiles = INFO_TILES.map(([key, label]) => {
      const s = this._st(key);
      return s ? `<div class="tile"><span>${esc(this._t(label))}</span><b>${esc(this._fmt(s))}</b></div>` : "";
    }).join("");

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card class="card ${on ? "on" : ""} ${heating ? "heating" : ""} ${unavailable ? "offline" : ""} ${pending ? "pending" : ""}">
        <div class="head">
          <div class="badge">${icon("flame")}</div>
          <div class="titles"><div class="name">${esc(name)}</div><div class="sub">${esc(subtitle)}</div></div>
          <button class="pwr${this._isBusy("power")}" data-a="power" ${unavailable ? "disabled" : ""}
            aria-label="${esc(this._t(on ? "turn_off" : "turn_on"))}" aria-pressed="${on}">${icon("power")}</button>
        </div>
        ${banner}
        <div class="body">
          <div class="dial">
            ${this._dial(ambient, setpoint, heating)}
            <div class="center">
              <div class="label">${esc(dynamic ? this._t("dynamic") : this._t("manual"))}</div>
              <div class="temp">${esc(whole)}<small>${frac ? esc(sep + frac) : ""}°</small></div>
              <div class="sp ${dynamic ? "" : "off"}${this._isBusy("sp")}">
                <button data-a="sp" data-v="-1" aria-label="${esc(this._t("lower"))}" ${dynamic ? "" : "disabled"}>${icon("minus")}</button>
                <div class="v">${setpoint == null ? "—" : `${esc(this._num(setpoint))}°`}<span>${esc(dynamic ? this._t("setpoint") : this._t("manual_setpoint"))}</span></div>
                <button data-a="sp" data-v="1" aria-label="${esc(this._t("raise"))}" ${dynamic ? "" : "disabled"}>${icon("plus")}</button>
              </div>
            </div>
          </div>
          <div class="ctl">
            <div class="seg${this._isBusy("mode")}">
              <button data-a="mode" data-v="dynamic" aria-pressed="${dynamic}">${icon("auto")}${esc(this._t("dynamic"))}</button>
              <button data-a="mode" data-v="manual" aria-pressed="${!dynamic}">${icon("hand")}${esc(this._t("manual"))}</button>
            </div>
            <div>
              <div class="row-h"><b>${esc(this._t("power"))}</b><span>${esc(dynamic ? this._t("power_auto") : power ? `${power} / 5` : "")}</span></div>
              <div class="bars ${dynamic ? "ro" : ""}${this._isBusy("level")}">${bars}</div>
            </div>
            ${fanButtons}
            <div class="chips">
              ${chip("switch.eco", "leaf", "eco")}
              ${chip("switch.chrono", "clock", "chrono")}
              ${chip("switch.silent", "mute", "silent")}
            </div>
          </div>
        </div>
        ${tiles ? `<details ${this._infoOpen ? "open" : ""}><summary>${esc(this._t("info"))}${icon("chevron")}</summary><div class="grid">${tiles}</div></details>` : ""}
      </ha-card>`;
  }
}

class McZMaestroCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => ({ entity: "Poêle (climate)", name: "Nom affiché" })[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        this._config = { ...this._config, ...ev.detail.value };
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      { name: "entity", required: true, selector: { entity: { domain: "climate", integration: DOMAIN } } },
      { name: "name", selector: { text: {} } },
    ];
  }
}

if (!customElements.get("mcz-maestro-card")) {
  customElements.define("mcz-maestro-card", McZMaestroCard);
  customElements.define("mcz-maestro-card-editor", McZMaestroCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "mcz-maestro-card",
    name: "MCZ Maestro",
    description: "Poêle à granulés MCZ (ancienne appli Maestro)",
    preview: true,
    documentationURL: "https://github.com/Alardware/mcz-maestro",
  });
  console.info(`%c MCZ-MAESTRO-CARD %c ${CARD_VERSION} `, "background:#ef4d2f;color:#fff;border-radius:3px 0 0 3px", "background:#1e2d3d;color:#fff;border-radius:0 3px 3px 0");
}
