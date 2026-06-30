import React, { useState, useEffect, useRef } from 'react';
import mqtt from 'mqtt';
import { 
  Flame, 
  Battery, 
  Wrench, 
  ShieldAlert, 
  Volume2, 
  Lightbulb, 
  Wifi, 
  WifiOff, 
  Terminal, 
  CheckCircle,
  Activity
} from 'lucide-react';
import './App.css';

// Liste statique des capteurs attendus pour pré-remplir l'interface
const INITIAL_SENSORS = {
  "AA00000000000001": {
    dev_eui: "AA00000000000001",
    location: { site: "paris", batiment: "batiment_A", salle: "salle_1", machine: "detecteur_01" },
    readings: { smoke_level: 0, smoke: false, temperature: 0, battery_level: 0, status: "connecting", siren: "OFF", light: "OFF" }
  },
  "AA00000000000002": {
    dev_eui: "AA00000000000002",
    location: { site: "paris", batiment: "batiment_A", salle: "salle_2", machine: "detecteur_01" },
    readings: { smoke_level: 0, smoke: false, temperature: 0, battery_level: 0, status: "connecting", siren: "OFF", light: "OFF" }
  },
  "AA00000000000003": {
    dev_eui: "AA00000000000003",
    location: { site: "paris", batiment: "batiment_B", salle: "salle_1", machine: "detecteur_01" },
    readings: { smoke_level: 0, smoke: false, temperature: 0, battery_level: 0, status: "connecting", siren: "OFF", light: "OFF" }
  },
  "AA00000000000004": {
    dev_eui: "AA00000000000004",
    location: { site: "lyon", batiment: "batiment_A", salle: "salle_1", machine: "detecteur_01" },
    readings: { smoke_level: 0, smoke: false, temperature: 0, battery_level: 0, status: "connecting", siren: "OFF", light: "OFF" }
  }
};

function App() {
  const [sensors, setSensors] = useState(INITIAL_SENSORS);
  const [mqttConnected, setMqttConnected] = useState(false);
  const [logs, setLogs] = useState([
    { time: new Date().toLocaleTimeString(), msg: "Système de supervision initialisé.", type: "system" }
  ]);
  
  const mqttClientRef = useRef(null);

  useEffect(() => {
    // Connexion au broker MQTT HiveMQ via WebSockets
    const host = import.meta.env.VITE_HIVEMQ_HOST || 'localhost';
    const wsPort = import.meta.env.VITE_HIVEMQ_WS_PORT || '8000';
    const username = import.meta.env.VITE_HIVEMQ_USER;
    const password = import.meta.env.VITE_HIVEMQ_PASSWORD;

    const isLocal = host.includes('localhost') || host.includes('127.0.0.1');
    const protocol = isLocal ? 'ws://' : 'wss://';
    const brokerUrl = `${protocol}${host}:${wsPort}/mqtt`;

    logMessage(`Connexion au broker HiveMQ (${protocol.replace('://', '').toUpperCase()})...`, "system");

    const client = mqtt.connect(brokerUrl, {
      clientId: `react-dashboard-${Math.random().toString(16).substr(2, 8)}`,
      clean: true,
      connectTimeout: 4000,
      reconnectPeriod: 4000,
      username: username || undefined,
      password: password || undefined
    });

    mqttClientRef.current = client;

    client.on('connect', () => {
      setMqttConnected(true);
      logMessage("✅ Connecté au broker HiveMQ avec succès.", "system");
      
      // Souscription aux télémétries de la gateway
      const topic = 'fire/+/+/+/+/telemetry';
      client.subscribe(topic, { qos: 1 }, (err) => {
        if (!err) {
          logMessage(`Souscrit au topic : ${topic}`, "system");
        } else {
          logMessage(`❌ Erreur d'abonnement : ${err.message}`, "alert");
        }
      });
    });

    client.on('message', (topic, message) => {
      try {
        const telemetry = JSON.parse(message.toString());
        const dev_eui = telemetry.dev_eui;
        
        if (dev_eui) {
          // Mise à jour de l'état du capteur
          setSensors(prev => ({
            ...prev,
            [dev_eui]: telemetry
          }));

          const { site, batiment, salle } = telemetry.location;
          const { smoke_level, temperature, battery_level, status } = telemetry.readings;
          
          const isFire = smoke_level >= 50.0 || temperature >= 60.0;
          const logText = `[Uplink] ${site}/${batiment}/${salle} - Fumée: ${smoke_level} ppm | Temp: ${temperature}°C | Batterie: ${battery_level}%`;
          
          logMessage(logText, isFire ? 'alert' : 'info');
        }
      } catch (e) {
        logMessage(`Erreur parsing message MQTT : ${e.message}`, "alert");
      }
    });

    client.on('error', (err) => {
      logMessage(`❌ Erreur MQTT : ${err.message}`, "alert");
    });

    client.on('close', () => {
      setMqttConnected(false);
      logMessage("Connexion perdue avec le broker MQTT.", "alert");
    });

    return () => {
      if (client) {
        client.end();
      }
    };
  }, []);

  // Fonction utilitaire pour ajouter un log
  const logMessage = (msg, type = 'info') => {
    const timeString = new Date().toLocaleTimeString();
    setLogs(prev => [
      { time: timeString, msg, type },
      ...prev.slice(0, 99) // Garder les 100 derniers logs
    ]);
  };

  // Publier une commande manuelle vers la gateway
  const sendCommand = (sensor, action, value) => {
    if (!mqttConnected || !mqttClientRef.current) {
      logMessage("Impossible d'envoyer la commande : Non connecté à MQTT.", "alert");
      return;
    }

    const { site, batiment, salle, machine } = sensor.location;
    // Format de topic attendu par la gateway : fire/{site}/{batiment}/{salle}/{machine}/cmd/{action}
    const topic = `fire/${site}/${batiment}/${salle}/${machine}/cmd/${action}`;
    
    logMessage(`[Downlink Command] Publication -> ${action.toUpperCase()}=${value} pour ${site}/${batiment}/${salle}`, "system");
    mqttClientRef.current.publish(topic, value, { qos: 1, retain: false });
  };

  // Traiter les alertes d'incendie (haut gauche)
  const fireAlerts = Object.values(sensors).filter(s => {
    const { smoke_level, temperature } = s.readings;
    return smoke_level >= 50.0 || temperature >= 60.0;
  });

  // Traiter les alertes techniques (bas gauche)
  const technicalAlerts = Object.values(sensors).filter(s => {
    const { battery_level, status } = s.readings;
    return (battery_level > 0 && battery_level < 20) || status === "inactive";
  });

  // Calcul du nombre de sirènes et lumières actives
  const activeSirensCount = Object.values(sensors).filter(s => s.readings.siren === "ON").length;
  const activeLightsCount = Object.values(sensors).filter(s => s.readings.light === "ON").length;

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-title-container">
          <Activity className="glow-success" size={28} />
          <h1 className="header-title">Supervision Incendie</h1>
        </div>
        <div className="connection-status">
          {mqttConnected ? (
            <>
              <Wifi size={18} className="glow-success" />
              <span className="glow-success">HiveMQ Connecté (WS)</span>
            </>
          ) : (
            <>
              <WifiOff size={18} className="glow-danger animate-pulse" />
              <span className="glow-danger">HiveMQ Déconnecté</span>
            </>
          )}
        </div>
      </header>

      {/* Summary Cards */}
      <section className="metrics-summary-bar">
        <div className="summary-card">
          <div className={`summary-icon-container ${fireAlerts.length > 0 ? 'danger' : 'success'}`}>
            <Flame size={22} className={fireAlerts.length > 0 ? 'animate-pulse' : ''} />
          </div>
          <div className="summary-info">
            <span className="summary-value">{fireAlerts.length}</span>
            <span className="summary-label">Alertes Incendie</span>
          </div>
        </div>

        <div className="summary-card">
          <div className={`summary-icon-container ${technicalAlerts.length > 0 ? 'warning' : 'success'}`}>
            <Wrench size={22} />
          </div>
          <div className="summary-info">
            <span className="summary-value">{technicalAlerts.length}</span>
            <span className="summary-label">Alertes Tech</span>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon-container">
            <Volume2 size={22} className={activeSirensCount > 0 ? 'glow-danger animate-pulse' : ''} />
          </div>
          <div className="summary-info">
            <span className="summary-value">{activeSirensCount} / 4</span>
            <span className="summary-label">Sirènes Actives</span>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon-container">
            <Lightbulb size={22} className={activeLightsCount > 0 ? 'glow-success animate-pulse' : ''} />
          </div>
          <div className="summary-info">
            <span className="summary-value">{activeLightsCount} / 4</span>
            <span className="summary-label">Gyrophares Actifs</span>
          </div>
        </div>
      </section>

      {/* 4 Quadrants Grid */}
      <main className="dashboard-grid">
        
        {/* HAUT GAUCHE : Alertes Incendie */}
        <section className="quadrant-card">
          <div className="card-header">
            <div className="card-title-container">
              <Flame size={18} className="glow-danger" />
              <h2 className="card-title">Alertes Incendie Actives</h2>
            </div>
            <span className={`badge-count ${fireAlerts.length > 0 ? 'danger' : ''}`}>
              {fireAlerts.length}
            </span>
          </div>
          <div className="card-content">
            {fireAlerts.length === 0 ? (
              <div className="empty-state">
                <CheckCircle size={36} className="glow-success" />
                <p>Aucun incendie détecté. Tous les sites sont sécurisés.</p>
              </div>
            ) : (
              <div className="alerts-list">
                {fireAlerts.map(sensor => {
                  const { site, batiment, salle, machine } = sensor.location;
                  const { smoke_level, temperature } = sensor.readings;
                  return (
                    <div key={sensor.dev_eui} className="alert-item danger alert-fire-active">
                      <div className="alert-info">
                        <span className="alert-location">{site.toUpperCase()} — {batiment} ({salle})</span>
                        <span className="alert-details">ID: {machine} | Ref: {sensor.dev_eui.slice(-4)}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <span className="alert-badge danger">{smoke_level} ppm</span>
                        <span className="alert-badge danger">{temperature} °C</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* HAUT DROITE : Contrôle des Actuateurs (Boutons Downlink) */}
        <section className="quadrant-card">
          <div className="card-header">
            <div className="card-title-container">
              <Volume2 size={18} className="glow-success" />
              <h2 className="card-title">Panneau de Contrôle Actuateurs</h2>
            </div>
            <span className="badge-count">Actif</span>
          </div>
          <div className="card-content">
            <div className="actuators-grid">
              {Object.values(sensors).map(sensor => {
                const { site, batiment, salle } = sensor.location;
                const { siren, light, status } = sensor.readings;
                const isOffline = status === "inactive" || status === "connecting";
                
                return (
                  <div key={sensor.dev_eui} className="sensor-control-card">
                    <div className="sensor-control-header">
                      <div>
                        <span className="sensor-name">{site.toUpperCase()} — {batiment} ({salle})</span>
                        <div className="sensor-eui">EUI: {sensor.dev_eui}</div>
                      </div>
                      <span className={`indicator-dot ${isOffline ? 'inactive' : 'active'}`}></span>
                    </div>

                    <div className="controls-row">
                      {/* Sirène */}
                      <div className="actuator-status-container">
                        <span className="actuator-label">
                          <Volume2 size={14} /> Sirène
                        </span>
                        <span className={`actuator-state-badge ${siren === 'ON' ? 'active' : 'inactive'}`}>
                          {siren}
                        </span>
                      </div>
                      <div className="button-group">
                        <button 
                          className={`control-btn ${siren === 'ON' ? 'btn-active' : ''}`}
                          onClick={() => sendCommand(sensor, 'siren', siren === 'ON' ? 'OFF' : 'ON')}
                          disabled={isOffline}
                        >
                          {siren === 'ON' ? 'Éteindre' : 'Allumer'}
                        </button>
                      </div>
                    </div>

                    <div className="controls-row">
                      {/* Lumières */}
                      <div className="actuator-status-container">
                        <span className="actuator-label">
                          <Lightbulb size={14} /> Gyrophares
                        </span>
                        <span className={`actuator-state-badge ${light === 'ON' ? 'active' : 'inactive'}`}>
                          {light}
                        </span>
                      </div>
                      <div className="button-group">
                        <button 
                          className={`control-btn ${light === 'ON' ? 'btn-active' : ''}`}
                          onClick={() => sendCommand(sensor, 'light', light === 'ON' ? 'OFF' : 'ON')}
                          disabled={isOffline}
                        >
                          {light === 'ON' ? 'Éteindre' : 'Allumer'}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* BAS GAUCHE : Alertes Techniques */}
        <section className="quadrant-card">
          <div className="card-header">
            <div className="card-title-container">
              <ShieldAlert size={18} className="glow-danger" />
              <h2 className="card-title">Maintenance & Alertes Techniques</h2>
            </div>
            <span className={`badge-count warning ${technicalAlerts.length > 0 ? 'warning' : ''}`}>
              {technicalAlerts.length}
            </span>
          </div>
          <div className="card-content">
            {technicalAlerts.length === 0 ? (
              <div className="empty-state">
                <CheckCircle size={36} className="glow-success" />
                <p>Aucune anomalie technique. Tous les capteurs sont opérationnels.</p>
              </div>
            ) : (
              <div className="alerts-list">
                {technicalAlerts.map(sensor => {
                  const { site, batiment, salle, machine } = sensor.location;
                  const { battery_level, status } = sensor.readings;
                  
                  const isLowBattery = battery_level > 0 && battery_level < 20;
                  const isOffline = status === "inactive";
                  
                  return (
                    <div key={sensor.dev_eui} className="alert-item warning">
                      <div className="alert-info">
                        <span className="alert-location">{site.toUpperCase()} — {batiment} ({salle})</span>
                        <span className="alert-details">ID: {machine} | Ref: {sensor.dev_eui.slice(-4)}</span>
                      </div>
                      <div>
                        {isLowBattery && (
                          <span className="alert-badge warning" style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                            <Battery size={12} /> Batterie : {battery_level}%
                          </span>
                        )}
                        {isOffline && (
                          <span className="alert-badge danger">
                            Hors-ligne (Inactif)
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* BAS DROITE : Synoptique Graphique des Équipements */}
        <section className="quadrant-card">
          <div className="card-header">
            <div className="card-title-container">
              <Activity size={18} className="glow-success" />
              <h2 className="card-title">Synoptique Graphique des Équipements</h2>
            </div>
            <span className="badge-count" style={{ background: 'var(--clr-success)' }}>Interactif</span>
          </div>
          <div className="card-content">
            <div className="synoptic-grid">
              {Object.values(sensors).map(sensor => {
                const { site, batiment, salle } = sensor.location;
                const { smoke_level, temperature, siren, light, status } = sensor.readings;
                const isFire = smoke_level >= 50.0 || temperature >= 60.0;
                const isOffline = status === "inactive" || status === "connecting";
                
                return (
                  <div key={sensor.dev_eui} className={`synoptic-room-card ${isFire ? 'fire-alarm-active' : ''} ${isOffline ? 'room-offline' : ''}`}>
                    <div className="room-header">
                      <span className="room-title">{site.toUpperCase()} — {batiment.replace('batiment_', 'Bât. ')} ({salle.replace('salle_', 'S.')})</span>
                      <span className={`status-dot ${isOffline ? 'offline' : (isFire ? 'danger' : 'success')}`}></span>
                    </div>

                    <div className="room-layout">
                      {/* Capteur */}
                      <div className="equipment-node">
                        <div className={`equipment-icon ${isOffline ? 'bg-dark' : (isFire ? 'bg-danger text-light' : 'bg-success text-light')}`}>
                          <Flame size={16} className={isFire ? 'animate-pulse' : ''} />
                        </div>
                        <span className="equipment-label">Capteur</span>
                        <span className="equipment-value">{isOffline ? 'N/A' : `${smoke_level} ppm`}</span>
                        <span className="equipment-value">{isOffline ? '' : `${temperature} °C`}</span>
                      </div>

                      {/* Sirène */}
                      <div className="equipment-node">
                        <div className={`equipment-icon ${isOffline ? 'bg-dark' : (siren === 'ON' ? 'siren-active' : 'bg-dark text-muted')}`}>
                          <Volume2 size={16} />
                        </div>
                        <span className="equipment-label">Sirène</span>
                        <span className="equipment-value" style={{ color: siren === 'ON' ? 'var(--clr-danger)' : 'var(--text-secondary)' }}>
                          {isOffline ? 'N/A' : siren}
                        </span>
                      </div>

                      {/* Gyrophare */}
                      <div className="equipment-node">
                        <div className={`equipment-icon ${isOffline ? 'bg-dark' : (light === 'ON' ? 'light-active' : 'bg-dark text-muted')}`}>
                          <Lightbulb size={16} />
                        </div>
                        <span className="equipment-label">Gyrophare</span>
                        <span className="equipment-value" style={{ color: light === 'ON' ? 'var(--clr-warning)' : 'var(--text-secondary)' }}>
                          {isOffline ? 'N/A' : light}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

      </main>
    </div>
  );
}

export default App;
