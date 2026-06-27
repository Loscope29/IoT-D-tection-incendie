"""
Connecteur Kafka -> InfluxDB
=============================
Consomme le topic Kafka 'fire-telemetry' et écrit les métriques dans InfluxDB.
"""

import json
import logging
import sys
import time
from kafka import KafkaConsumer
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kafka_to_influx")

# Configuration Kafka
KAFKA_BOOTSTRAP_SERVERS = ["localhost:29092"]
KAFKA_TOPIC = "fire-telemetry"

# Configuration InfluxDB
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "fire-detection-admin-token"
INFLUXDB_ORG = "fire-detection"
INFLUXDB_BUCKET = "fire-detection-data"

# Initialisation du client InfluxDB
log.info("Connexion à InfluxDB...")
try:
    influx_client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG
    )
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    log.info("✅ Connecté à InfluxDB avec succès.")
except Exception as e:
    log.error(f"❌ Échec de connexion à InfluxDB : {e}")
    sys.exit(1)

# Initialisation du consommateur Kafka avec reconnexion automatique
consumer = None
log.info("Connexion à Kafka...")
for attempt in range(1, 6):
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='latest',
            group_id='influxdb-bridge-group'
        )
        log.info(f"✅ Connecté à Kafka. Écoute du topic : {KAFKA_TOPIC}")
        break
    except Exception as e:
        log.warning(f"Tentative {attempt}/5 : Impossible de se connecter à Kafka ({e}). Nouvelle tentative dans 3s...")
        time.sleep(3)

if not consumer:
    log.error("❌ Échec critique de connexion à Kafka.")
    sys.exit(1)


# Boucle principale de consommation et d'écriture
try:
    for message in consumer:
        payload = message.value
        
        # Le payload dans Kafka contient les champs : mqtt_topic, timestamp, location, data_type, value
        # La clé 'value' contient l'objet telemetry complet
        telemetry = payload.get("value")
        if not telemetry or not isinstance(telemetry, dict):
            continue
            
        location = telemetry.get("location", {})
        readings = telemetry.get("readings", {})
        dev_eui = telemetry.get("dev_eui", "unknown")
        
        site = location.get("site", "unknown")
        batiment = location.get("batiment", "unknown")
        salle = location.get("salle", "unknown")
        machine = location.get("machine", "unknown")

        # Extraction des métriques
        smoke_level = float(readings.get("smoke_level", 0.0))
        temperature = float(readings.get("temperature", 20.0))
        battery_level = int(readings.get("battery_level", 100))
        status = readings.get("status", "active")
        siren_on = 1 if readings.get("siren", "OFF") == "ON" else 0
        light_on = 1 if readings.get("light", "OFF") == "ON" else 0
        
        # Création du point InfluxDB
        point = Point("sensor_data") \
            .tag("dev_eui", dev_eui) \
            .tag("site", site) \
            .tag("batiment", batiment) \
            .tag("salle", salle) \
            .tag("machine", machine) \
            .field("smoke_level", smoke_level) \
            .field("temperature", temperature) \
            .field("battery_level", battery_level) \
            .field("status", status) \
            .field("siren", siren_on) \
            .field("light", light_on)

        try:
            # Écriture dans InfluxDB
            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
            log.info(
                f"[InfluxDB] Écrit -> {site}/{batiment}/{salle}/{machine} | "
                f"smoke={smoke_level} ppm | temp={temperature}°C | battery={battery_level}%"
            )
        except Exception as e:
            log.error(f"Erreur d'écriture dans InfluxDB : {e}")

except KeyboardInterrupt:
    log.info("Arrêt du connecteur demandé.")
finally:
    if consumer:
        consumer.close()
    if influx_client:
        influx_client.close()
    log.info("Connecteur InfluxDB arrêté proprement.")
