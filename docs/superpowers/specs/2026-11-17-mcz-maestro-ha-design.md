# MCZ Maestro (ancienne appli) — intégration Home Assistant

Date : 2026-11-17 · Statut : validé à l'oral, en relecture

## 1. Objectif

Piloter et surveiller depuis Home Assistant (HAOS) le poêle à granulés MCZ
équipé du module **Maestro première génération** (appli historique « MCZ Maestro »,
appairage par n° de série + adresse MAC), avec tout ce que montre l'appli officielle :
marche/arrêt, consigne, mode Auto/Manuel, puissance, ventilateur, Éco, Chrono, écran Info.

L'intégration existante `Robbe-B/maestro_mcz` ne couvre que la nouvelle appli (compte MCZ) :
elle ne convient pas à ce poêle.

## 2. Décisions

| Sujet | Choix |
|---|---|
| Connexion | Cloud MCZ uniquement (`http://app.mcz.it:9000`, socket.io), comme l'appli |
| Implémentation | Intégration native, client socket.io maison sur aiohttp, **aucune dépendance externe** |
| Interface | Entités HA + carte Lovelace `custom:mcz-maestro-card` embarquée |
| Distribution | Dépôt GitHub `Alardware/mcz-maestro`, installable comme dépôt perso HACS |
| Domaine | `mcz_maestro` |
| Langues | Français (principal) + anglais |

## 3. Protocole (faits issus de la rétro-ingénierie communautaire, code réécrit)

### 3.1 Transport
- Serveur socket.io : `http://app.mcz.it:9000`, chemin `/socket.io/`.
- Version supposée socket.io 2 (Engine.IO v3). Le client négocie : websocket EIO=3,
  puis websocket EIO=4, puis long-polling EIO=3 en dernier recours.
- Engine.IO : paquets `0` open (JSON : sid, pingInterval, pingTimeout), `2` ping, `3` pong,
  `4` message. Socket.IO : `40` connexion namespace `/`, `42[...]` événement.
- Keep-alive : en v3 le client envoie `2` toutes les `pingInterval` ms ; en v4 il répond `3`
  aux `2` du serveur. Le client gère les deux.

### 3.2 Messages applicatifs
- À la connexion : `emit("join", {"serialNumber", "macAddress", "type": "Android-App"})`.
- Requête : `emit("chiedo", {"serialNumber", "macAddress", "tipoChiamata": 1, "richiesta": <cmd>})`.
- Réponse : événement `rispondo` → `{"stringaRicevuta": "<trame>"}`.
- Trame = champs séparés par `|`, champ 0 = type (`01` info, `00` paramètres, `0A` alarmes,
  `PING`…), autres champs en hexadécimal. Seul le type `01` est exploité ; le reste est journalisé.
- MAC normalisée : majuscules, sans `:` ni `-` (12 hex). N° de série : chiffres uniquement.

### 3.3 Trame Info (`C|RecuperoInfo` → `01|…`)

| Idx | Donnée | Conversion |
|---|---|---|
| 1 | État du poêle | code (table 3.5) |
| 2 | Ventilateur ambiance | 0 arrêt, 1–5, 6 auto |
| 5 | T° fumées | °C entier |
| 6 | T° ambiante | ÷ 2 |
| 10 | Bougie | 0 off, ≠0 on |
| 11 | Active consigne | entier |
| 12 | RPM extracteur fumées | entier |
| 13 | RPM vis sans fin consigne | entier |
| 14 | RPM vis sans fin réel | entier |
| 17 | Brasero | 0 OK, ≠0 à nettoyer |
| 18 | Profil | brut (lecture seule, voir §8) |
| 20 | Mode Active | 0/1 |
| 21 | Active réel | entier |
| 22 | Régulation | 0 manuel, 1 auto |
| 23 | Éco | 0/1 |
| 24 | Silence | 0/1 |
| 25 | Chrono | 0/1 |
| 26 | Consigne | ÷ 2 |
| 28 | T° carte mère | ÷ 2 |
| 29 | Puissance réelle | 11–15 → 1–5 |
| 32–36 | Horloge poêle h, min, j, mois, année | entiers |
| 37 | Temps de fonctionnement total | secondes → heures |
| 38–42 | Temps en puissance 1 à 5 | secondes → heures |
| 43 | Heures avant entretien | entier |
| 44 | Minutes avant extinction | entier |
| 45 | Nombre d'allumages | entier |
| 46 | Active – T° | entier |
| 47 | Capteur granulés | 0 absent, 10 OK, 11 vide |
| 49 | Sons | 0/1 |
| 51 | Saison | 0 hiver, 1 été |
| 60 | Antigel | brut (lecture seule, voir §8) |

Champs absents ou non hexadécimaux → valeur `None`, jamais d'exception.

### 3.4 Commandes (`C|WriteParametri|<id>|<valeur>` sauf mention)

| Action | Id | Valeur |
|---|---|---|
| Marche / arrêt | 34 | 1 / 40 |
| Consigne | 42 | °C × 2 |
| Puissance | 36 | 1–5 |
| Ventilateur ambiance | 37 | 0–5, 6 = auto |
| Régulation Auto / Manuel | 40 | 1 / 0 |
| Éco | 41 | 0/1 |
| Active | 35 | 0/1 |
| Silence | 45 | 0/1 |
| Sons | 50 | 0/1 |
| Chrono | 1111 | 0/1 |
| Reset alarme | 1 | 255 |
| Synchro heure | `C|SalvaDataOra|ddmmYYYYHHMM` | heure HA |
| Rafraîchir | `C|RecuperoInfo` | — |

Jamais envoyées : `C|Diagnostica|…`, réglages usine, menu technique.

### 3.5 États (idx 1)
0 Éteint · 1 Contrôle chaud/froid · 2 Nettoyage à froid · 3 Chargement à froid ·
4 Démarrage 1 à froid · 5 Démarrage 2 à froid · 6 Nettoyage à chaud · 7 Chargement à chaud ·
8 Démarrage 1 à chaud · 9 Démarrage 2 à chaud · 10 Stabilisation · 11–15 Puissance 1–5 ·
30 Diagnostic · 31 Allumé · 40 Extinction · 41 Refroidissement · 42 Nettoyage basse pression ·
43 Nettoyage haute pression · 44 Déblocage vis sans fin · 45 Auto Éco · 46 Veille ·
48 Diagnostic · 49 Chargement vis sans fin · 50–67 Alarmes A01…A23 · 69 Attente alarmes sécurité.

Alarmes : 50 A01 allumage raté · 51 A02 pas de flamme · 52 A03 surchauffe réservoir ·
53 A04 fumées trop chaudes · 54 A05 conduit obstrué/vent · 55 A06 mauvais tirage ·
56 A09 sonde fumées · 57 A11 motoréducteur · 58 A13 carte mère trop chaude ·
59 A14 défaut Active · 60 A18 eau trop chaude · 61 A19 sonde eau · 62 A20 sonde auxiliaire ·
63 A21 pressostat · 64 A22 sonde ambiante · 65 A23 fermeture brasero ·
66 A12 contrôleur motoréducteur · 67 A17 bourrage vis sans fin.

« En marche » = états 1–15, 31, 40–43. « En chauffe » = 10–15, 31.

## 4. Architecture

```
custom_components/mcz_maestro/
  __init__.py          setup/unload, enregistre la carte (static path + extra JS)
  manifest.json        iot_class cloud_push, aucune requirement
  const.py             domaine, clés, défauts
  socketio_client.py   mini client Engine.IO/Socket.IO (ws v3/v4 + polling v3), reconnexion
  protocol.py          décodage trame → MaestroState (dataclass), fabrique des commandes, tables
  api.py               MaestroCloud : join, request_info, send_command, file 1 cmd/s
  coordinator.py       DataUpdateCoordinator : push + RecuperoInfo périodique, fraîcheur
  config_flow.py       série + MAC + nom, test réel ; options : intervalle ; reconfigure
  entity.py            entité de base (device_info, disponibilité)
  climate.py fan.py select.py switch.py sensor.py binary_sensor.py button.py
  diagnostics.py       série et MAC masqués
  strings.json translations/fr.json translations/en.json icons.json
  frontend/mcz-maestro-card.js
hacs.json · README.md · tests/
```

Chaque module a une seule responsabilité : `socketio_client` ignore tout de MCZ, `protocol`
ignore le réseau, `api` assemble les deux, `coordinator` fait le lien avec HA.

### Flux
1. Setup → `MaestroCloud.start()` : connexion, `join`, `RecuperoInfo`.
2. Chaque `rispondo` de type `01` → `protocol.parse_info()` → `coordinator.async_set_updated_data()`.
3. Toutes les N s (défaut 30, réglable 15–300) → `RecuperoInfo`.
4. Commande d'une entité → file d'attente (≥ 1 s entre envois) → `RecuperoInfo` 2 s après.
5. Passage en état d'alarme (code 50–69) → événement `mcz_maestro_alarm`
   (`code`, `label`, `device_id`), une fois par nouvelle alarme.

## 5. Entités (nom d'appareil par défaut « Poêle »)

| Plateforme | Entité | Source / commande |
|---|---|---|
| climate | Poêle : HEAT/OFF, consigne 5–35 °C pas 0,5, T° ambiante, presets `auto`/`manual`, hvac_action heating/idle/off | 1, 6, 22, 26 / 34, 42, 40 |
| fan | Ventilateur ambiance : 5 vitesses + preset `auto`, arrêt | 2 / 37 |
| select | Puissance 1–5 | 29 / 36 |
| switch | Éco, Chrono, Silence, Active, Sons | 23, 25, 24, 20, 49 |
| sensor | État (enum), T° fumées, T° carte mère, consigne, RPM extracteur, vis sans fin réel, vis sans fin consigne, Active réel, Active consigne, puissance réelle, temps total (h), temps P1–P5 (h, désactivés par défaut), heures avant entretien, minutes avant extinction, nb allumages, code alarme, profil (brut, diagnostic), antigel (brut, diagnostic), saison | §3.3 |
| binary_sensor | En chauffe, Bougie, Alarme (problem), Brasero à nettoyer, Granulés vides (si capteur présent) | 1, 10, 17, 47 |
| button | Reset alarme, Synchro heure, Rafraîchir | §3.4 |

Entités techniques en catégorie *diagnostic*. Disponibilité : connexion OK et dernière trame
< 3 min.

## 6. Carte `custom:mcz-maestro-card`

- Config : `entity: climate.poele` (seule clé obligatoire), `name` optionnel.
- Retrouve les entités sœurs via `hass.entities` (même `device_id`, `platform: mcz_maestro`,
  `translation_key`).
- Cadran circulaire : T° ambiante en grand, consigne dessous, arc indiquant l'écart, −/+ 0,5 °C
  (envoi groupé après 1 s sans clic).
- Bouton marche/arrêt, état en clair, pastilles Éco / Chrono / Auto–Manuel.
- Puissance 1–5 (segments, actifs en Manuel), ventilateur 1–5 / Auto.
- Bloc « Infos » repliable : fumées, vis sans fin, extracteur, Active, heures, entretien.
- Bandeau d'alarme rouge avec code, libellé et bouton reset.
- Style Loggia, variables CSS du thème HA (clair/sombre), 360 px de large minimum.
- Design original : ni logo ni charte MCZ.
- Servie par l'intégration (`/mcz_maestro/mcz-maestro-card.js?v=<version>`), déclarée dans le
  sélecteur de cartes.

## 7. Erreurs

- Cloud injoignable / coupure : reconnexion 5 s, 10 s, 20 s… plafonnée à 5 min.
- Config flow : `cannot_connect` (cloud), `no_response` (poêle hors ligne ou série/MAC faux,
  20 s sans trame `01`), `invalid_serial`, `invalid_mac`, `already_configured`.
- Commande hors connexion → `HomeAssistantError` lisible.
- Trame illisible → ignorée, log debug.
- Série + MAC = clé d'accès au poêle : stockés dans l'entrée de config HA, masqués dans les
  diagnostics et les logs, absents du dépôt.

## 8. Points à valider sur le vrai poêle

1. Version socket.io réellement servie par `app.mcz.it:9000`.
2. Valeurs du profil (idx 18) affiché « DYNAMIC » → éventuel select ensuite.
3. « HEURES AU SERVICE 660 » = temps total (idx 37) ou heures avant entretien (idx 43).
4. Signification exacte de l'antigel (idx 60, commande 154) → éventuel interrupteur ensuite.

## 9. Tests

- `pytest` + `pytest-homeassistant-custom-component`.
- Faux serveur cloud MCZ (aiohttp) en Engine.IO v3 **et** v4, websocket et polling.
- Trame de référence reconstituée depuis l'écran Info de l'appli (fumées 120, ambiante 18,
  consigne 19, extracteur 1886, vis 1350/1400, Active 166/160, carte mère 23, ventilo auto,
  Auto ON, Éco ON, puissance 5).
- Couverture : négociation de version, keep-alive, reconnexion, décodage, chaque commande,
  config flow (succès + chaque erreur), chaque entité, événement d'alarme, diagnostics masqués.
- Carte : rendu navigateur headless avec faux `hass`, clair/sombre, 390 px et desktop,
  clics → appels de service attendus.

## 10. Hors périmètre

Mode local (Wi-Fi du poêle), édition des plages Chrono, menu technique/diagnostic,
réglages usine, modèles hydro (puffer, chaudière, vanne 3 voies).
