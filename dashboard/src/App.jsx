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
  Activity,
  Sun,
  Moon,
  Search,
  Clock,
  ShieldCheck,
  EyeOff
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
  
  // Nouveaux états de navigation, d'acquittement et de style (Style Hôpital William Morey)
  const [activeTab, setActiveTab] = useState('supervision'); // 'supervision', 'rooms', 'journal'
  const [searchQuery, setSearchQuery] = useState('');
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState({}); // dev_eui -> details
  const [inhibitedSensors, setInhibitedSensors] = useState({}); // dev_eui -> boolean
  const [selectedAlert, setSelectedAlert] = useState(null); // sensor object
  const [activeAlertPanelType, setActiveAlertPanelType] = useState('fire'); // 'fire' or 'technical'
  const [alertTimers, setAlertTimers] = useState({}); // dev_eui -> seconds elapsed
  const [alertTriggers, setAlertTriggers] = useState({}); // dev_eui -> { timestamp, smoke_level, temperature }
  const [lastSeen, setLastSeen] = useState(() => {
    const initial = {};
    Object.keys(INITIAL_SENSORS).forEach(eui => {
      initial[eui] = Date.now();
    });
    return initial;
  });

  // Formulaire d'acquittement temporaire
  const [tempMotifs, setTempMotifs] = useState([]);
  const [tempActions, setTempActions] = useState([]);
  const [tempImpact, setTempImpact] = useState('Aucun');
  const [tempComment, setTempComment] = useState('');

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
        
        // Enregistrement dynamique du capteur si l'EUI est présent
        if (dev_eui) {
          // Extraire le site du topic si manquant dans le payload
          const topicParts = topic.split('/');
          const siteFromTopic = topicParts[1] || 'paris';

          if (!telemetry.location) telemetry.location = {};
          if (!telemetry.location.site) telemetry.location.site = siteFromTopic;

          // Mise à jour de l'état du capteur
          setSensors(prev => ({
            ...prev,
            [dev_eui]: telemetry
          }));

          // Mise à jour du timestamp de dernière réception
          setLastSeen(prev => ({
            ...prev,
            [dev_eui]: Date.now()
          }));

          const { site, batiment, salle } = telemetry.location;
          const { smoke_level, temperature, battery_level } = telemetry.readings;
          
          const isFire = smoke_level >= 50.0 || temperature >= 60.0;
          const logText = `[Uplink] ${site.toUpperCase()}/${batiment}/${salle} - Fumée: ${smoke_level} ppm | Temp: ${temperature}°C | Batterie: ${battery_level}%`;
          
          logMessage(logText, isFire ? 'alert' : 'info');

          // Gérer le déclenchement de l'alerte pour le chronomètre d'acquittement
          if (isFire) {
            setAlertTriggers(prev => {
              if (!prev[dev_eui]) {
                return {
                  ...prev,
                  [dev_eui]: {
                    timestamp: new Date().toLocaleTimeString(),
                    smoke_level,
                    temperature
                  }
                };
              }
              return prev;
            });
          } else {
            // Nettoyage si retour à la normale
            setAlertTriggers(prev => {
              const updated = { ...prev };
              delete updated[dev_eui];
              return updated;
            });
            setAlertTimers(prev => {
              const updated = { ...prev };
              delete updated[dev_eui];
              return updated;
            });
            setAcknowledgedAlerts(prev => {
              const updated = { ...prev };
              delete updated[dev_eui];
              return updated;
            });
          }
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

  // Incrémenter les timers d'alerte en temps réel toutes les secondes (Alerte depuis...)
  useEffect(() => {
    const interval = setInterval(() => {
      setAlertTimers(prev => {
        const updated = { ...prev };
        let changed = false;
        Object.keys(alertTriggers).forEach(eui => {
          if (!acknowledgedAlerts[eui] && !inhibitedSensors[eui]) {
            updated[eui] = (updated[eui] || 0) + 1;
            changed = true;
          }
        });
        return changed ? updated : prev;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [alertTriggers, acknowledgedAlerts, inhibitedSensors]);

  // Gérer la classe de thème sur le body
  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.add('dark-theme');
      document.body.classList.remove('light-theme');
    } else {
      document.body.classList.add('light-theme');
      document.body.classList.remove('dark-theme');
    }
  }, [isDarkMode]);

  // Fonction utilitaire pour ajouter un log
  const logMessage = (msg, type = 'info') => {
    const timeString = new Date().toLocaleTimeString();
    setLogs(prev => [
      { time: timeString, msg, type },
      ...prev.slice(0, 99) // Garder les 100 derniers logs
    ]);
  };

  // Watchdog Keep-Alive : Détecter les capteurs qui ne répondent plus (ex: arrachés)
  useEffect(() => {
    const watchdog = setInterval(() => {
      const now = Date.now();
      const TIMEOUT_MS = 30000; // 30 secondes sans signal
      
      Object.keys(sensors).forEach(eui => {
        const sensor = sensors[eui];
        const lastUpdate = lastSeen[eui];
        
        if (sensor.readings.status !== "inactive" && lastUpdate && (now - lastUpdate) > TIMEOUT_MS) {
          // Mettre à jour l'état du capteur
          setSensors(prev => ({
            ...prev,
            [eui]: {
              ...prev[eui],
              readings: {
                ...prev[eui].readings,
                status: "inactive"
              }
            }
          }));
          
          const { site, batiment, salle } = sensor.location;
          logMessage(`⚠️ Liaison perdue avec ${site.toUpperCase()}/${batiment}/${salle} (Équipement hors-ligne / arraché)`, "alert");
        }
      });
    }, 5000);
    
    return () => clearInterval(watchdog);
  }, [lastSeen, sensors]);

  // Publier une commande manuelle vers la gateway
  const sendCommand = (sensor, action, value) => {
    if (!mqttConnected || !mqttClientRef.current) {
      logMessage("Impossible d'envoyer la commande : Non connecté à MQTT.", "alert");
      return;
    }

    const { site, batiment, salle, machine } = sensor.location;
    const topic = `fire/${site}/${batiment}/${salle}/${machine}/cmd/${action}`;
    
    logMessage(`[Downlink Command] Publication -> ${action.toUpperCase()}=${value} pour ${site}/${batiment}/${salle}`, "system");
    mqttClientRef.current.publish(topic, value, { qos: 1, retain: false });
  };

  // Enregistrer l'acquittement de l'alerte
  const handleSaveAcknowledge = () => {
    if (!selectedAlert) return;
    const dev_eui = selectedAlert.dev_eui;
    const { site, batiment, salle } = selectedAlert.location;

    setAcknowledgedAlerts(prev => ({
      ...prev,
      [dev_eui]: {
        type: activeAlertPanelType,
        motifs: tempMotifs,
        actions: tempActions,
        impact: tempImpact,
        comment: tempComment,
        timestamp: new Date().toLocaleTimeString(),
        duration: alertTimers[dev_eui] || 0
      }
    }));

    const logPrefix = activeAlertPanelType === 'fire' ? '[Acquittement]' : '[Intervention Technique]';
    const logText = `${logPrefix} ${site.toUpperCase()}/${batiment}/${salle} traité - Motif: ${tempMotifs.join(', ') || 'Non spécifié'} | Action: ${tempActions.join(', ') || 'Aucune'} | Impact: ${tempImpact}`;
    logMessage(logText, "success");

    // Fermer le volet et réinitialiser le formulaire
    setSelectedAlert(null);
    setTempMotifs([]);
    setTempActions([]);
    setTempImpact('Aucun');
    setTempComment('');
  };

  // Activer le volet d'acquittement pour un capteur spécifique
  const openAcknowledgePanel = (sensor, type = 'fire') => {
    setSelectedAlert(sensor);
    setActiveAlertPanelType(type);
    setTempMotifs([]);
    setTempActions([]);
    setTempImpact('Aucun');
    setTempComment('');
  };

  // Activer ou désactiver l'inhibition d'un capteur
  const toggleInhibit = (dev_eui) => {
    const sensor = sensors[dev_eui];
    const { site, batiment, salle } = sensor.location;
    const isNowInhibited = !inhibitedSensors[dev_eui];
    
    setInhibitedSensors(prev => ({
      ...prev,
      [dev_eui]: isNowInhibited
    }));

    if (isNowInhibited) {
      logMessage(`[Configuration] Capteur ${site.toUpperCase()}/${batiment}/${salle} INHIBÉ (surveillance suspendue).`, "warning");
    } else {
      logMessage(`[Configuration] Capteur ${site.toUpperCase()}/${batiment}/${salle} RÉACTIVÉ.`, "system");
    }
  };

  // Formatter la durée d'une alerte en chaîne lisible
  const formatAlertDuration = (seconds) => {
    if (!seconds) return "0s";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  // --- FILTRES ET COMPTEURS DYNAMIQUES ---

  // 1. Alertes Incendie en cours (Hors capteurs inhibés)
  const activeFireAlerts = Object.values(sensors).filter(s => {
    const { smoke_level, temperature } = s.readings;
    return (smoke_level >= 50.0 || temperature >= 60.0) && !inhibitedSensors[s.dev_eui];
  });

  // 2. Alertes Incendie non traitées (Non acquittées par l'opérateur)
  const untreatedAlerts = activeFireAlerts.filter(s => !(acknowledgedAlerts[s.dev_eui] && acknowledgedAlerts[s.dev_eui].type === 'fire'));

  // 3. Équipements déconnectés
  const disconnectedAlerts = Object.values(sensors).filter(s => {
    return s.readings.status === "inactive" || s.readings.status === "connecting";
  });

  // 4. Équipements inhibés
  const inhibitedCount = Object.values(sensors).filter(s => inhibitedSensors[s.dev_eui]).length;

  // 5. Équipements en préalarme (valeurs hautes mais sous le seuil d'incendie, ou batterie faible, non inhibés)
  const prealarmAlerts = Object.values(sensors).filter(s => {
    const { smoke_level, temperature, battery_level } = s.readings;
    const isFire = smoke_level >= 50.0 || temperature >= 60.0;
    const isPrealarm = (smoke_level >= 25.0 && smoke_level < 50.0) || (temperature >= 45.0 && temperature < 60.0);
    const isLowBattery = battery_level > 0 && battery_level < 20;
    return (isPrealarm || isLowBattery) && !isFire && !inhibitedSensors[s.dev_eui];
  });

  // 6. Alertes techniques (batterie faible ou hors-ligne, excluant les incendies actifs)
  const technicalAlerts = Object.values(sensors).filter(s => {
    const { smoke_level, temperature, battery_level, status } = s.readings;
    const isOffline = status === "inactive" || status === "connecting";
    const isLowBattery = battery_level > 0 && battery_level < 20;
    const isFire = (smoke_level >= 50.0 || temperature >= 60.0) && !inhibitedSensors[s.dev_eui];
    return (isOffline || isLowBattery) && !isFire;
  });

  // Filtrer les capteurs pour l'onglet de recherche
  const filteredSensors = Object.values(sensors).filter(s => {
    const query = searchQuery.toLowerCase();
    const { site, batiment, salle } = s.location;
    return (
      site.toLowerCase().includes(query) ||
      batiment.toLowerCase().includes(query) ||
      salle.toLowerCase().includes(query) ||
      s.dev_eui.toLowerCase().includes(query)
    );
  });

  return (
    <div className={`dashboard-container ${isDarkMode ? 'dark-theme' : 'light-theme'}`}>
      
      {/* HEADER PROFESSIONNEL  */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="header-logo-circle">
            <Flame size={20} className="glow-success" />
          </div>
          <h1 className="header-title">Fire Protection</h1>
        </div>

        {/* Onglets de navigation */}
        <nav className="header-tabs">
          <button 
            className={`tab-btn ${activeTab === 'supervision' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('supervision')}
          >
            <Activity size={16} />
            <span>Supervision Incendie</span>
          </button>
          <button 
            className={`tab-btn ${activeTab === 'rooms' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('rooms')}
          >
            <Search size={16} />
            <span>État des Salles</span>
          </button>
          <button 
            className={`tab-btn ${activeTab === 'control' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('control')}
          >
            <ShieldAlert size={16} />
            <span>Console de Contrôle</span>
          </button>
        </nav>

        <div className="header-right">
          {/* Commutateur de thème */}
          <button 
            className="theme-toggle-btn"
            onClick={() => setIsDarkMode(!isDarkMode)}
            title={isDarkMode ? "Passer en mode clair (Hôpital)" : "Passer en mode sombre (OLED)"}
          >
            {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {/* Statut de connexion */}
          <div className="connection-status">
            {mqttConnected ? (
              <>
                <Wifi size={16} className="text-success" />
                <span className="text-success font-mono">HiveMQ WS</span>
              </>
            ) : (
              <>
                <WifiOff size={16} className="text-danger animate-pulse" />
                <span className="text-danger font-mono">Déconnecté</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* METRICS SUMMARY BAR (Style CH William Morey) */}
      <section className="metrics-summary-bar">
        {/* 1. Alertes en cours */}
        <div className={`metric-card card-solid-red ${activeFireAlerts.length > 0 ? 'pulse-danger' : ''}`}>
          <div className="metric-header">Alertes en cours</div>
          <div className="metric-value font-mono">{activeFireAlerts.length}</div>
          <div className="metric-sub">Équipements</div>
        </div>

        {/* 2. Alertes non traitées */}
        <div className={`metric-card card-border-red ${untreatedAlerts.length > 0 ? 'pulse-border' : ''}`}>
          <div className="metric-header text-danger">Alertes non traitées</div>
          <div className="metric-value font-mono text-danger">{untreatedAlerts.length}</div>
          <div className="metric-sub text-muted">Équipements</div>
        </div>

        {/* 3. Équipements déconnectés */}
        <div className="metric-card card-solid-grey">
          <div className="metric-header">Équipement déconnecté</div>
          <div className="metric-value font-mono">{disconnectedAlerts.length}</div>
          <div className="metric-sub text-muted">Équipements</div>
        </div>

        {/* 4. Équipements inhibés */}
        <div className="metric-card card-border-yellow">
          <div className="metric-header text-warning">Équipement inhibé</div>
          <div className="metric-value font-mono text-warning">{inhibitedCount}</div>
          <div className="metric-sub text-muted">Équipements</div>
        </div>

        {/* 5. Équipements en préalarme */}
        <div className="metric-card card-border-orange">
          <div className="metric-header text-orange">Équipement en préalarme</div>
          <div className="metric-value font-mono text-orange">{prealarmAlerts.length}</div>
          <div className="metric-sub text-muted">Équipements</div>
        </div>
      </section>

      {/* RENDER PRINCIPAL DE LA VUE ACTIVE */}
      <main className="dashboard-main-content">
        
        {activeTab === 'supervision' && (
          <div className="dashboard-grid">
            {/* Colonne de Gauche : Listes des Alerte actives & Contrôles */}
            <div className="dashboard-sidebar-column">
              
              {/* Alertes Incendie Actives */}
              <section className="quadrant-card">
                <div className="card-header">
                  <div className="card-title-container">
                    <Flame size={18} className="glow-danger" />
                    <h2 className="card-title">Incendies Détectés</h2>
                  </div>
                  <span className={`badge-count ${untreatedAlerts.length > 0 ? 'danger' : ''}`}>
                    {untreatedAlerts.length}
                  </span>
                </div>
                <div className="card-content">
                  {untreatedAlerts.length === 0 ? (
                    <div className="empty-state">
                      <CheckCircle size={32} className="text-success" />
                      <p>Aucun incendie détecté sur les sites.</p>
                    </div>
                  ) : (
                    <div className="alerts-list">
                      {untreatedAlerts.map(sensor => {
                        const { dev_eui } = sensor;
                        const { site, batiment, salle } = sensor.location;
                        const { smoke_level, temperature } = sensor.readings;
                        const isAcked = acknowledgedAlerts[dev_eui] && acknowledgedAlerts[dev_eui].type === 'fire';
                        const duration = alertTimers[dev_eui];
                        
                        return (
                          <div key={dev_eui} className={`alert-item-hospital ${isAcked ? 'acked' : 'unacked'}`}>
                            <div className="alert-item-header">
                              <span className="alert-item-location">{site.toUpperCase()} — {salle.replace('salle_', 'Salle ')}</span>
                              <span className="alert-item-time font-mono">
                                <Clock size={12} style={{ marginRight: '3px' }} />
                                {formatAlertDuration(duration)}
                              </span>
                            </div>
                            <div className="alert-item-body">
                              <div className="alert-values">
                                <span className="alert-pill font-mono">{smoke_level} ppm</span>
                                <span className="alert-pill font-mono">{temperature} °C</span>
                              </div>
                              
                              {isAcked ? (
                                <span className="acked-badge">
                                  <ShieldCheck size={14} />
                                  <span>Acquittée</span>
                                </span>
                              ) : (
                                <button 
                                  className="ack-btn-red"
                                  onClick={() => openAcknowledgePanel(sensor)}
                                >
                                  Traiter
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </section>

              {/* Alertes Techniques & Maintenance */}
              <section className="quadrant-card">
                <div className="card-header">
                  <div className="card-title-container">
                    <Wrench size={18} className="glow-warning" />
                    <h2 className="card-title">Maintenance & Diagnostic</h2>
                  </div>
                  <span className={`badge-count ${technicalAlerts.length > 0 ? 'warning' : ''}`} style={{ background: technicalAlerts.length > 0 ? 'var(--clr-warning)' : '', color: technicalAlerts.length > 0 ? '#fff' : '' }}>
                    {technicalAlerts.length}
                  </span>
                </div>
                <div className="card-content">
                  {technicalAlerts.length === 0 ? (
                    <div className="empty-state">
                      <CheckCircle size={32} className="text-success" />
                      <p>Tous les capteurs fonctionnent normalement.</p>
                    </div>
                  ) : (
                    <div className="alerts-list">
                      {technicalAlerts.map(sensor => {
                        const { dev_eui } = sensor;
                        const { site, batiment, salle } = sensor.location;
                        const { battery_level, status } = sensor.readings;
                        const isOffline = status === "inactive" || status === "connecting";
                        
                        const isAcked = !!acknowledgedAlerts[dev_eui];
                        
                        return (
                          <div key={dev_eui} className="alert-item-hospital warning" style={{ borderColor: 'var(--clr-warning)', backgroundColor: 'rgba(245, 158, 11, 0.03)' }}>
                            <div className="alert-item-header">
                              <span className="alert-item-location">{site.toUpperCase()} — {salle.replace('salle_', 'Salle ')}</span>
                              {isOffline ? (
                                <span className="acked-badge" style={{ color: 'var(--text-muted)', borderColor: 'var(--border-subtle)', background: 'transparent' }}>
                                  Hors-ligne
                                </span>
                              ) : (
                                <span className="acked-badge" style={{ color: 'var(--clr-warning)', borderColor: 'rgba(245, 158, 11, 0.3)', background: 'rgba(245, 158, 11, 0.05)' }}>
                                  Batterie Faible
                                </span>
                              )}
                            </div>
                            <div className="alert-item-body" style={{ marginTop: '0.4rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span className="sensor-eui-lbl">ID: {dev_eui.slice(-4)} | Ref: <span className="font-mono">{dev_eui}</span></span>
                              
                              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                {!isOffline && (
                                  <span className="alert-pill font-mono" style={{ color: 'var(--clr-warning)', borderColor: 'rgba(245, 158, 11, 0.2)' }}>
                                    {battery_level}%
                                  </span>
                                )}
                                
                                {isAcked ? (
                                  <span className="acked-badge" style={{ color: 'var(--clr-success)', borderColor: 'rgba(29, 158, 117, 0.3)', background: 'rgba(29, 158, 117, 0.05)', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                                    <ShieldCheck size={12} />
                                    <span>Pris en charge</span>
                                  </span>
                                ) : (
                                  <button 
                                    className="ack-btn-warning"
                                    onClick={() => openAcknowledgePanel(sensor, 'technical')}
                                    style={{
                                      backgroundColor: 'var(--clr-warning)',
                                      color: '#0f172a',
                                      border: 'none',
                                      padding: '0.2rem 0.6rem',
                                      borderRadius: '4px',
                                      fontSize: '0.65rem',
                                      fontWeight: '800',
                                      cursor: 'pointer',
                                      boxShadow: '0 2px 4px rgba(245, 158, 11, 0.15)'
                                    }}
                                  >
                                    Gérer
                                  </button>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </section>

            </div>

            {/* Colonne de Droite : La Carte Mentale interactive */}
            <div className="dashboard-content-column">
              <section className="quadrant-card">
                <div className="card-header">
                  <div className="card-title-container">
                    <Activity size={18} className="glow-success" />
                    <h2 className="card-title">Carte Mentale & Topologie Réseau</h2>
                  </div>
                </div>
                <div className="card-content" style={{ overflow: 'hidden', padding: 0 }}>
                  <div className="graph-container">
                    <svg viewBox="0 0 680 400" className="graph-svg">
                      <defs>
                        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M2 1L8 5L2 9" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </marker>
                      </defs>

                      {/* Rendu dynamique des Hubs et des Capteurs en fonction des données */}
                      {(() => {
                        const uniqueSites = [...new Set(Object.values(sensors).map(s => s.location.site))].sort();
                        const totalSites = uniqueSites.length;
                        const width = 680;
                        const padding = 100;
                        const availableWidth = width - 2 * padding;
                        
                        const hubCoordinates = {};
                        uniqueSites.forEach((siteName, j) => {
                          const x = totalSites === 1 ? width / 2 : padding + (j * (availableWidth / (totalSites - 1)));
                          hubCoordinates[siteName] = x;
                        });

                        return (
                          <>
                            {/* Liaisons centrale -> hubs */}
                            {uniqueSites.map(siteName => {
                              const xHub = hubCoordinates[siteName];
                              let strokeColor = '#378ADD'; // Paris style bleu
                              if (siteName === 'lyon') strokeColor = '#7F77DD'; // Lyon style violet
                              else if (siteName === 'strasbourg') strokeColor = '#10B981'; // Strasbourg style vert
                              else if (siteName === 'marseille') strokeColor = '#EF4444'; // Marseille style rouge
                              
                              return (
                                <line
                                  key={`link-central-${siteName}`}
                                  x1="340" y1="80"
                                  x2={xHub} y2="138"
                                  stroke={strokeColor}
                                  strokeWidth="1.5"
                                  markerEnd="url(#arrow)"
                                />
                              );
                            })}

                            {/* Liaisons hubs -> capteurs */}
                            {Object.values(sensors).map((sensor) => {
                              const { dev_eui } = sensor;
                              const { site } = sensor.location;
                              const { status, smoke_level, temperature } = sensor.readings;
                              const isOffline = status === 'inactive' || status === 'connecting';
                              const isFire = (smoke_level >= 50.0 || temperature >= 60.0) && !inhibitedSensors[dev_eui] && !(acknowledgedAlerts[dev_eui] && acknowledgedAlerts[dev_eui].type === 'fire');
                              
                              const xHub = hubCoordinates[site] || 340;
                              const siteSensors = Object.values(sensors).filter(s => s.location.site === site);
                              const idx = siteSensors.findIndex(s => s.dev_eui === dev_eui);
                              const M = siteSensors.length;
                              const sensorGap = 65;
                              const xSensor = xHub + (idx - (M - 1) / 2) * sensorGap;

                              let strokeColor = '#1D9E75'; // Normal
                              if (isOffline) strokeColor = '#888780';
                              else if (isFire) strokeColor = '#E24B4A';
                              else if (inhibitedSensors[dev_eui]) strokeColor = '#b58c1e';

                              return (
                                <line
                                  key={`link-sensor-${dev_eui}`}
                                  x1={xHub} y1="182"
                                  x2={xSensor} y2="236"
                                  stroke={strokeColor}
                                  strokeWidth={isFire ? 2 : 1.5}
                                  strokeDasharray={isOffline ? '4 4' : isFire ? '5 5' : undefined}
                                  markerEnd="url(#arrow)"
                                />
                              );
                            })}

                            {/* Nœuds centrale */}
                            <g className="node-group node-survey-group">
                              <rect x="270" y="40" width="140" height="40" rx="8" className="node-rect node-rect-survey" strokeWidth="0.5" />
                              <text x="340" y="60" textAnchor="middle" dominantBaseline="central" className="node-text-title">IBMH Survey</text>
                            </g>

                            {/* Nœuds Hubs */}
                            {uniqueSites.map((siteName) => {
                              const xHub = hubCoordinates[siteName];
                              let rectClass = "node-rect-paris";
                              if (siteName === 'lyon') rectClass = "node-rect-lyon";
                              else if (siteName !== 'paris') rectClass = "node-rect-survey";
                              
                              return (
                                <g key={`hub-${siteName}`} className="node-group node-hub-group">
                                  <rect
                                    x={xHub - 60}
                                    y="140"
                                    width="120"
                                    height="40"
                                    rx="8"
                                    className={`node-rect ${rectClass}`}
                                    strokeWidth="0.5"
                                  />
                                  <text x={xHub} y="160" textAnchor="middle" dominantBaseline="central" className="node-text-title">
                                    Hub {siteName.charAt(0).toUpperCase() + siteName.slice(1)}
                                  </text>
                                </g>
                              );
                            })}

                            {/* Nœuds capteurs actifs */}
                            {Object.values(sensors).map((sensor) => {
                              const { dev_eui } = sensor;
                              const { site, salle } = sensor.location;
                              const { status, smoke_level, temperature, battery_level } = sensor.readings;
                              const isOffline = status === 'inactive' || status === 'connecting';
                              const isFire = (smoke_level >= 50.0 || temperature >= 60.0) && !inhibitedSensors[dev_eui] && !(acknowledgedAlerts[dev_eui] && acknowledgedAlerts[dev_eui].type === 'fire');
                              const isInhibited = inhibitedSensors[dev_eui];
                              const isLowBattery = battery_level > 0 && battery_level < 20;

                              const xHub = hubCoordinates[site] || 340;
                              const siteSensors = Object.values(sensors).filter(s => s.location.site === site);
                              const idx = siteSensors.findIndex(s => s.dev_eui === dev_eui);
                              const M = siteSensors.length;
                              const sensorGap = 65;
                              const xSensor = xHub + (idx - (M - 1) / 2) * sensorGap;

                              let nodeClass = 'node-sensor';
                              if (isFire) nodeClass += ' node-sensor-fire';
                              else if (isLowBattery) nodeClass += ' node-sensor-technical';
                              else if (isOffline) nodeClass += ' node-sensor-offline';
                              else if (isInhibited) nodeClass += ' node-sensor-inhibited';
                              else nodeClass += ' node-sensor-normal';

                              return (
                                <g
                                  key={`sensor-${dev_eui}`}
                                  className={nodeClass}
                                  style={{ cursor: 'pointer' }}
                                  onClick={() => isFire && !acknowledgedAlerts[dev_eui] && openAcknowledgePanel(sensor)}
                                >
                                  <circle cx={xSensor} cy="258" r="22" strokeWidth={isFire ? 1.5 : 0.5} strokeDasharray={isOffline ? '3 3' : undefined} />
                                  <text x={xSensor} y="258" textAnchor="middle" dominantBaseline="central" className="node-text-sub">
                                    {salle.replace('salle_', 'S.')}
                                  </text>
                                </g>
                              );
                            })}
                          </>
                        );
                      })()}

                      {/* Légende */}
                      <g className="node-legend">
                        <circle cx="80" cy="340" r="5" className="legend-dot legend-dot-normal" />
                        <text x="92" y="340" dominantBaseline="central" className="node-text-sub">En ligne</text>
                        
                        <circle cx="180" cy="340" r="5" className="legend-dot legend-dot-fire" />
                        <text x="192" y="340" dominantBaseline="central" className="node-text-sub">Danger Feu</text>
                        
                        <circle cx="290" cy="340" r="5" className="legend-dot legend-dot-offline" />
                        <text x="302" y="340" dominantBaseline="central" className="node-text-sub">Hors ligne</text>

                        <circle cx="400" cy="340" r="5" style={{ fill: '#b58c1e', stroke: 'rgba(181, 140, 30, 0.4)', strokeWidth: 1 }} />
                        <text x="412" y="340" dominantBaseline="central" className="node-text-sub">Inhibé</text>

                        <circle cx="510" cy="340" r="5" style={{ fill: '#f59e0b', stroke: 'rgba(245, 158, 11, 0.4)', strokeWidth: 1 }} />
                        <text x="522" y="340" dominantBaseline="central" className="node-text-sub">Alerte Tech / Bat.</text>
                      </g>
                    </svg>
                  </div>
                </div>
              </section>
            </div>
          </div>
        )}

        {/* TAB 2 : ÉTAT DES SALLES (Grille dynamique style Hôpital William Morey) */}
        {activeTab === 'rooms' && (
          <section className="rooms-grid-tab">
            <div className="search-bar-container">
              <Search size={18} className="search-icon" />
              <input 
                type="text" 
                placeholder="Rechercher une salle, un bâtiment ou un identifiant EUI..." 
                className="search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Rendu dynamique des groupes par site */}
            {(() => {
              const uniqueSites = [...new Set(Object.values(sensors).map(s => s.location.site))].sort();
              return uniqueSites.map(siteName => {
                const siteSensors = filteredSensors.filter(s => s.location.site === siteName);
                if (siteSensors.length === 0) return null;

                return (
                  <div key={`group-${siteName}`} className="rooms-group-section">
                    <h3 className="group-section-title">CHAMBRE DE SUPERVISION — {siteName.toUpperCase()}</h3>
                    <div className="rooms-cards-grid">
                      {siteSensors.map(sensor => {
                        const { dev_eui } = sensor;
                        const { batiment, salle } = sensor.location;
                        const { smoke_level, temperature, battery_level, status } = sensor.readings;
                        const isOffline = status === "inactive" || status === "connecting";
                        const isFire = (smoke_level >= 50.0 || temperature >= 60.0) && !inhibitedSensors[dev_eui];
                        const isPrealarm = ((smoke_level >= 25.0 && smoke_level < 50.0) || (temperature >= 45.0 && temperature < 60.0)) && !isFire && !inhibitedSensors[dev_eui];
                        const isInhibited = inhibitedSensors[dev_eui];
                        const isLowBattery = battery_level > 0 && battery_level < 20;
                        const isFireAcked = acknowledgedAlerts[dev_eui] && acknowledgedAlerts[dev_eui].type === 'fire';
                        const isTechAcked = acknowledgedAlerts[dev_eui] && acknowledgedAlerts[dev_eui].type === 'technical';

                        let cardClass = "room-supervision-card";
                        if (isFire) cardClass += " card-state-fire";
                        else if (isLowBattery) cardClass += " card-state-technical";
                        else if (isOffline) cardClass += " card-state-offline";
                        else if (isPrealarm) cardClass += " card-state-prealarm";
                        else if (isInhibited) cardClass += " card-state-inhibited";
                        
                        return (
                          <div key={dev_eui} className={cardClass}>
                            <div className="room-card-header">
                              <div className="room-card-title">
                                <h4>{batiment.replace('batiment_', 'Bât. ')} — {salle.replace('salle_', 'Salle ')}</h4>
                                <span className="room-card-subtitle">Capteur Optique & Thermique</span>
                              </div>
                              {/* Alerte Incendie */}
                              {isFire && !isFireAcked && (
                                <button className="card-alert-btn" onClick={() => openAcknowledgePanel(sensor, 'fire')}>Traiter</button>
                              )}
                              {/* Alerte Technique (Batterie faible ou Hors-ligne, masqué si incendie actif) */}
                              {(isLowBattery || isOffline) && !isFire && !isTechAcked && (
                                <button 
                                  className="card-alert-btn warning" 
                                  onClick={() => openAcknowledgePanel(sensor, 'technical')}
                                  style={{
                                    backgroundColor: 'var(--clr-warning)',
                                    color: '#0f172a',
                                    boxShadow: '0 2px 4px rgba(245, 158, 11, 0.2)',
                                    animation: 'none'
                                  }}
                                >
                                  Gérer
                                </button>
                              )}
                              {/* Statut Pris en Charge / Géré */}
                              {((isFire && isFireAcked) || ((isLowBattery || isOffline) && isTechAcked)) && (
                                <span className="acked-badge" style={{ color: 'var(--clr-success)', borderColor: 'rgba(29, 158, 117, 0.3)', background: 'rgba(29, 158, 117, 0.05)', fontSize: '0.65rem', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                                  <ShieldCheck size={12} />
                                  <span>Géré</span>
                                </span>
                              )}
                            </div>

                            <div className="room-card-body">
                              <div className="room-telemetry-col">
                                <div className="telemetry-item">
                                  <span className="telemetry-value font-mono">{isOffline ? 'N/A' : `${temperature}°C`}</span>
                                  <span className="telemetry-lbl">Température</span>
                                </div>
                                <div className="telemetry-item">
                                  <span className="telemetry-value font-mono">{isOffline ? 'N/A' : `${smoke_level} ppm`}</span>
                                  <span className="telemetry-lbl">Fumée (Optique)</span>
                                </div>
                              </div>

                              <div className="room-thresholds-col">
                                <div className="threshold-line">
                                  <span className="threshold-lbl">Seuil haut</span>
                                  <span className="threshold-val font-mono">60°C / 50 ppm</span>
                                </div>
                                <div className="threshold-line">
                                  <span className="threshold-lbl">Seuil préalarme</span>
                                  <span className="threshold-val font-mono">45°C / 25 ppm</span>
                                </div>
                                <div className="threshold-line font-mono">
                                  <span className="threshold-lbl">Batterie</span>
                                  <span className={`threshold-val ${battery_level < 20 ? 'text-danger animate-pulse' : ''}`}>{isOffline ? 'N/A' : `${battery_level}%`}</span>
                                </div>
                              </div>
                            </div>

                            <div className="room-card-footer">
                              <span className="sensor-eui-lbl">EUI: <span className="font-mono">{dev_eui}</span></span>
                              <button 
                                className={`inhibit-toggle-btn ${isInhibited ? 'inhibited' : ''}`}
                                onClick={() => toggleInhibit(dev_eui)}
                              >
                                <EyeOff size={12} />
                                {isInhibited ? 'Désinhiber' : 'Inhiber'}
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              });
            })()}
          </section>
        )}

        {/* TAB 3 : CONSOLE DE CONTRÔLE PHYSIQUE */}
        {activeTab === 'control' && (
          <section className="control-console-tab">
            <div className="quadrant-card control-console-card">
              <div className="card-header">
                <div className="card-title-container">
                  <ShieldAlert size={18} className="glow-warning" />
                  <h2 className="card-title">Console de Contrôle Physique</h2>
                </div>
              </div>
              <div className="card-content">
                <div className="control-rack-panel">
                  {/* Vis du rack skeuomorphe */}
                  <div className="rack-screw top-left"></div>
                  <div className="rack-screw top-right"></div>
                  <div className="rack-screw bottom-left"></div>
                  <div className="rack-screw bottom-right"></div>

                  <div className="rack-title">COMMANDE GÉNÉRALE ACTUATEURS</div>
                  
                  <div className="rack-grid">
                    {Object.values(sensors).map(sensor => {
                      const { dev_eui } = sensor;
                      const { site, batiment, salle } = sensor.location;
                      const { siren, light, status } = sensor.readings;
                      const isOffline = status === "inactive" || status === "connecting" || inhibitedSensors[dev_eui];
                      
                      return (
                        <div key={dev_eui} className={`rack-row ${isOffline ? 'rack-row-offline' : ''}`}>
                          <div className="rack-label-container">
                            <span className="rack-label-room">
                              {batiment.replace('batiment_', 'Bât. ')} — {salle.replace('salle_', 'Salle ')} ({site.toUpperCase()})
                            </span>
                            {inhibitedSensors[dev_eui] && <span className="badge-inhibited" style={{ marginLeft: '8px' }}>INHIBÉ</span>}
                          </div>
                          
                          <div className="rack-buttons-group">
                            {/* Commande Sirène */}
                            <div className="rack-control-block">
                              <div className="rack-led-container">
                                <div className={`led-bulb led-red ${siren === 'ON' && !isOffline ? 'led-active' : ''} ${isOffline ? 'led-offline' : ''}`}></div>
                                <span className="led-lbl">Sirène</span>
                              </div>
                              <button 
                                className={`rack-push-btn ${siren === 'ON' && !isOffline ? 'btn-pushed' : ''}`}
                                onClick={() => sendCommand(sensor, 'siren', siren === 'ON' ? 'OFF' : 'ON')}
                                disabled={isOffline}
                              >
                                {siren === 'ON' ? 'STOP' : 'TEST'}
                              </button>
                            </div>

                            {/* Commande Gyrophare */}
                            <div className="rack-control-block">
                              <div className="rack-led-container">
                                <div className={`led-bulb led-yellow ${light === 'ON' && !isOffline ? 'led-active' : ''} ${isOffline ? 'led-offline' : ''}`}></div>
                                <span className="led-lbl">Gyr.</span>
                              </div>
                              <button 
                                className={`rack-push-btn ${light === 'ON' && !isOffline ? 'btn-pushed' : ''}`}
                                onClick={() => sendCommand(sensor, 'light', light === 'ON' ? 'OFF' : 'ON')}
                                disabled={isOffline}
                              >
                                {light === 'ON' ? 'ÉTEINDRE' : 'ALLUMER'}
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

      </main>

      {/* OVERLAY D'ACQUITTEMENT D'ALERTE (Style Hôpital William Morey) */}
      {selectedAlert && (() => {
        const motifsOptions = activeAlertPanelType === 'fire' ? [
          "Surchauffe machine / Surcharge",
          "Fausse alerte (poussière/vapeur)",
          "Exercice de sécurité / Test",
          "Court-circuit / Problème électrique",
          "Dysfonctionnement capteur",
          "Porte ou enceinte mal isolée"
        ] : [
          "Usure normale de la batterie",
          "Déconnexion radio LoRaWAN",
          "Capteur arraché / Vandalisé",
          "Changement d'emplacement de la pièce",
          "Incident matériel / Panne capteur",
          "Interférences radio / Obstacle"
        ];

        const actionsOptions = activeAlertPanelType === 'fire' ? [
          "Appel des secours (18/112)",
          "Ventilation forcée de la salle",
          "Évacuation de la zone concernée",
          "Coupure d'urgence de l'alimentation",
          "Aucune anomalie constatée",
          "Intervention équipe technique"
        ] : [
          "Remplacement de la pile / batterie",
          "Redémarrage du boîtier",
          "Repositionnement physique du capteur",
          "Remplacement complet de l'équipement",
          "Appel au support technique / Constructeur",
          "Enquête sur site pour perte de liaison"
        ];

        return (
          <div className="ack-overlay-backdrop">
            <div className="ack-modal-container">
              {/* Volet gauche (Alerte / Rouge Incendie ou Orange Technique) */}
              <div className={`ack-left-panel ${activeAlertPanelType === 'technical' ? 'technical' : ''}`}>
                <div className="ack-left-header">
                  <h3>{selectedAlert.location.site.toUpperCase()} — {selectedAlert.location.salle.toUpperCase()}</h3>
                  <span className="ack-left-subtitle">{selectedAlert.location.batiment.replace('batiment_', 'Bâtiment ')}</span>
                </div>
                
                <div className="ack-left-alert-values">
                  {activeAlertPanelType === 'fire' ? (
                    <>
                      <span className="ack-big-value font-mono">
                        {selectedAlert.readings.smoke_level} ppm
                      </span>
                      <span className="ack-big-value font-mono" style={{ fontSize: '1.8rem', marginTop: '0.5rem' }}>
                        {selectedAlert.readings.temperature} °C
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="ack-big-value" style={{ fontSize: '2.0rem' }}>
                        {selectedAlert.readings.status === 'inactive' ? 'HORS-LIGNE' : 'BATTERIE'}
                      </span>
                      <span className="ack-big-value font-mono" style={{ fontSize: '1.8rem', marginTop: '0.5rem' }}>
                        {selectedAlert.readings.status === 'inactive' ? '⚠️ Liaison perdue' : `🔋 ${selectedAlert.readings.battery_level}%`}
                      </span>
                    </>
                  )}
                </div>

                <div className="ack-left-details">
                  {activeAlertPanelType === 'fire' ? (
                    <>
                      <div className="ack-details-row">
                        <span className="ack-detail-lbl">Alerte active depuis :</span>
                        <span className="ack-detail-val font-mono">{formatAlertDuration(alertTimers[selectedAlert.dev_eui])}</span>
                      </div>
                      <div className="ack-details-row">
                        <span className="ack-detail-lbl">Date du déclenchement :</span>
                        <span className="ack-detail-val font-mono">{alertTriggers[selectedAlert.dev_eui]?.timestamp || 'N/A'}</span>
                      </div>
                      <div className="ack-details-row">
                        <span className="ack-detail-lbl">Type d'alerte :</span>
                        <span className="ack-detail-val">Dépassement du seuil critique</span>
                      </div>
                      <div className="ack-details-row">
                        <span className="ack-detail-lbl">Valeur seuil critique :</span>
                        <span className="ack-detail-val font-mono">50 ppm / 60 °C</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="ack-details-row">
                        <span className="ack-detail-lbl">Signalé le :</span>
                        <span className="ack-detail-val font-mono">{new Date().toLocaleDateString()}</span>
                      </div>
                      <div className="ack-details-row">
                        <span className="ack-detail-lbl">Type d'anomalie :</span>
                        <span className="ack-detail-val">
                          {selectedAlert.readings.status === 'inactive' ? 'Panne de communication' : 'Batterie faible (< 20%)'}
                        </span>
                      </div>
                      <div className="ack-details-row">
                        <span className="ack-detail-lbl">Seuil critique :</span>
                        <span className="ack-detail-val font-mono">Batterie &lt; 20% ou Inactivité &gt; 30s</span>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Volet droit (Formulaire d'acquittement) */}
              <div className="ack-right-panel">
                <h2 className="ack-right-title">Informations alerte</h2>
                
                {/* 1. Motif de l'alerte */}
                <div className="form-section">
                  <h4 className="section-label">Motif de l'alerte <span className="required">*</span></h4>
                  <div className="checkbox-grid">
                    {motifsOptions.map(motif => (
                      <label key={motif} className="checkbox-label">
                        <input 
                          type="checkbox" 
                          checked={tempMotifs.includes(motif)}
                          onChange={(e) => {
                            if (e.target.checked) setTempMotifs([...tempMotifs, motif]);
                            else setTempMotifs(tempMotifs.filter(m => m !== motif));
                          }}
                        />
                        <span>{motif}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* 2. Action menée */}
                <div className="form-section">
                  <h4 className="section-label">Action <span className="required">*</span></h4>
                  <div className="checkbox-grid">
                    {actionsOptions.map(action => (
                      <label key={action} className="checkbox-label">
                        <input 
                          type="checkbox" 
                          checked={tempActions.includes(action)}
                          onChange={(e) => {
                            if (e.target.checked) setTempActions([...tempActions, action]);
                            else setTempActions(tempActions.filter(a => a !== action));
                          }}
                        />
                        <span>{action}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* 3. Impact */}
                <div className="form-section">
                  <h4 className="section-label">Impact <span className="required">*</span></h4>
                  <div className="radio-group-row">
                    {["Aucun", "Mineur", "Majeur"].map(impact => (
                      <label key={impact} className="radio-label">
                        <input 
                          type="radio" 
                          name="impact" 
                          value={impact}
                          checked={tempImpact === impact}
                          onChange={() => setTempImpact(impact)}
                        />
                        <span>{impact}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* 4. Commentaires */}
                <div className="form-section">
                  <h4 className="section-label">Commentaires ou autres précisions</h4>
                  <textarea 
                    className="form-textarea"
                    placeholder="Saisissez des détails additionnels sur l'intervention ici..."
                    value={tempComment}
                    onChange={(e) => setTempComment(e.target.value)}
                  />
                </div>

                {/* Pied de formulaire */}
                <div className="ack-form-footer">
                  <button className="btn-cancel" onClick={() => setSelectedAlert(null)}>Annuler</button>
                  <button 
                    className="btn-save-ack" 
                    onClick={handleSaveAcknowledge}
                    disabled={tempMotifs.length === 0 && tempActions.length === 0}
                  >
                    Enregistrer l'acquittement
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

    </div>
  );
}

export default App;
