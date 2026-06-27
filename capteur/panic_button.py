"""
Panic Button — Déclenchement manuel sur site
=============================================
Simule un bouton physique pressé par le personnel sur site.

Publie un uplink avec manual_trigger=true sur HiveMQ.
Flink recevra cet événement et broadcastera siren=ON + light=ON
vers TOUS les capteurs du site concerné.

Différence clé avec le capteur normal :
  - smoke=False (pas de fumée détectée)
  - manual_trigger=True (action humaine délibérée)
  - source=manual (tracé dans InfluxDB pour audit)
"""

import json
import logging
import time
import uuid
import argparse
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("panic-button")

HIVEMQ_HOST = "localhost"
HIVEMQ_PORT = 1883
APP_ID      = "fire-detection-app"


class PanicButton:
    def __init__(self, dev_eui: str, site: str, batiment: str):
        self.dev_eui  = dev_eui
        self.site     = site
        self.batiment = batiment

        self._client = mqtt.Client(client_id=f"panic-{dev_eui}")
        self._client.on_connect = lambda c, u, f, rc: log.info(
            "Connecté à HiveMQ" if rc == 0
            else f"Erreur connexion (code {rc})"
        )

    def _build_payload(self) -> dict:
        """
        Payload panic button :
        - manual_trigger=True → signale à Flink qu'il faut broadcaster le site
        - site dans les tags → Flink sait quel site broadcaster
        """
        return {
            "deduplicationId": str(uuid.uuid4()),
            "time": datetime.now(timezone.utc).isoformat(),
            "deviceInfo": {
                "applicationId":     APP_ID,
                "applicationName":   "fire-detection",
                "deviceName":        f"panic-button-{self.dev_eui[-4:]}",
                "devEui":            self.dev_eui,
                "deviceProfileName": "fire-sensor-classC-eu868",
                "tags": {
                    "site":     self.site,
                    "batiment": self.batiment,
                    "salle":    "all",      # broadcast tout le bâtiment
                    "machine":  "panic-button",
                },
            },
            "fCnt":  1,
            "fPort": 2,    # fPort 2 = panic button (distingue du capteur normal)
            "object": {
                "smoke":          False,
                "battery":        "connected",
                "status":         "active",
                "manual_trigger": True,     # ← clé Flink pour broadcaster
                "source":         "manual",
            },
            "rxInfo": [{"gatewayId": "gateway-sim-001", "rssi": -75, "snr": 8.0}],
        }

    def trigger(self):
        """Déclenche une alerte manuelle une seule fois."""
        topic   = f"application/{APP_ID}/device/{self.dev_eui}/event/up"
        payload = self._build_payload()

        self._client.connect(HIVEMQ_HOST, HIVEMQ_PORT)
        self._client.loop_start()
        time.sleep(0.5)

        self._client.publish(topic, json.dumps(payload), qos=1)

        log.warning(
            f"🚨 DÉCLENCHEMENT MANUEL — "
            f"site={self.site} | batiment={self.batiment} | "
            f"device={self.dev_eui}"
        )

        time.sleep(1)
        self._client.loop_stop()
        self._client.disconnect()
        log.info("Signal envoyé. Flink va broadcaster à tous les capteurs du site.")


# ─── Entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Panic button — déclenchement manuel")
    parser.add_argument("--dev-eui",  default="FF00000000000001")
    parser.add_argument("--site",     default="paris")
    parser.add_argument("--batiment", default="batiment_A")
    args = parser.parse_args()

    button = PanicButton(
        dev_eui  = args.dev_eui,
        site     = args.site,
        batiment = args.batiment,
    )
    button.trigger()