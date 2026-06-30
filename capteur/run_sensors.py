"""
Lance plusieurs capteurs en parallèle pour simuler un site complet.
Chaque capteur tourne dans son propre thread.

Usage :
    python run_sensors.py
    python run_sensors.py --scenario incendie    # force smoke=True sur salle_1
    python run_sensors.py --scenario batterie    # force battery=disconnected
"""

import threading
import time
import argparse
import logging
from sensor import FireSensor, SensorLocation

log = logging.getLogger("run_sensors")

# ─── Définition du parc de capteurs ────────────────────────────────────────
# Modifier ici pour ajouter / enlever des capteurs
SENSORS = [
    {
        "dev_eui":  "AA00000000000001",
        "site":     "paris",
        "batiment": "batiment_A",
        "salle":    "salle_1",
        "machine":  "detecteur_01",
        "interval": 10,   # uplink toutes les 10s (simulation rapide)
    },
    {
        "dev_eui":  "AA00000000000002",
        "site":     "paris",
        "batiment": "batiment_A",
        "salle":    "salle_2",
        "machine":  "detecteur_01",
        "interval": 10,
    },
    {
        "dev_eui":  "AA00000000000003",
        "site":     "paris",
        "batiment": "batiment_B",
        "salle":    "salle_1",
        "machine":  "detecteur_01",
        "interval": 15,
    },
    {
        "dev_eui":  "AA00000000000004",
        "site":     "lyon",
        "batiment": "batiment_A",
        "salle":    "salle_1",
        "machine":  "detecteur_01",
        "interval": 10,
    },
]

# ─── Scénarios de test ──────────────────────────────────────────────────────
def apply_scenario(sensors: list[FireSensor], scenario: str):
    """Force un état particulier sur certains capteurs pour les tests."""
    time.sleep(2)   # laisser les capteurs démarrer

    if scenario == "incendie":
        # Premier capteur en alarme incendie
        sensors[0].fire_triggered = True
        log.warning("SCÉNARIO : incendie forcé sur " + sensors[0].dev_eui)

    elif scenario == "batterie":
        # Deuxième capteur avec batterie faible
        sensors[1].low_battery_triggered = True
        log.warning("SCÉNARIO : batterie faible forcée sur " + sensors[1].dev_eui)

    elif scenario == "inactif":
        # Troisième capteur inactif
        sensors[2].state.status = "inactive"
        log.warning("SCÉNARIO : capteur inactif sur " + sensors[2].dev_eui)

    elif scenario == "multi":
        # Plusieurs incidents simultanés
        sensors[0].fire_triggered = True
        sensors[1].low_battery_triggered = True
        sensors[3].fire_triggered = True
        log.warning("SCÉNARIO : incidents multiples")

    elif scenario == "apocalypse":
        log.warning("SCÉNARIO : APOCALYPSE - PIRE CAS POSSIBLE SUR TOUS LES CAPTEURS")
        for s in sensors:
            s.fire_triggered = True
            s.low_battery_triggered = True
            s.state.status = "inactive"



def main():
    parser = argparse.ArgumentParser(description="Lance le parc de capteurs simulés")
    parser.add_argument(
        "--scenario",
        choices=["incendie", "batterie", "inactif", "multi", "apocalypse"],
        default=None,
        help="Scénario à simuler"
    )
    args = parser.parse_args()

    # Créer les instances capteurs
    sensor_instances = []
    for cfg in SENSORS:
        s = FireSensor(
            dev_eui  = cfg["dev_eui"],
            location = SensorLocation(
                site     = cfg["site"],
                batiment = cfg["batiment"],
                salle    = cfg["salle"],
                machine  = cfg["machine"],
            ),
            interval = cfg["interval"],
        )
        sensor_instances.append(s)

    # Lancer chaque capteur dans un thread dédié
    threads = []
    for sensor in sensor_instances:
        t = threading.Thread(target=sensor.run, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.3)   # décalage léger pour éviter les collisions MQTT

    # Appliquer le scénario si demandé
    if args.scenario:
        scenario_thread = threading.Thread(
            target=apply_scenario,
            args=(sensor_instances, args.scenario),
            daemon=True
        )
        scenario_thread.start()

    log.info(f"{len(sensor_instances)} capteurs démarrés.")
    if args.scenario:
        log.info(f"Scénario actif : {args.scenario}")

    # Maintenir le processus principal en vie
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Arrêt de tous les capteurs.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    main()