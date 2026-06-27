"""
Gateway de détection incendie
==============================
Bridge sur un seul broker HiveMQ (Option A).
Souscrit aux uplinks ChirpStack, reformate les données vers des métriques numériques,
exécute un moteur d'alertes par seuil et gère les downlinks automatiques.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gateway")

# ─── Configuration ─────────────────────────────────────────────────────────
HIVEMQ_HOST  = "localhost"
HIVEMQ_PORT  = 1883
HIVEMQ_USER  = ""
HIVEMQ_PASS  = ""
APP_ID       = "fire-detection-app"

# Topics souscrits
TOPIC_UPLINK  = "application/+/device/+/event/up"
TOPIC_CMD_SUB = "fire/+/+/+/+/cmd/+"

# Templates topics
TOPIC_DOWNLINK = "application/{app_id}/device/{dev_eui}/command/down"


# ─── Device Registry ───────────────────────────────────────────────────────
class DeviceRegistry:
    """
    Maintient le mapping bidirectionnel :
      location_key  → dev_eui   (pour les downlinks)
      dev_eui       → location  (pour les logs)
    """

    def __init__(self):
        self._lock        = threading.Lock()
        self._loc_to_eui  = {}   # "paris/batiment_A/salle_1/detecteur_01" → "AA001"
        self._eui_to_loc  = {}   # "AA001" → "paris/batiment_A/salle_1/detecteur_01"

    def _key(self, site, batiment, salle, machine) -> str:
        return f"{site}/{batiment}/{salle}/{machine}"

    def register(self, dev_eui: str, site: str, batiment: str, salle: str, machine: str):
        key = self._key(site, batiment, salle, machine)
        with self._lock:
            if self._loc_to_eui.get(key) != dev_eui:
                self._loc_to_eui[key]       = dev_eui
                self._eui_to_loc[dev_eui]   = key
                log.info(f"[Registry] {key} → {dev_eui}")

    def get_eui(self, site: str, batiment: str, salle: str, machine: str) -> str | None:
        with self._lock:
            return self._loc_to_eui.get(self._key(site, batiment, salle, machine))

    def count(self) -> int:
        with self._lock:
            return len(self._loc_to_eui)


# ─── Helpers topics ────────────────────────────────────────────────────────
def fire_base(site: str, batiment: str, salle: str, machine: str) -> str:
    return f"fire/{site}/{batiment}/{salle}/{machine}"


def parse_cmd_topic(topic: str) -> tuple[str, str, str, str, str] | None:
    """
    Parse : fire/{site}/{batiment}/{salle}/{machine}/cmd/{action}
    Retourne (site, batiment, salle, machine, action) ou None.
    """
    parts = topic.split("/")
    if len(parts) == 7 and parts[0] == "fire" and parts[5] == "cmd":
        return parts[1], parts[2], parts[3], parts[4], parts[6]
    return None


# ─── Gateway ───────────────────────────────────────────────────────────────
class FireGateway:
    def __init__(self):
        self._registry = DeviceRegistry()

        # Un seul client MQTT sur HiveMQ
        self._client = mqtt.Client(client_id="fire-gateway")
        self._client.on_connect    = self._on_connect
        self._client.on_message    = self._on_message
        self._client.on_disconnect = self._on_disconnect

        if HIVEMQ_USER:
            self._client.username_pw_set(HIVEMQ_USER, HIVEMQ_PASS)

    # ── Callbacks MQTT ─────────────────────────────────────────────────────
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("[Gateway] Connecté à HiveMQ")
            # Uplinks ChirpStack
            client.subscribe(TOPIC_UPLINK, qos=1)
            log.info(f"[Gateway] Souscrit → {TOPIC_UPLINK}")
            # Commandes dashboard / Flink
            client.subscribe(TOPIC_CMD_SUB, qos=1)
            log.info(f"[Gateway] Souscrit → {TOPIC_CMD_SUB}")
        else:
            log.error(f"[Gateway] Erreur connexion HiveMQ (code {rc})")

    def _on_disconnect(self, client, userdata, rc):
        log.warning(f"[Gateway] Déconnecté (code {rc}) — reconnexion auto...")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic

        if topic.startswith("application/"):
            # Uplink ChirpStack → reformater vers fire/
            self._handle_uplink(msg)
        elif topic.startswith("fire/") and "/cmd/" in topic:
            # Commande dashboard/Flink → downlink vers capteur
            self._handle_command(msg)

    # ── Envoi de commande Downlink ──────────────────────────────────────────
    def _send_downlink(self, dev_eui: str, site: str, batiment: str, salle: str, machine: str, action: str, value: str):
        downlink_topic = TOPIC_DOWNLINK.format(
            app_id  = APP_ID,
            dev_eui = dev_eui,
        )
        downlink_payload = json.dumps({
            "cmd":       action,
            "value":     value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._client.publish(downlink_topic, downlink_payload, qos=1)
        log.info(
            f"[Downlink] {site}/{batiment}/{salle}/{machine} | "
            f"{action.upper()}={value} → {dev_eui}"
        )

    # ── Traitement uplink ──────────────────────────────────────────────────
    def _handle_uplink(self, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError as e:
            log.error(f"[Uplink] JSON invalide : {e}")
            return

        device_info = payload.get("deviceInfo", {})
        tags        = device_info.get("tags", {})
        obj         = payload.get("object", {})

        dev_eui  = device_info.get("devEui", "unknown")
        site     = tags.get("site",     "unknown")
        batiment = tags.get("batiment", "unknown")
        salle    = tags.get("salle",    "unknown")
        machine  = tags.get("machine",  "unknown")

        # Enregistrer dans le registry
        self._registry.register(dev_eui, site, batiment, salle, machine)

        base = fire_base(site, batiment, salle, machine)

        # Extraction des nouvelles valeurs numériques
        smoke_level   = float(obj.get("smoke_level", 0.0))
        temperature   = float(obj.get("temperature", 20.0))
        battery_level = int(obj.get("battery_level", 100))
        status        = obj.get("status", "unknown")
        siren_state   = obj.get("siren", "OFF").upper()
        light_state   = obj.get("light", "OFF").upper()

        # Calcul de l'état d'alerte (seuil de 50 ppm pour la fumée ou 60°C pour la température)
        is_alert = (smoke_level >= 50.0) or (temperature >= 60.0)

        # ── Publication des champs individuels (retain=True) ──
        self._client.publish(f"{base}/smoke_level", json.dumps(smoke_level), qos=1, retain=True)
        self._client.publish(f"{base}/temperature", json.dumps(temperature), qos=1, retain=True)
        self._client.publish(f"{base}/battery_level", json.dumps(battery_level), qos=1, retain=True)
        self._client.publish(f"{base}/status", status, qos=1, retain=True)
        self._client.publish(f"{base}/smoke", json.dumps(is_alert), qos=1, retain=True) # pour compatibilité

        # ── Telemetry complète ──
        telemetry = {
            "dev_eui":   dev_eui,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {
                "site": site, "batiment": batiment,
                "salle": salle, "machine": machine,
            },
            "readings": {
                "smoke_level":    smoke_level,
                "smoke":          is_alert,
                "temperature":    temperature,
                "battery_level":  battery_level,
                "status":         status,
                "siren":          siren_state,
                "light":          light_state,
                "manual_trigger": obj.get("manual_trigger", False),
            },
            "radio": {
                "frame_count": payload.get("fCnt", 0),
                "data_rate":   payload.get("dr", 0),
                "fport":       payload.get("fPort", 1),
                "rx_info":     payload.get("rxInfo", []),
            },
        }

        self._client.publish(f"{base}/telemetry", json.dumps(telemetry), qos=1, retain=True)

        # Log
        smoke_icon = "🔥 ALERTE" if is_alert else "✅"
        manual_tag = " | 🚨 FORCÉ/MANUEL" if obj.get("manual_trigger") else ""
        log.info(
            f"[Uplink] {site}/{batiment}/{salle}/{machine} | {smoke_icon} | "
            f"smoke={smoke_level} ppm | temp={temperature}°C | battery={battery_level}% | "
            f"status={status} | siren={siren_state}{manual_tag}"
        )

        # ── Moteur d'Alerte et de Downlink Automatique ──
        if is_alert:
            # Si le capteur a sa sirène ou sa lumière éteinte, on envoie la commande d'activation
            if siren_state == "OFF":
                log.info(f"[AlertEngine] Taux critique détecté à {site}/{batiment}/{salle}/{machine}. Activation sirène.")
                self._send_downlink(dev_eui, site, batiment, salle, machine, "siren", "ON")
            if light_state == "OFF":
                log.info(f"[AlertEngine] Taux critique détecté à {site}/{batiment}/{salle}/{machine}. Activation gyrophares.")
                self._send_downlink(dev_eui, site, batiment, salle, machine, "light", "ON")
        else:
            # Si pas d'alerte mais sirène/lumière toujours allumées, on éteint
            if siren_state == "ON":
                log.info(f"[AlertEngine] Retour à la normale à {site}/{batiment}/{salle}/{machine}. Désactivation sirène.")
                self._send_downlink(dev_eui, site, batiment, salle, machine, "siren", "OFF")
            if light_state == "ON":
                log.info(f"[AlertEngine] Retour à la normale à {site}/{batiment}/{salle}/{machine}. Désactivation gyrophares.")
                self._send_downlink(dev_eui, site, batiment, salle, machine, "light", "OFF")

    # ── Traitement commande manuelle depuis dashboard ──────────────────────
    def _handle_command(self, msg):
        parsed = parse_cmd_topic(msg.topic)
        if not parsed:
            log.warning(f"[Cmd] Topic invalide : {msg.topic}")
            return

        site, batiment, salle, machine, action = parsed
        value = msg.payload.decode().strip().upper()

        if action not in ("siren", "light") or value not in ("ON", "OFF"):
            log.warning(f"[Cmd] Commande invalide : {action}={value}")
            return

        dev_eui = self._registry.get_eui(site, batiment, salle, machine)
        if not dev_eui:
            log.error(f"[Cmd] dev_eui introuvable pour {site}/{batiment}/{salle}/{machine} — capteur non enregistré ?")
            return

        # Envoi de la commande manuelle
        self._send_downlink(dev_eui, site, batiment, salle, machine, action, value)

    # ── Démarrage ──────────────────────────────────────────────────────────
    def run(self):
        log.info(
            f"\n{'='*60}\n"
            f"  Gateway incendie — broker unique HiveMQ\n"
            f"  Host : {HIVEMQ_HOST}:{HIVEMQ_PORT}\n"
            f"{'='*60}"
        )

        self._client.connect(HIVEMQ_HOST, HIVEMQ_PORT, keepalive=60)
        self._client.loop_start()

        try:
            while True:
                time.sleep(30)
                log.debug(f"[Registry] {self._registry.count()} device(s) connus")
        except KeyboardInterrupt:
            log.info("[Gateway] Arrêt.")
        finally:
            self._client.loop_stop()
            self._client.disconnect()


if __name__ == "__main__":
    FireGateway().run()