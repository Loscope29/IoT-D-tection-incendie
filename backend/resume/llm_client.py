import json
import re
import logging
import urllib.request
import urllib.error
from django.conf import settings

logger = logging.getLogger(__name__)

# Config par tier : modèle, longueur max, et timeout adaptés à chaque usage
TIER_CONFIG = {
    "light": {"model": "llama-3.1-8b-instant", "max_tokens": 512, "timeout": 15},
    "heavy": {"model": "llama-3.3-70b-versatile", "max_tokens": 2048, "timeout": 45},
}


def generate_llm_content(prompt: str, tier: str = "light") -> str:
    """
    Appelle Groq (si configuré) ou le LLM local (Llama via Ollama/vLLM) avec un prompt donné.
    En cas d'échec ou d'absence de configuration, retourne un résumé simulé de secours (mock).

    tier: "light" (résumé périodique) ou "heavy" (briefing hebdo/mensuel).
    Détermine le modèle Groq utilisé, la limite de tokens et le timeout.
    """
    config = TIER_CONFIG.get(tier, TIER_CONFIG["light"])
    groq_api_key = getattr(settings, "GROQ_API_KEY", "")

    if groq_api_key:
        api_url = "https://api.groq.com/openai/v1/chat/completions"
        # settings.GROQ_MODEL reste prioritaire si défini explicitement (utile en dev pour forcer un modèle)
        model_name = getattr(settings, "GROQ_MODEL", None) or config["model"]
        logger.info(f"Utilisation de l'API Groq (tier={tier}, modèle={model_name})...")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": config["max_tokens"],
            "stream": False,
        }
    else:
        api_url = getattr(settings, "LLM_API_URL", "http://localhost:11434/api/generate")
        model_name = getattr(settings, "LLM_MODEL", "llama3")

        if api_url.rstrip("/").endswith("11434"):
            api_url = api_url.rstrip("/") + "/api/generate"

        logger.info(f"Tentative d'appel LLM local (tier={tier}) sur {api_url} avec le modèle {model_name}...")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        if "chat/completions" in api_url:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": config["max_tokens"],
                "stream": False,
            }
        else:
            payload = {
                "model": model_name,
                "prompt": prompt,
                "options": {"temperature": 0.3, "num_predict": config["max_tokens"]},
                "stream": False,
            }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=config["timeout"]) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                if "chat/completions" in api_url:
                    return res_data["choices"][0]["message"]["content"].strip()
                else:
                    return res_data.get("response", res_data.get("text", "")).strip()
            else:
                logger.warning(f"Réponse LLM non-200 : {response.status}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        logger.error(f"❌ Échec de la connexion au LLM ({api_url}) - HTTP {e.code}: {e.reason} - Réponse: {error_body}")
    except Exception as e:
        logger.error(f"❌ Échec de la connexion au LLM ({api_url}) : {e}")

    logger.info("⚠️ Activation du mode démo / mock AI pour la génération du résumé.")
    return generate_mock_summary(prompt, tier)


def generate_mock_summary(prompt: str, tier: str = "light") -> str:
    """
    Génère une réponse simulée en fonction du tier demandé (plus fiable que deviner
    via des mots-clés dans le prompt, qui casse si le prompt est reformulé).
    Pour "heavy", on distingue hebdo/mensuel par mot-clé — cas moins critique
    car ce sont tous les deux des briefings agrégés au format similaire.
    """
    if tier == "heavy":
        if "mensuel" in prompt.lower() or "bilan" in prompt.lower():
            return (
                "###  Rapport Mensuel Simulé (Mode Démo)\n\n"
                "**Période** : Mois écoulé\n\n"
                "####  Analyse de tendance :\n"
                "- **Volume d'événements** : Stable par rapport au mois précédent. Les capteurs de télémétrie envoient régulièrement leurs signaux de santé.\n"
                "- **Sûreté incendie** : Aucun incendie réel détecté. Les alertes déclenchées étaient d'ordre technique ou de fausses alertes d'équipements.\n"
                "- **Performance de l'équipe** : Temps d'acquittement moyen inférieur à 2 minutes pour les alertes critiques.\n\n"
                "####  Recommandations de l'Assistant IA :\n"
                "1. Effectuer un nettoyage régulier du capteur de fumée de la Salle Machine au Bâtiment B (sensibilité accrue aux poussières).\n"
                "2. Planifier un contrôle des batteries des dispositifs de transmission Lora.\n\n"
                "*(Note : Ce rapport a été généré en mode démo car le LLM n'était pas joignable.)*"
            )
        return (
            "###  Bilan Hebdomadaire Simulé (Mode Démo)\n\n"
            "**Période** : Semaine écoulée\n\n"
            "####  Synthèse des alertes et événements :\n"
            "- **État global** : Le système a enregistré plusieurs événements de télémétrie et d'alerte cette semaine.\n"
            "- **Alertes marquantes** : Les seuils de température ou de fumée ont généré des notifications temporaires, mais la plupart ont été acquittées par les opérateurs.\n"
            "- **Disponibilité des capteurs** : Les transmissions de télémétrie sont restées stables sur l'ensemble des sites.\n\n"
            "####  Actions menées :\n"
            "- Tous les acquittements requis ont été enregistrés avec succès dans les temps.\n"
            "- Les motifs renseignés par les opérateurs font état de fausses alertes mineures dues à de la poussière ou des opérations de maintenance programmées.\n\n"
            "*(Note : Ce briefing a été généré en mode démo car le LLM n'était pas joignable.)*"
        )

    # tier == "light" : résumé périodique
    alerts_count = len(re.findall(r"alert|alerte", prompt, re.IGNORECASE))
    telemetry_count = len(re.findall(r"telemetry|télémétrie", prompt, re.IGNORECASE))
    acks_count = len(re.findall(r"acknowledgement|acquittement", prompt, re.IGNORECASE))

    return (
        "### ⚡ Synthèse des événements récents (Mode Démo)\n\n"
        f"- **Événements analysés** : {telemetry_count + alerts_count + acks_count} signaux reçus.\n"
        f"- **Alertes détectées** : {alerts_count} alerte(s) enregistrée(s).\n"
        f"- **Acquittements** : {acks_count} acquittement(s) d'opérateur.\n"
        f"- **Télémétrie** : {telemetry_count} rapports d'état reçus.\n\n"
        "####  Analyse :\n"
        "Le système fonctionne normalement. Les signaux reçus indiquent que la télémétrie de température et d'humidité reste dans les plages normales de sécurité. "
        "Les éventuelles alertes ont été rapidement prises en charge ou signalées. Aucun comportement anormal n'est à déclarer.\n\n"
        "*(Note : Ce résumé a été généré en mode démo car le LLM n'était pas joignable.)*"
    )