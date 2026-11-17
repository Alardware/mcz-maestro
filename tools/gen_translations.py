"""Generate strings.json, translations/en.json and translations/fr.json.

Run from the repository root: python tools/gen_translations.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "mcz_maestro"

STATES = {
    "off": ("Off", "Éteint"),
    "checking": ("Checking hot/cold", "Contrôle chaud/froid"),
    "cleaning_cold": ("Cleaning (cold)", "Nettoyage à froid"),
    "loading_cold": ("Loading pellets (cold)", "Chargement à froid"),
    "start_1_cold": ("Start 1 (cold)", "Démarrage 1 à froid"),
    "start_2_cold": ("Start 2 (cold)", "Démarrage 2 à froid"),
    "cleaning_hot": ("Cleaning (hot)", "Nettoyage à chaud"),
    "loading_hot": ("Loading pellets (hot)", "Chargement à chaud"),
    "start_1_hot": ("Start 1 (hot)", "Démarrage 1 à chaud"),
    "start_2_hot": ("Start 2 (hot)", "Démarrage 2 à chaud"),
    "stabilising": ("Stabilising", "Stabilisation"),
    "power_1": ("Power 1", "Puissance 1"),
    "power_2": ("Power 2", "Puissance 2"),
    "power_3": ("Power 3", "Puissance 3"),
    "power_4": ("Power 4", "Puissance 4"),
    "power_5": ("Power 5", "Puissance 5"),
    "diagnostics": ("Diagnostics", "Diagnostic"),
    "on": ("On", "Allumé"),
    "extinguishing": ("Extinguishing", "Extinction"),
    "cooling": ("Cooling down", "Refroidissement"),
    "cleaning_low": ("Cleaning (low pressure)", "Nettoyage basse pression"),
    "cleaning_high": ("Cleaning (high pressure)", "Nettoyage haute pression"),
    "unlocking_auger": ("Unlocking auger", "Déblocage vis sans fin"),
    "auto_eco": ("Auto Eco", "Auto Éco"),
    "standby": ("Standby", "Veille"),
    "loading_auger": ("Loading auger", "Chargement vis sans fin"),
    "waiting_safety_alarms": ("Waiting for safety alarms", "Attente alarmes de sécurité"),
    "unknown": ("Unknown", "Inconnu"),
}

ALARMS = {
    "a01": ("Ignition failed", "Allumage raté"),
    "a02": ("No flame", "Pas de flamme"),
    "a03": ("Tank overheating", "Surchauffe du réservoir"),
    "a04": ("Flue gas too hot", "Température des fumées trop haute"),
    "a05": ("Flue obstructed or wind", "Conduit obstrué ou vent"),
    "a06": ("Poor draught", "Mauvais tirage"),
    "a09": ("Flue gas probe fault", "Défaut sonde fumées"),
    "a11": ("Gear motor fault", "Défaut motoréducteur"),
    "a12": ("Gear motor controller fault", "Défaut contrôleur motoréducteur"),
    "a13": ("Motherboard too hot", "Température carte mère trop haute"),
    "a14": ("Active fault", "Défaut Active"),
    "a17": ("Auger jammed", "Bourrage vis sans fin"),
    "a18": ("Water too hot", "Température d'eau trop haute"),
    "a19": ("Water probe fault", "Défaut sonde eau"),
    "a20": ("Auxiliary probe fault", "Défaut sonde auxiliaire"),
    "a21": ("Pressure switch alarm", "Alarme pressostat"),
    "a22": ("Room probe fault", "Défaut sonde ambiante"),
    "a23": ("Brazier closing fault", "Défaut fermeture brasero"),
}

for key, (en, fr) in ALARMS.items():
    STATES[f"alarm_{key}"] = (f"Alarm {key.upper()} – {en}", f"Alarme {key.upper()} – {fr}")


def build(lang: int) -> dict:
    """lang 0 = English, 1 = French."""

    def t(en: str, fr: str) -> str:
        return (en, fr)[lang]

    states = {k: v[lang] for k, v in STATES.items()}
    alarm_states = {"none": t("None", "Aucune"), "safety": t("Waiting for safety alarms", "Attente alarmes de sécurité")}
    alarm_states.update({k: f"{k.upper()} – {v[lang]}" for k, v in ALARMS.items()})
    name = lambda en, fr: {"name": t(en, fr)}  # noqa: E731

    return {
        "config": {
            "step": {
                "user": {
                    "title": t("MCZ Maestro stove", "Poêle MCZ Maestro"),
                    "description": t(
                        "Stove paired with the legacy MCZ Maestro app (serial number + remote MAC address). Both are shown in the app under Device list.",
                        "Poêle appairé avec l'ancienne appli MCZ Maestro (numéro de série + adresse MAC remote). Les deux sont visibles dans l'appli, menu Liste des dispositifs.",
                    ),
                    "data": {
                        "name": t("Name", "Nom"),
                        "serial": t("Serial number", "Numéro de série"),
                        "mac": t("Remote MAC address", "Adresse MAC remote"),
                    },
                    "data_description": {
                        "serial": t("On the stove's rating plate or in the app.", "Sur la plaque du poêle ou dans l'appli."),
                        "mac": t("12 hex characters, with or without colons.", "12 caractères hexadécimaux, avec ou sans « : »."),
                    },
                },
                "reconfigure": {
                    "title": t("Change remote MAC address", "Changer l'adresse MAC remote"),
                    "data": {"mac": t("Remote MAC address", "Adresse MAC remote")},
                },
            },
            "error": {
                "invalid_serial": t("Invalid serial number.", "Numéro de série invalide."),
                "invalid_mac": t("Invalid MAC address (12 hex characters).", "Adresse MAC invalide (12 caractères hexadécimaux)."),
                "cannot_connect": t("Cannot reach the MCZ cloud.", "Impossible de joindre le cloud MCZ."),
                "no_response": t(
                    "The MCZ cloud answered but the stove did not: check it is online and the serial/MAC pair.",
                    "Le cloud MCZ répond mais pas le poêle : vérifie qu'il est en ligne et le couple série/MAC.",
                ),
                "unknown": t("Unexpected error, see the logs.", "Erreur inattendue, voir les journaux."),
            },
            "abort": {
                "already_configured": t("This stove is already configured.", "Ce poêle est déjà configuré."),
                "reconfigure_successful": t("MAC address updated.", "Adresse MAC mise à jour."),
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": t("Options", "Options"),
                    "data": {"scan_interval": t("Refresh interval (s)", "Intervalle de rafraîchissement (s)")},
                    "data_description": {
                        "scan_interval": t(
                            "How often the stove is asked for fresh data (15–300 s).",
                            "Fréquence de demande de nouvelles données au poêle (15–300 s).",
                        )
                    },
                }
            }
        },
        "entity": {
            "climate": {
                "stove": {
                    "state_attributes": {
                        "preset_mode": {
                            "state": {"dynamic": "Dynamic", "manual": t("Manual", "Manuel")}
                        }
                    }
                }
            },
            "fan": {
                "room_fan": {
                    "name": t("Room fan", "Ventilateur ambiance"),
                    "state_attributes": {"preset_mode": {"state": {"auto": "Auto"}}},
                }
            },
            "select": {"power_level": name("Power level", "Puissance")},
            "switch": {
                "eco": name("Eco Stop", "Eco Stop"),
                "chrono": name("Chrono", "Chrono"),
                "silent": name("Silent", "Silence"),
                "active": name("Active", "Active"),
                "sounds": name("Sounds", "Sons"),
            },
            "sensor": {
                "state": {"name": t("State", "État"), "state": states},
                "alarm": {"name": t("Alarm", "Alarme"), "state": alarm_states},
                "ambient_temp": name("Room temperature", "Température ambiante"),
                "fumes_temp": name("Flue gas temperature", "Température des fumées"),
                "setpoint": name("Setpoint", "Consigne"),
                "board_temp": name("Motherboard temperature", "Température carte mère"),
                "power": name("Current power", "Puissance actuelle"),
                "fumes_fan_rpm": name("Flue fan speed", "Vitesse extracteur fumées"),
                "auger_rpm": name("Auger speed", "Vis sans fin"),
                "auger_rpm_set": name("Auger speed setpoint", "Vis sans fin consigne"),
                "active_live": name("Active", "Active"),
                "active_set": name("Active setpoint", "Active consigne"),
                "hours_to_service": name("Hours before service", "Heures avant entretien"),
                "total_hours": name("Operating time", "Temps de fonctionnement"),
                **{
                    f"power_{n}_hours": name(f"Operating time power {n}", f"Temps en puissance {n}")
                    for n in range(1, 6)
                },
                "minutes_to_off": name("Minutes before shutdown", "Minutes avant extinction"),
                "ignitions": name("Ignitions", "Allumages"),
                "season": {
                    "name": t("Season", "Saison"),
                    "state": {"winter": t("Winter", "Hiver"), "summer": t("Summer", "Été")},
                },
                "stove_clock": name("Stove clock", "Horloge du poêle"),
                "profile": name("Profile (raw)", "Profil (brut)"),
                "antifreeze": name("Frost protection (raw)", "Hors-gel (brut)"),
            },
            "binary_sensor": {
                "heating": name("Heating", "En chauffe"),
                "alarm": name("Alarm", "Alarme"),
                "igniter": name("Igniter", "Bougie"),
                "brazier": name("Brazier to clean", "Brasero à nettoyer"),
                "pellets_empty": name("Pellets empty", "Granulés vides"),
                "cloud": name("MCZ cloud", "Cloud MCZ"),
            },
            "button": {
                "reset_alarm": name("Reset alarm", "Réinitialiser l'alarme"),
                "sync_clock": name("Sync stove clock", "Mettre le poêle à l'heure"),
                "refresh": name("Refresh", "Rafraîchir"),
            },
        },
        "exceptions": {
            "not_connected": {"message": t("MCZ cloud not connected, try again shortly.", "Cloud MCZ non connecté, réessaie dans un instant.")},
            "no_first_frame": {"message": t("The stove did not answer through the MCZ cloud.", "Le poêle n'a pas répondu via le cloud MCZ.")},
            "stale": {"message": t("No data from the stove for {seconds} s.", "Aucune donnée du poêle depuis {seconds} s.")},
        },
    }


def main() -> None:
    en = build(0)
    fr = build(1)
    (ROOT / "translations").mkdir(exist_ok=True)
    for path, data in (
        (ROOT / "strings.json", en),
        (ROOT / "translations" / "en.json", en),
        (ROOT / "translations" / "fr.json", fr),
    ):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
