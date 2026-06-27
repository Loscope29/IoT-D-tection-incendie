# Pipeline IoT de Détection Incendie et Automatisation des Actionneurs

Ce projet est un Pipeline IoT complet de bout en bout simulant des capteurs de fumée et température LoRaWAN, un traitement de flux en temps réel, un moteur d'alertes automatisé (boucle fermée), un archivage dans une base de données de séries temporelles, et une interface de supervision (Dashboard React).

---

## 🏗️ Architecture du Projet

Le flux de données nominal de l'architecture est le suivant :

```
             ┌────────────────────────────────────────────────────────┐
             │                Simulateur de Capteurs                  │
             │           (capteur/run_sensors.py - LoRaWAN)           │
             └──────────────────────────┬─────────────────────────────┘
                                        │ (Uplink MQTT)
                                        ▼
             ┌────────────────────────────────────────────────────────┐
             │                    Broker HiveMQ                       │◄───────────────┐
             │            (Inbound: application/.../up)               │                │ (WebSockets)
             └──────────────────────────┬─────────────────────────────┘                │
                                        │                                              │
                                        ▼                                              │
             ┌────────────────────────────────────────────────────────┐                │
             │             Gateway Métier (gateway/gateway.py)        │                │
             │          - Moteur d'alertes & Télémétrie               │                │
             │          - Auto-Downlinks (siren/light ON/OFF)          │                │
             └──────────────────────────┬─────────────────────────────┘                │
                                        │ (Publish fire/...)                           │
                                        ▼                                              │
             ┌────────────────────────────────────────────────────────┐                │
             │                    Broker HiveMQ                       │                │
             │               (Outbound: fire/... )                    │                │
             └──────────────────────────┬─────────────────────────────┘                │
                                        │                                              │
                                        ▼                                              │
             ┌────────────────────────────────────────────────────────┐                │
             │      Pont MQTT -> Kafka (gateway/mqtt_to_kafka.py)     │                │
             └──────────────────────────┬─────────────────────────────┘                │
                                        │                                              │
                                        ▼                                              │
             ┌────────────────────────────────────────────────────────┐                │
             │                      Apache Kafka                      │                │
             │               (Topic: fire-telemetry)                  │                │
             └──────────────────────────┬─────────────────────────────┘                │
                                        │                                              │
                                        ▼                                              │
             ┌────────────────────────────────────────────────────────┐                │
             │    Pont Kafka -> InfluxDB (Influx/kafka_to_influx.py)  │                │
             └──────────────────────────┬─────────────────────────────┘                │
                                        │                                              │
                                        ▼                                              │
             ┌────────────────────────────────────────────────────────┐                │
             │                   InfluxDB (Storage)                   │                │
             └────────────────────────────────────────────────────────┘                │
                                                                                       │
             ┌────────────────────────────────────────────────────────┐                │
             │                    Dashboard React                     │────────────────┘
             │             (Abonnement temps réel & Commandes)        │
             └────────────────────────────────────────────────────────┘
```

---

## 📁 Structure des Répertoires

* **`capteur/`** : Contient le code du simulateur de capteurs.
  * `sensor.py` : Modélise un capteur LoRaWAN avec des mesures physiques (`smoke_level` en ppm, `temperature` en °C, `battery_level` en %) et des actionneurs (`siren`, `light`).
  * `run_sensors.py` : Lance en parallèle les 4 capteurs (Paris Bâtiment A/B, Lyon) et permet d'injecter des scénarios d'incidents.
* **`gateway/`** : Logique métier intermédiaire.
  * `gateway.py` : Transforme les uplinks bruts, enrichit le JSON, et intègre le **moteur d'alerte** (downlinks automatique si `smoke_level >= 50` ou `temperature >= 60`).
  * `mqtt_to_kafka.py` : Pont de redirection des données du broker MQTT vers les topics Kafka.
* **`Influx/`** : Persistance des données.
  * `kafka_to_influx.py` : Consommateur Kafka qui stocke les métriques de télémétrie en temps réel dans InfluxDB.
* **`dashboard/`** : Application web React (Vite) de supervision.
  * Interface Cyberpunk sombre découpée en **4 quadrants** :
    * *Top Left* : Alertes incendies critiques actives (rouge clignotant).
    * *Bottom Left* : Alertes techniques (batterie faible, déconnexion).
    * *Top Right* : Contrôle et forçage manuel des sirènes/gyrophares par downlink.
    * *Bottom Right* : Terminal de logs en direct (WebSockets MQTT).
* **`chirpstack/`** & **`hivemq/`** : Fichiers de configuration pour ChirpStack et HiveMQ.

---

## 🔌 Cartographie des Ports

| Service | Port Externe | Port Interne | Description |
| :--- | :--- | :--- | :--- |
| **HiveMQ MQTT** | `1883` | `1883` | Port de communication MQTT principal |
| **HiveMQ WS** | `8000` | `8000` | WebSockets MQTT (utilisé par le Dashboard React) |
| **HiveMQ UI** | `8085` | `8080` | HiveMQ Control Center (`admin` / `admin`) |
| **ChirpStack UI** | `8095` | `8000` | Interface LoRaWAN ChirpStack |
| **Kafka UI** | `8090` | `8080` | Interface web d'administration de Kafka |
| **Kafka Broker**| `29092`| `29092`| Endpoint Kafka accessible par l'hôte |
| **InfluxDB** | `8086` | `8086` | Base de données InfluxDB UI/API (`admin` / `adminpassword`) |
| **React App** | `5173` | `5173` | Serveur de développement du Dashboard |

---

## 🚀 Démarrage et Exécution

### Étape 1 : Lancer les conteneurs d'infrastructure
Assurez-vous que Docker est démarré, puis exécutez à la racine :
```bash
docker compose up -d
```

### Étape 2 : Préparer l'environnement Python
Installez les bibliothèques requises sur votre machine hôte :
```bash
pip install paho-mqtt kafka-python influxdb-client
```

### Étape 3 : Lancer la Gateway, les Ponts et le Simulateur
Ouvrez vos terminaux et lancez :
1. **Gateway** :
   ```bash
   python gateway/gateway.py
   ```
2. **Pont Kafka** :
   ```bash
   python gateway/mqtt_to_kafka.py
   ```
3. **Pont InfluxDB** :
   ```bash
   python Influx/kafka_to_influx.py
   ```
4. **Capteurs (Scénario Incendie)** :
   ```bash
   capteur/capteur/Scripts/python.exe capteur/run_sensors.py --scenario incendie
   ```

### Étape 4 : Lancer le Dashboard React
1. Rendez-vous dans le dossier :
   ```bash
   cd dashboard
   ```
2. Installez les paquets npm :
   ```bash
   npm install
   ```
3. Démarrez l'application :
   ```bash
   npm run dev
   ```
4. Ouvrez **[http://localhost:5173/](http://localhost:5173/)** dans votre navigateur.

---

## 🧪 Scénarios de Test Disponibles
Lors du lancement de `run_sensors.py`, vous pouvez passer l'argument `--scenario` pour tester différents comportements :
* `--scenario incendie` : Déclenche un incendie sur le capteur Paris-A-1 (fumée et température s'élèvent, sirènes et lumières s'allument automatiquement via la gateway).
* `--scenario batterie` : Réduit la batterie du capteur Paris-A-2 à un niveau critique (génère une alerte technique sur le dashboard).
* `--scenario inactif` : Rend le capteur Paris-B-1 hors-ligne (génère une alerte de maintenance).
* `--scenario multi` : Combine plusieurs incidents simultanément.
