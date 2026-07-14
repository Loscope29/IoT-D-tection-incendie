"""
Bridge MQTT -> Kafka pour la détection d'incendie
==================================================
Souscrit à 'fire/#' sur HiveMQ et envoie les messages dans Kafka.
"""

import json
import logging
import time
import sys
import os
from kafka import KafkaProducer
from kafka.errors import KafkaError
import paho.mqtt.client as mqtt

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mqtt_to_kafka")

# Configuration des brokers
def load_env(file_path=".env"):
    current_dir = os.path.abspath(os.path.dirname(__file__)) if '__file__' in globals() else os.getcwd()
    while current_dir:
        env_path = os.path.join(current_dir, file_path)
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, val = line.split('=', 1)
                            os.environ[key.strip()] = val.strip()
            return True
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    return False

# Chargement du fichier .env
load_env()

MQTT_HOST = os.environ.get("VITE_HIVEMQ_HOST", "localhost")
MQTT_PORT = int(os.environ.get("VITE_HIVEMQ_PORT", 1883))
MQTT_USER = os.environ.get("VITE_HIVEMQ_USER")
MQTT_PASS = os.environ.get("VITE_HIVEMQ_PASSWORD")
MQTT_TOPIC_SUB = "fire/#"

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092").split(",")

# Initialisation du producteur Kafka avec reconnexion automatique
producer = None
log.info("Connexion à Kafka en cours...")
for attempt in range(1, 6):
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=5000,
        )
        log.info("✅ Connecté à Kafka avec succès.")
        break
    except KafkaError as e:
        log.warning(f"Tentative {attempt}/5 : Impossible de se connecter à Kafka ({e}). Nouvelle tentative dans 3s...")
        time.sleep(3)

if not producer:
    log.error("❌ Échec critique de connexion à Kafka. Veuillez vérifier que le conteneur Kafka est bien lancé et accessible sur le port 29092.")
    sys.exit(1)


# Callback de connexion MQTT
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info(f"✅ Connecté à HiveMQ ({MQTT_HOST}:{MQTT_PORT})")
        client.subscribe(MQTT_TOPIC_SUB, qos=1)
        log.info(f"Souscrit au topic MQTT global : {MQTT_TOPIC_SUB}")
    else:
        log.error(f"Erreur de connexion à HiveMQ (code {rc})")

# Callback de déconnexion MQTT
def on_disconnect(client, userdata, rc):
    log.warning(f"Déconnecté de HiveMQ (code {rc}). Reconnexion auto...")

# Callback de réception de message MQTT et routage vers Kafka
def on_message(client, userdata, msg):
    topic = msg.topic
    raw_payload = msg.payload.decode('utf-8', errors='replace')
    
    # Extraction des infos du topic : fire/{site}/{batiment}/{salle}/{machine}/{type}
    parts = topic.split("/")
    if len(parts) < 6:
        return
        
    data_type = parts[-1]
    site = parts[1]
    batiment = parts[2]
    salle = parts[3]
    machine = parts[4]

    try:
        val = json.loads(raw_payload)
    except json.JSONDecodeError:
        val = raw_payload

    # Préparation du payload structuré pour Kafka
    kafka_payload = {
        "mqtt_topic": topic,
        "timestamp": time.time(),
        "location": {
            "site": site,
            "batiment": batiment,
            "salle": salle,
            "machine": machine
        },
        "data_type": data_type,
        "value": val
    }

    # Choix du topic Kafka de destination selon le type de donnée
    if data_type == "telemetry":
        kafka_topic = "fire-telemetry"
    elif data_type in ("smoke", "smoke_level", "temperature"):
        kafka_topic = "fire-alerts"
    elif data_type in ("battery", "battery_level", "status"):
        kafka_topic = "fire-diagnostics"
    else:
        kafka_topic = "fire-others"

    try:
        future = producer.send(kafka_topic, kafka_payload)
        record_metadata = future.get(timeout=2)
        log.info(f"[{data_type}] {site}/{batiment}/{salle}/{machine} -> Kafka topic '{kafka_topic}' (offset {record_metadata.offset})")
    except Exception as e:
        log.error(f"Erreur lors de l'envoi vers Kafka : {e}")

# Initialisation du client MQTT
mqtt_client = mqtt.Client(client_id="hivemq-to-kafka-bridge")
if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
if MQTT_PORT == 8883 or (MQTT_PORT != 1883 and not ("localhost" in MQTT_HOST or "127.0.0.1" in MQTT_HOST or "hivemq" in MQTT_HOST)):
    mqtt_client.tls_set()
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

try:
    log.info(f"Connexion à HiveMQ...")
    connected = False
    while not connected:
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            connected = True
        except Exception as e:
            log.warning(f"Impossible de se connecter au broker ({e}). Nouvelle tentative dans 5 secondes...")
            time.sleep(5)
    mqtt_client.loop_forever()
except KeyboardInterrupt:
    log.info("Arrêt du pont MQTT -> Kafka demandé.")
finally:
    if producer:
        producer.close()
    mqtt_client.disconnect()
    log.info("Pont arrêté proprement.")
