"""Generate strings.json and translations/{en,fr,it,de}.json.

Run from the repository root: python tools/gen_translations.py
Every text is a tuple (English, French, Italian, German).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "mcz_maestro"
LANGS = ("en", "fr", "it", "de")

STATES = {
    "off": ("Off", "Éteint", "Spenta", "Aus"),
    "checking": ("Checking hot/cold", "Contrôle chaud/froid", "Controllo caldo/freddo", "Prüfung warm/kalt"),
    "cleaning_cold": ("Cleaning (cold)", "Nettoyage à froid", "Pulizia a freddo", "Reinigung (kalt)"),
    "loading_cold": ("Loading pellets (cold)", "Chargement à froid", "Carico pellet a freddo", "Pelletbeschickung (kalt)"),
    "start_1_cold": ("Start 1 (cold)", "Démarrage 1 à froid", "Avvio 1 a freddo", "Start 1 (kalt)"),
    "start_2_cold": ("Start 2 (cold)", "Démarrage 2 à froid", "Avvio 2 a freddo", "Start 2 (kalt)"),
    "cleaning_hot": ("Cleaning (hot)", "Nettoyage à chaud", "Pulizia a caldo", "Reinigung (warm)"),
    "loading_hot": ("Loading pellets (hot)", "Chargement à chaud", "Carico pellet a caldo", "Pelletbeschickung (warm)"),
    "start_1_hot": ("Start 1 (hot)", "Démarrage 1 à chaud", "Avvio 1 a caldo", "Start 1 (warm)"),
    "start_2_hot": ("Start 2 (hot)", "Démarrage 2 à chaud", "Avvio 2 a caldo", "Start 2 (warm)"),
    "stabilising": ("Stabilising", "Stabilisation", "Stabilizzazione", "Stabilisierung"),
    **{
        f"power_{n}": (f"Power {n}", f"Puissance {n}", f"Potenza {n}", f"Leistung {n}")
        for n in range(1, 6)
    },
    "diagnostics": ("Diagnostics", "Diagnostic", "Diagnostica", "Diagnose"),
    "on": ("On", "Allumé", "Accesa", "An"),
    "extinguishing": ("Extinguishing", "Extinction", "Spegnimento", "Abschaltung"),
    "cooling": ("Cooling down", "Refroidissement", "Raffreddamento", "Abkühlung"),
    "cleaning_low": ("Cleaning (low pressure)", "Nettoyage basse pression", "Pulizia bassa pressione", "Reinigung (Niederdruck)"),
    "cleaning_high": ("Cleaning (high pressure)", "Nettoyage haute pression", "Pulizia alta pressione", "Reinigung (Hochdruck)"),
    "unlocking_auger": ("Unlocking auger", "Déblocage vis sans fin", "Sblocco coclea", "Förderschnecke lösen"),
    "auto_eco": ("Auto Eco", "Auto Éco", "Auto Eco", "Auto Eco"),
    "standby": ("Standby", "Veille", "Standby", "Standby"),
    "loading_auger": ("Loading auger", "Chargement vis sans fin", "Carico coclea", "Förderschnecke füllen"),
    "waiting_safety_alarms": ("Waiting for safety alarms", "Attente alarmes de sécurité", "Attesa allarmi di sicurezza", "Warten auf Sicherheitsalarme"),
    "unknown": ("Unknown", "Inconnu", "Sconosciuto", "Unbekannt"),
}

ALARMS = {
    "a01": ("Ignition failed", "Allumage raté", "Accensione fallita", "Zündung fehlgeschlagen"),
    "a02": ("No flame", "Pas de flamme", "Assenza fiamma", "Keine Flamme"),
    "a03": ("Tank overheating", "Surchauffe du réservoir", "Surriscaldamento serbatoio", "Überhitzung Behälter"),
    "a04": ("Flue gas too hot", "Température des fumées trop haute", "Temperatura fumi elevata", "Abgastemperatur zu hoch"),
    "a05": ("Flue obstructed or wind", "Conduit obstrué ou vent", "Canna fumaria ostruita o vento", "Rauchrohr verstopft oder Wind"),
    "a06": ("Poor draught", "Mauvais tirage", "Tiraggio insufficiente", "Unzureichender Zug"),
    "a09": ("Flue gas probe fault", "Défaut sonde fumées", "Guasto sonda fumi", "Abgasfühler defekt"),
    "a11": ("Gear motor fault", "Défaut motoréducteur", "Guasto motoriduttore", "Getriebemotor defekt"),
    "a12": ("Gear motor controller fault", "Défaut contrôleur motoréducteur", "Guasto controllo motoriduttore", "Getriebemotor-Steuerung defekt"),
    "a13": ("Motherboard too hot", "Température carte mère trop haute", "Temperatura scheda elevata", "Platinentemperatur zu hoch"),
    "a14": ("Active fault", "Défaut Active", "Guasto Active", "Active-Fehler"),
    "a17": ("Auger jammed", "Bourrage vis sans fin", "Coclea bloccata", "Förderschnecke blockiert"),
    "a18": ("Water too hot", "Température d'eau trop haute", "Temperatura acqua elevata", "Wassertemperatur zu hoch"),
    "a19": ("Water probe fault", "Défaut sonde eau", "Guasto sonda acqua", "Wasserfühler defekt"),
    "a20": ("Auxiliary probe fault", "Défaut sonde auxiliaire", "Guasto sonda ausiliaria", "Zusatzfühler defekt"),
    "a21": ("Pressure switch alarm", "Alarme pressostat", "Allarme pressostato", "Druckschalter-Alarm"),
    "a22": ("Room probe fault", "Défaut sonde ambiante", "Guasto sonda ambiente", "Raumfühler defekt"),
    "a23": ("Brazier closing fault", "Défaut fermeture brasero", "Guasto chiusura braciere", "Fehler Brennschalen-Verschluss"),
}

ALARM_WORD = ("Alarm", "Alarme", "Allarme", "Alarm")


def build(i: int) -> dict:
    """i = index in LANGS."""

    def t(*texts: str) -> str:
        assert len(texts) == len(LANGS), texts
        return texts[i]

    def name(*texts: str) -> dict:
        return {"name": t(*texts)}

    states = {k: v[i] for k, v in STATES.items()}
    states.update({f"alarm_{k}": f"{ALARM_WORD[i]} {k.upper()} – {v[i]}" for k, v in ALARMS.items()})
    alarm_states = {
        "none": t("None", "Aucune", "Nessuno", "Keiner"),
        "safety": STATES["waiting_safety_alarms"][i],
        **{k: f"{k.upper()} – {v[i]}" for k, v in ALARMS.items()},
    }

    return {
        "config": {
            "step": {
                "user": {
                    "title": t("MCZ Maestro stove", "Poêle MCZ Maestro", "Stufa MCZ Maestro", "MCZ-Maestro-Ofen"),
                    "description": t(
                        "Stove paired with the legacy MCZ Maestro app (serial number + remote MAC address). Both are shown in the app under Device list.",
                        "Poêle appairé avec l'ancienne appli MCZ Maestro (numéro de série + adresse MAC remote). Les deux sont visibles dans l'appli, menu Liste des dispositifs.",
                        "Stufa abbinata alla vecchia app MCZ Maestro (numero di serie + indirizzo MAC remote). Entrambi sono visibili nell'app, menu Lista dispositivi.",
                        "Ofen, der mit der alten MCZ-Maestro-App gekoppelt ist (Seriennummer + Remote-MAC-Adresse). Beide stehen in der App unter Geräteliste.",
                    ),
                    "data": {
                        "name": t("Name", "Nom", "Nome", "Name"),
                        "serial": t("Serial number", "Numéro de série", "Numero di serie", "Seriennummer"),
                        "mac": t("Remote MAC address", "Adresse MAC remote", "Indirizzo MAC remote", "Remote-MAC-Adresse"),
                    },
                    "data_description": {
                        "serial": t(
                            "On the stove's rating plate or in the app.",
                            "Sur la plaque du poêle ou dans l'appli.",
                            "Sulla targhetta della stufa o nell'app.",
                            "Auf dem Typenschild des Ofens oder in der App.",
                        ),
                        "mac": t(
                            "12 hex characters, with or without colons.",
                            "12 caractères hexadécimaux, avec ou sans « : ».",
                            "12 caratteri esadecimali, con o senza « : ».",
                            "12 Hexadezimalzeichen, mit oder ohne Doppelpunkte.",
                        ),
                    },
                },
                "reconfigure": {
                    "title": t("Change remote MAC address", "Changer l'adresse MAC remote", "Modifica indirizzo MAC remote", "Remote-MAC-Adresse ändern"),
                    "data": {"mac": t("Remote MAC address", "Adresse MAC remote", "Indirizzo MAC remote", "Remote-MAC-Adresse")},
                },
            },
            "error": {
                "invalid_serial": t("Invalid serial number.", "Numéro de série invalide.", "Numero di serie non valido.", "Ungültige Seriennummer."),
                "invalid_mac": t(
                    "Invalid MAC address (12 hex characters).",
                    "Adresse MAC invalide (12 caractères hexadécimaux).",
                    "Indirizzo MAC non valido (12 caratteri esadecimali).",
                    "Ungültige MAC-Adresse (12 Hexadezimalzeichen).",
                ),
                "cannot_connect": t(
                    "Cannot reach the MCZ cloud.",
                    "Impossible de joindre le cloud MCZ.",
                    "Impossibile raggiungere il cloud MCZ.",
                    "MCZ-Cloud nicht erreichbar.",
                ),
                "no_response": t(
                    "The MCZ cloud answered but the stove did not: check it is online and the serial/MAC pair.",
                    "Le cloud MCZ répond mais pas le poêle : vérifie qu'il est en ligne et le couple série/MAC.",
                    "Il cloud MCZ risponde ma la stufa no: verifica che sia online e la coppia seriale/MAC.",
                    "Die MCZ-Cloud antwortet, der Ofen aber nicht: prüfe, ob er online ist und ob Seriennummer/MAC stimmen.",
                ),
                "unknown": t(
                    "Unexpected error, see the logs.",
                    "Erreur inattendue, voir les journaux.",
                    "Errore imprevisto, vedi i log.",
                    "Unerwarteter Fehler, siehe Protokolle.",
                ),
            },
            "abort": {
                "already_configured": t(
                    "This stove is already configured.",
                    "Ce poêle est déjà configuré.",
                    "Questa stufa è già configurata.",
                    "Dieser Ofen ist bereits eingerichtet.",
                ),
                "reconfigure_successful": t("MAC address updated.", "Adresse MAC mise à jour.", "Indirizzo MAC aggiornato.", "MAC-Adresse aktualisiert."),
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": t("Options", "Options", "Opzioni", "Optionen"),
                    "data": {
                        "scan_interval": t(
                            "Refresh interval (s)",
                            "Intervalle de rafraîchissement (s)",
                            "Intervallo di aggiornamento (s)",
                            "Aktualisierungsintervall (s)",
                        ),
                        "safety_revert": t(
                            "Turn Eco Stop and Dynamic back on automatically",
                            "Réactiver automatiquement Eco Stop et Dynamic",
                            "Riattiva automaticamente Eco Stop e Dynamic",
                            "Eco Stop und Dynamic automatisch wieder aktivieren",
                        ),
                        "safety_delay": t("After (minutes)", "Au bout de (minutes)", "Dopo (minuti)", "Nach (Minuten)"),
                        "safety_overheat": t(
                            "Overheat protection", "Protection surchauffe", "Protezione surriscaldamento", "Überhitzungsschutz"
                        ),
                        "overheat_temp": t(
                            "Room limit: Eco Stop + Dynamic (°C)",
                            "Seuil pièce : Eco Stop + Dynamic (°C)",
                            "Soglia ambiente: Eco Stop + Dynamic (°C)",
                            "Raumgrenze: Eco Stop + Dynamic (°C)",
                        ),
                        "shutdown_temp": t(
                            "Room limit: switch off (°C)",
                            "Seuil pièce : extinction (°C)",
                            "Soglia ambiente: spegnimento (°C)",
                            "Raumgrenze: Abschalten (°C)",
                        ),
                        "safety_notify": t(
                            "Notify when a safety steps in",
                            "Notifier quand une sécurité intervient",
                            "Notifica quando interviene una sicurezza",
                            "Benachrichtigen, wenn eine Sicherung eingreift",
                        ),
                    },
                    "data_description": {
                        "scan_interval": t(
                            "How often the stove is asked for fresh data (15–300 s).",
                            "Fréquence de demande de nouvelles données au poêle (15–300 s).",
                            "Frequenza con cui si chiedono nuovi dati alla stufa (15–300 s).",
                            "Wie oft der Ofen nach neuen Daten gefragt wird (15–300 s).",
                        ),
                        "safety_revert": t(
                            "If Eco Stop stays off or the stove stays in Manual longer than the delay, it is switched back.",
                            "Si Eco Stop reste coupé ou le poêle reste en Manuel plus longtemps que le délai, il est remis.",
                            "Se Eco Stop resta disattivato o la stufa resta in Manuale oltre il ritardo, viene ripristinato.",
                            "Bleibt Eco Stop aus oder der Ofen länger als die Wartezeit auf Manuell, wird zurückgeschaltet.",
                        ),
                        "safety_delay": t("5 to 480 minutes.", "De 5 à 480 minutes.", "Da 5 a 480 minuti.", "5 bis 480 Minuten."),
                        "overheat_temp": t(
                            "At or above this room temperature, Eco Stop and Dynamic are turned back on at once.",
                            "À partir de cette température dans la pièce, Eco Stop et Dynamic sont remis tout de suite.",
                            "Da questa temperatura ambiente, Eco Stop e Dynamic vengono riattivati subito.",
                            "Ab dieser Raumtemperatur werden Eco Stop und Dynamic sofort wieder aktiviert.",
                        ),
                        "shutdown_temp": t(
                            "At or above this room temperature, the stove is switched off. Must be above the previous limit.",
                            "À partir de cette température dans la pièce, le poêle est éteint. Doit être au-dessus du seuil précédent.",
                            "Da questa temperatura ambiente, la stufa viene spenta. Deve superare la soglia precedente.",
                            "Ab dieser Raumtemperatur wird der Ofen ausgeschaltet. Muss über der vorigen Grenze liegen.",
                        ),
                    },
                }
            },
            "error": {
                "shutdown_below_overheat": t(
                    "The switch-off limit must be above the Eco Stop + Dynamic limit.",
                    "Le seuil d'extinction doit être au-dessus du seuil Eco Stop + Dynamic.",
                    "La soglia di spegnimento deve superare la soglia Eco Stop + Dynamic.",
                    "Die Abschaltgrenze muss über der Grenze für Eco Stop + Dynamic liegen.",
                )
            },
        },
        "entity": {
            "climate": {
                "stove": {
                    "state_attributes": {
                        "preset_mode": {
                            "state": {
                                "dynamic": "Dynamic",
                                "manual": t("Manual", "Manuel", "Manuale", "Manuell"),
                            }
                        }
                    }
                }
            },
            "fan": {
                "room_fan": {
                    "name": t("Room fan", "Ventilateur ambiance", "Ventilatore ambiente", "Raumgebläse"),
                    "state_attributes": {"preset_mode": {"state": {"auto": "Auto"}}},
                }
            },
            "select": {"power_level": name("Power level", "Puissance", "Potenza", "Leistungsstufe")},
            "switch": {
                "eco": name("Eco Stop", "Eco Stop", "Eco Stop", "Eco Stop"),
                "chrono": name("Chrono", "Chrono", "Chrono", "Chrono"),
                "silent": name("Silent", "Silence", "Silenzioso", "Leise"),
                "active": name("Active", "Active", "Active", "Active"),
                "sounds": name("Sounds", "Sons", "Suoni", "Töne"),
            },
            "sensor": {
                "state": {"name": t("State", "État", "Stato", "Status"), "state": states},
                "alarm": {"name": t(*ALARM_WORD), "state": alarm_states},
                "ambient_temp": name("Room temperature", "Température ambiante", "Temperatura ambiente", "Raumtemperatur"),
                "fumes_temp": name("Flue gas temperature", "Température des fumées", "Temperatura fumi", "Abgastemperatur"),
                "setpoint": name("Setpoint", "Consigne", "Temperatura impostata", "Solltemperatur"),
                "board_temp": name("Motherboard temperature", "Température carte mère", "Temperatura scheda", "Platinentemperatur"),
                "power": name("Current power", "Puissance actuelle", "Potenza attuale", "Aktuelle Leistung"),
                "fumes_fan_rpm": name("Flue fan speed", "Vitesse extracteur fumées", "Velocità estrattore fumi", "Drehzahl Abgasgebläse"),
                "auger_rpm": name("Auger speed", "Vis sans fin", "Coclea", "Förderschnecke"),
                "auger_rpm_set": name("Auger speed setpoint", "Vis sans fin consigne", "Coclea impostata", "Förderschnecke Soll"),
                "active_live": name("Active", "Active", "Active", "Active"),
                "active_set": name("Active setpoint", "Active consigne", "Active impostato", "Active Soll"),
                "hours_to_service": name("Hours before service", "Heures avant entretien", "Ore alla manutenzione", "Stunden bis zur Wartung"),
                "total_hours": name("Operating time", "Temps de fonctionnement", "Ore di funzionamento", "Betriebsstunden"),
                **{
                    f"power_{n}_hours": name(
                        f"Operating time power {n}",
                        f"Temps en puissance {n}",
                        f"Ore in potenza {n}",
                        f"Betriebsstunden Stufe {n}",
                    )
                    for n in range(1, 6)
                },
                "minutes_to_off": name("Minutes before shutdown", "Minutes avant extinction", "Minuti allo spegnimento", "Minuten bis zur Abschaltung"),
                "ignitions": name("Ignitions", "Allumages", "Accensioni", "Zündungen"),
                "season": {
                    "name": t("Season", "Saison", "Stagione", "Saison"),
                    "state": {
                        "winter": t("Winter", "Hiver", "Inverno", "Winter"),
                        "summer": t("Summer", "Été", "Estate", "Sommer"),
                    },
                },
                "stove_clock": name("Stove clock", "Horloge du poêle", "Orologio stufa", "Ofenuhr"),
                "profile": name("Profile (raw)", "Profil (brut)", "Profilo (grezzo)", "Profil (roh)"),
                "antifreeze": name("Frost protection (raw)", "Hors-gel (brut)", "Antigelo (grezzo)", "Frostschutz (roh)"),
            },
            "binary_sensor": {
                "heating": name("Heating", "En chauffe", "In riscaldamento", "Heizt"),
                "alarm": name(*ALARM_WORD),
                "igniter": name("Igniter", "Bougie", "Candeletta", "Glühzünder"),
                "brazier": name("Brazier to clean", "Brasero à nettoyer", "Braciere da pulire", "Brennschale reinigen"),
                "pellets_empty": name("Pellets empty", "Granulés vides", "Pellet esaurito", "Pellets leer"),
                "cloud": name("MCZ cloud", "Cloud MCZ", "Cloud MCZ", "MCZ-Cloud"),
            },
            "button": {
                "reset_alarm": name("Reset alarm", "Réinitialiser l'alarme", "Reset allarme", "Alarm zurücksetzen"),
                "sync_clock": name("Sync stove clock", "Mettre le poêle à l'heure", "Sincronizza orologio stufa", "Ofenuhr synchronisieren"),
                "refresh": name("Refresh", "Rafraîchir", "Aggiorna", "Aktualisieren"),
            },
        },
        "exceptions": {
            "not_connected": {
                "message": t(
                    "MCZ cloud not connected, try again shortly.",
                    "Cloud MCZ non connecté, réessaie dans un instant.",
                    "Cloud MCZ non connesso, riprova tra poco.",
                    "MCZ-Cloud nicht verbunden, versuche es gleich noch einmal.",
                )
            },
            "no_first_frame": {
                "message": t(
                    "The stove did not answer through the MCZ cloud.",
                    "Le poêle n'a pas répondu via le cloud MCZ.",
                    "La stufa non ha risposto tramite il cloud MCZ.",
                    "Der Ofen hat über die MCZ-Cloud nicht geantwortet.",
                )
            },
            "stale": {
                "message": t(
                    "No data from the stove for {seconds} s.",
                    "Aucune donnée du poêle depuis {seconds} s.",
                    "Nessun dato dalla stufa da {seconds} s.",
                    "Seit {seconds} s keine Daten vom Ofen.",
                )
            },
            "safety_title": {
                "message": t("Stove safety", "Sécurité poêle", "Sicurezza stufa", "Ofen-Sicherheit")
            },
            "safety_eco_restored": {
                "message": t(
                    "Eco Stop had been off for {minutes} min: turned back on.",
                    "Eco Stop était coupé depuis {minutes} min : il a été réactivé.",
                    "Eco Stop era disattivato da {minutes} min: è stato riattivato.",
                    "Eco Stop war seit {minutes} min aus: wieder aktiviert.",
                )
            },
            "safety_dynamic_restored": {
                "message": t(
                    "The stove had been in Manual for {minutes} min: back to Dynamic.",
                    "Le poêle était en Manuel depuis {minutes} min : retour en Dynamic.",
                    "La stufa era in Manuale da {minutes} min: ritorno a Dynamic.",
                    "Der Ofen war seit {minutes} min auf Manuell: zurück auf Dynamic.",
                )
            },
            "safety_overheat": {
                "message": t(
                    "Room at {temperature} °C (limit {limit} °C): Eco Stop and Dynamic turned back on.",
                    "Pièce à {temperature} °C (seuil {limit} °C) : Eco Stop et Dynamic réactivés.",
                    "Ambiente a {temperature} °C (soglia {limit} °C): Eco Stop e Dynamic riattivati.",
                    "Raum bei {temperature} °C (Grenze {limit} °C): Eco Stop und Dynamic wieder aktiviert.",
                )
            },
            "safety_shutdown": {
                "message": t(
                    "Room at {temperature} °C (limit {limit} °C): stove switched off.",
                    "Pièce à {temperature} °C (seuil {limit} °C) : poêle éteint.",
                    "Ambiente a {temperature} °C (soglia {limit} °C): stufa spenta.",
                    "Raum bei {temperature} °C (Grenze {limit} °C): Ofen ausgeschaltet.",
                )
            },
        },
    }


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    (ROOT / "translations").mkdir(exist_ok=True)
    _write(ROOT / "strings.json", build(0))
    for i, lang in enumerate(LANGS):
        _write(ROOT / "translations" / f"{lang}.json", build(i))


if __name__ == "__main__":
    main()
