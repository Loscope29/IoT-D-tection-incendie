import json
import random
import time
import uuid
import argparse
import logging
from datetime import datetime, timezone
from dataclasses import dataclass

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S"
)

log = logging.getLogger("sensor")

import os

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

CHIRPSTACK_HOST = os.environ.get("VITE_HIVEMQ_HOST", "localhost")
CHIRPSTACK_PORT = int(os.environ.get("VITE_HIVEMQ_PORT", 1883))
HIVEMQ_USER = os.environ.get("VITE_HIVEMQ_USER")
HIVEMQ_PASSWORD = os.environ.get("VITE_HIVEMQ_PASSWORD")
APPLICATION_ID = "fire-detection-app"


def uplink_topic(dev_eui: str) -> str:
    return f"application/{APPLICATION_ID}/device/{dev_eui}/event/up"

def downlink_topic(dev_eui: str) -> str:
    return f"application/{APPLICATION_ID}/device/{dev_eui}/command/down"

# Modele de donnees
@dataclass
class SensorLocation:
    site : str
    batiment : str
    salle : str
    machine : str

@dataclass
class SensorState:
    smoke_level : float = 10.0   # en ppm (normal: 5-15, alerte > 50)
    temperature : float = 20.0   # en °C (normal: 18-25, alerte > 60)
    battery_level : int = 100    # en % (0-100)
    status : str = "active"
    siren : str = "OFF"
    light : str = "OFF"

# Capteur de donnees simule
class FireSensor:
    def __init__(self, dev_eui: str, location: SensorLocation, interval: int = 30):
        self.dev_eui = dev_eui
        self.location = location
        self.interval = interval
        self.state = SensorState(
            smoke_level = round(random.uniform(5.0, 10.0), 1),
            temperature = round(random.uniform(19.0, 23.0), 1),
            battery_level = random.randint(90, 100)
        )
        self.fire_triggered = False
        self.low_battery_triggered = False
        self.frame_counter = 0
        self._client = mqtt.Client(client_id=f"sensor-{self.dev_eui}")
        if HIVEMQ_USER and HIVEMQ_PASSWORD:
            self._client.username_pw_set(HIVEMQ_USER, HIVEMQ_PASSWORD)
        if CHIRPSTACK_PORT == 8883 or (CHIRPSTACK_PORT != 1883 and not ("localhost" in CHIRPSTACK_HOST or "127.0.0.1" in CHIRPSTACK_HOST or "hivemq" in CHIRPSTACK_HOST)):
            self._client.tls_set()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    # Connexion au broker MQTT
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info(f"Connected to MQTT broker at {CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}")
            topic = downlink_topic(self.dev_eui)
            client.subscribe(topic, qos=1)
            log.info(f"Subscribed to downlink topic: {topic}")
        else:
            log.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        log.warning(f"[{self.dev_eui}] Disconnected from MQTT broker with return code {rc}")

    # Reception des messages MQTT pour les commandes de downlink
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            command = payload.get("command") or payload.get("cmd")
            value = payload.get("value", "").upper()
            if command == "siren" and value in ["ON", "OFF"]:
                self.state.siren = value
                log.info(f"[{self.dev_eui}] Siren set to {value}")
            elif command == "light" and value in ["ON", "OFF"]:
                self.state.light = value
                log.info(f"[{self.dev_eui}] Light set to {value}")
            else:
                log.warning(f"[{self.dev_eui}] Unknown command received: {command}")
        except json.JSONDecodeError:
            log.error(f"[{self.dev_eui}] Failed to decode JSON payload: {msg.payload.decode()}")

    # Simulation des donnees
    def _simulate_readings(self):
        # Simulation batterie
        if self.low_battery_triggered:
            # Chute rapide de la batterie pour test alerte
            if self.state.battery_level > 12:
                self.state.battery_level = 12
            else:
                self.state.battery_level = max(0, self.state.battery_level - 1)
        else:
            # Décharge lente en fonctionnement normal
            if random.random() < 0.05:
                self.state.battery_level = max(0, self.state.battery_level - 1)

        # Simulation fumée (smoke_level) et température
        if self.fire_triggered:
            # Incendie forcé : hausse rapide
            self.state.smoke_level = min(200.0, round(self.state.smoke_level + random.uniform(8.0, 15.0), 1))
            self.state.temperature = min(120.0, round(self.state.temperature + random.uniform(3.0, 7.0), 1))
        else:
            # Mode normal : fluctuations légères
            self.state.smoke_level = max(0.0, min(15.0, round(self.state.smoke_level + random.uniform(-0.5, 0.5), 1)))
            self.state.temperature = max(15.0, min(27.0, round(self.state.temperature + random.uniform(-0.2, 0.2), 1)))

        # Récupération automatique du statut
        if self.state.battery_level == 0:
            self.state.status = "dead"
        elif not self.fire_triggered and random.random() < 0.002:
            self.state.status = "inactive"
        else:
            self.state.status = "active"

    # Construction du payload
    def _build_uplink_payload(self) -> dict:
        self.frame_counter += 1
        return {
            "deduplicationId": str(uuid.uuid4()),
            "time": datetime.now(timezone.utc).isoformat(),
            "deviceInfo": {
                "applicationId": APPLICATION_ID,
                "applicationName": "fire-detection",
                "deviceName": f"fire-sensor-{self.dev_eui}[-4:]",
                "devEui": self.dev_eui,
                "deviceProfileName": "LoRaWan-ClassC-EU868",
                "tags": {
                    "site": self.location.site,
                    "batiment": self.location.batiment,
                    "salle": self.location.salle,
                    "machine": self.location.machine,
                },
            },
            "dr": 5,
            "fCnt": self.frame_counter,
            "fPort": 1,
            "object": {
                "smoke_level": self.state.smoke_level,
                "temperature": self.state.temperature,
                "battery_level": self.state.battery_level,
                "status": self.state.status,
                "siren": self.state.siren,
                "light": self.state.light,
                "manual_trigger": self.fire_triggered,
            },
            "rxInfo": [{
                "gatewayId": "gateway-sim-001",
                "rssi": random.randint(-110, -60),
                "snr": round(random.uniform(3.0, 10.0), 1),
                "location": {"latitude": 48.8666, "longitude": 2.3533},
            }],
            "txInfo": {
                "frequency": 868100000,
                "modulation": {
                    "lora": {
                        "bandwidth": 125000,
                        "spreadingFactor": 7,
                        "codeRate": "CR_4_5",
                    }
                },
            },
        }
    
    def _send_uplink(self):
        payload = self._build_uplink_payload()
        topic = uplink_topic(self.dev_eui)

        result = self._client.publish(topic, json.dumps(payload), qos=1)
        log.info(
            f"[{self.dev_eui}] -> Uplink #{self.frame_counter} | "
            f"smoke={self.state.smoke_level} ppm | temp={self.state.temperature}°C | "
            f"battery={self.state.battery_level}% | siren={self.state.siren} | light={self.state.light}"
        )

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            log.error(f"[{self.dev_eui}] Erreur publication MQTT : {result.rc}")

    def run(self):
        log.info(
            f"\n{'='*60}\n"
            f" Capteur : {self.dev_eui}\n"
            f"  Site   : {self.location.site}/{self.location.batiment}/"
            f"{self.location.salle}/{self.location.machine}\n"
            f" Classe : LoRaWan Class C\n"
            f" Intervalle uplink : {self.interval}s\n"
            f"{'='*60}"
        )

        connected = False
        while not connected:
            try:
                log.info(f"[{self.dev_eui}] Tentative de connexion au broker MQTT {CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}...")
                self._client.connect(CHIRPSTACK_HOST, CHIRPSTACK_PORT, keepalive=60)
                connected = True
            except Exception as e:
                log.warning(f"[{self.dev_eui}] Impossible de se connecter au broker ({e}). Nouvelle tentative dans 5 secondes...")
                time.sleep(5)
                
        self._client.loop_start()

        time.sleep(1)

        try:
            while True:
                if self.state.status != 'dead':
                    self._simulate_readings()
                    self._send_uplink()
                else:
                    log.warning(f"[{self.dev_eui}] Capteur HORS SERVICE (batterie vide)")

                time.sleep(self.interval)
        
        except KeyboardInterrupt:
            log.info(f"[{self.dev_eui}] Arret du capteur")
        finally:
            self._client.loop_stop()
            self._client.disconnect()


def parse_args():
    parser = argparse.ArgumentParser(description="Capteur incendie LoRaWAN simulé")
    parser.add_argument("--dev-eui",  default="0102030405060708",  help="Device EUI (16 hex chars)")
    parser.add_argument("--site",     default="paris",             help="Site")
    parser.add_argument("--batiment", default="batiment_A",        help="Bâtiment")
    parser.add_argument("--salle",    default="salle_3",           help="Salle")
    parser.add_argument("--machine",  default="detecteur_01",      help="Machine / identifiant")
    parser.add_argument("--interval", default=30, type=int,        help="Intervalle uplink (secondes)")
    return parser.parse_args()
 
 
if __name__ == "__main__":
    args = parse_args()
 
    location = SensorLocation(
        site     = args.site,
        batiment = args.batiment,
        salle    = args.salle,
        machine  = args.machine,
    )
 
    sensor = FireSensor(
        dev_eui  = args.dev_eui,
        location = location,
        interval = args.interval,
    )
 
    sensor.run()