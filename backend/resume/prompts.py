# prompts.py

PERIODIC_SUMMARY_PROMPT_TEMPLATE = """Vous êtes un assistant IA supervisant un système de sécurité incendie industriel basé sur l'IoT.
Voici la liste des événements survenus entre le {start_time} et le {end_time} (UTC) :

{events_text}

Rédigez une synthèse claire, structurée et professionnelle en français sous format Markdown.
La synthèse doit inclure :
1. Une analyse rapide des anomalies détectées (alertes de température, fumée, etc.).
2. Un point sur les télémétries standards reçues.
3. Les acquittements et interventions d'opérateurs enregistrés (motifs et actions).
4. Une évaluation globale de l'état du site sur cette période (ex: Stable, Vigilance, Alerte).
Soyez concis et direct.
"""

WEEKLY_BRIEFING_PROMPT_TEMPLATE = """Vous êtes un expert en sécurité industrielle chargé de rédiger le rapport hebdomadaire.
Voici la compilation des résumés d'événements de la semaine du {start_date} au {end_date} :

{summaries_text}

Rédigez un briefing hebdomadaire complet, structuré et professionnel en français sous format Markdown.
Le briefing doit inclure :
- Une synthèse des incidents marquants (alertes réelles ou fausses alertes répétées).
- Une analyse de la réactivité et des actions des équipes (durée d'acquittement moyenne, motifs d'intervention).
- Des statistiques clés résumées (nombre d'événements, nombre d'alertes).
- Des recommandations d'actions correctives ou de maintenance préventive pour la semaine suivante.
Privilégiez une présentation soignée avec des listes à puces.
"""

MONTHLY_REPORT_PROMPT_TEMPLATE = """Vous êtes un directeur de la sécurité et de la maintenance d'un grand complexe industriel.
Voici les briefings hebdomadaires compilés pour le mois de {month}/{year} :

{briefings_text}

Rédigez un bilan mensuel de sécurité incendie en français sous format Markdown.
Ce document stratégique doit inclure :
1. Une vue globale de la sécurité incendie sur l'ensemble des sites (Bâtiments, machines) pour le mois écoulé.
2. Une analyse des tendances (augmentation ou baisse des alertes, pannes de capteurs, etc.).
3. L'efficacité opérationnelle des interventions (performance opérationnelle, motifs prédominants).
4. Des préconisations stratégiques à long terme (investissements matériel, formation des équipes, révision des protocoles).
Le ton doit être formel, précis et orienté vers l'amélioration continue.
"""

def get_periodic_summary_prompt(start_time_str: str, end_time_str: str, events_text: str) -> str:
    """
    Construit le prompt pour la synthèse périodique (10-15 min).
    """
    return PERIODIC_SUMMARY_PROMPT_TEMPLATE.format(
        start_time=start_time_str,
        end_time=end_time_str,
        events_text=events_text
    )

def get_weekly_briefing_prompt(start_date_str: str, end_date_str: str, summaries_text: str) -> str:
    """
    Construit le prompt pour le briefing hebdomadaire.
    """
    return WEEKLY_BRIEFING_PROMPT_TEMPLATE.format(
        start_date=start_date_str,
        end_date=end_date_str,
        summaries_text=summaries_text
    )

def get_monthly_report_prompt(year: int, month: int, briefings_text: str) -> str:
    """
    Construit le prompt pour le bilan mensuel.
    """
    return MONTHLY_REPORT_PROMPT_TEMPLATE.format(
        year=year,
        month=month,
        briefings_text=briefings_text
    )
