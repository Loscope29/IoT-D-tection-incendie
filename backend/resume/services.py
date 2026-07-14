import logging
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.db import transaction
from .models import RawEvent, PeriodicSummary, WeeklyBriefing, MonthlyReport
from .llm_client import generate_llm_content
from .prompts import (
    get_periodic_summary_prompt,
    get_weekly_briefing_prompt,
    get_monthly_report_prompt
)

logger = logging.getLogger("resume.services")

def format_raw_event_for_llm(event: RawEvent) -> str:
    """
    Formate un événement brut sous forme de chaîne lisible pour le LLM.
    """
    topic = event.topic
    payload = event.payload or {}
    t_str = event.created_at.strftime("%Y-%m-%d %H:%M:%S")
    
    # Topic d'acquittement
    if "acknowledgement" in topic or "acquittement" in topic:
        dev_eui = payload.get("dev_eui", "Inconnu")
        alert_type = payload.get("alert_type", "Inconnue")
        location = payload.get("location", {})
        loc_str = f"{location.get('site', '')}/{location.get('batiment', '')}/{location.get('salle', '')}"
        motifs = ", ".join(payload.get("motifs", [])) or "Aucun motif spécifié"
        actions = ", ".join(payload.get("actions", [])) or "Aucune action spécifiée"
        impact = payload.get("impact", "Aucun")
        comment = payload.get("comment", "")
        duration = payload.get("duration", 0)
        
        desc = (
            f"[{t_str}] ACQUITTEMENT d'alerte {alert_type} pour le capteur {dev_eui} ({loc_str}).\n"
            f"  - Motifs : {motifs}\n"
            f"  - Actions : {actions}\n"
            f"  - Impact : {impact}\n"
            f"  - Commentaire : {comment or 'Sans précision'}\n"
            f"  - Durée de l'alerte : {duration} secondes"
        )
        return desc

    # Topics IoT standard (télémétrie ou alerte)
    location = payload.get("location", {})
    loc_str = f"{location.get('site', 'Inconnu')}/{location.get('batiment', 'Inconnu')}/{location.get('salle', 'Inconnu')}/{location.get('machine', 'Inconnu')}"
    data_type = payload.get("data_type", "data")
    value = payload.get("value", "N/A")
    
    if "alert" in topic:
        desc = f"[{t_str}]  ALERTE INCENDIE/FUMÉE ({data_type}) à {loc_str}. Valeur relevée : {value}."
    else:
        desc = f"[{t_str}] Télémétrie ({data_type}) à {loc_str}. Valeur relevée : {value}."
        
    return desc


def generate_periodic_summary() -> PeriodicSummary:
    """
    Prend tous les RawEvent du jour actuel, les regroupe et appelle le LLM pour générer ou mettre à jour le résumé quotidien.
    """
    logger.info("Début de la génération/mise à jour du résumé quotidien...")
    
    now = timezone.localtime(timezone.now())
    # Début et fin de la journée actuelle
    start_of_day = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
    end_of_day = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
    
    # 1. Sélectionner tous les événements bruts de la journée actuelle
    day_events = list(RawEvent.objects.filter(created_at__range=(start_of_day, end_of_day)).order_by('created_at'))
    
    if not day_events:
        logger.info("Aucun événement brut aujourd'hui à résumer.")
        return None
        
    logger.info(f"Traitement de {len(day_events)} événements pour la journée du {now.date()}.")
    
    # Formater les événements
    events_formatted = [format_raw_event_for_llm(e) for e in day_events]
    events_text = "\n\n".join(events_formatted)
    
    # Déterminer la période temporelle
    start_time = day_events[0].created_at
    end_time = day_events[-1].created_at
    
    # Prompt pour le LLM extrait de prompts.py
    prompt = get_periodic_summary_prompt(
        start_time.strftime('%Y-%m-%d %H:%M:%S'),
        end_time.strftime('%Y-%m-%d %H:%M:%S'),
        events_text
    )
    
    # 2. Appel au LLM (I/O réseau lente hors transaction)
    summary_text = generate_llm_content(prompt)
    
    if not summary_text:
        logger.error("Le LLM n'a pas retourné de résumé.")
        return None
        
    # 3. Transaction d'écriture ultra-rapide en base (création ou mise à jour du résumé de la journée)
    with transaction.atomic():
        summary = PeriodicSummary.objects.filter(start_time__range=(start_of_day, end_of_day)).first()
        
        if summary:
            logger.info(f"Mise à jour du résumé quotidien existant #{summary.id}.")
            summary.summary_text = summary_text
            summary.events_count = len(day_events)
            summary.end_time = end_time
            summary.save()
        else:
            logger.info("Création d'un nouveau résumé quotidien.")
            summary = PeriodicSummary.objects.create(
                summary_text=summary_text,
                events_count=len(day_events),
                start_time=start_of_day,
                end_time=end_time
            )
        
        # Marquer les événements traités (optionnel, pour compatibilité)
        RawEvent.objects.filter(id__in=[e.id for e in day_events]).update(processed=True)
        
    logger.info(f"Résumé quotidien #{summary.id} généré/mis à jour avec succès.")
    return summary


def generate_weekly_briefing() -> WeeklyBriefing:
    """
    Prend tous les résumés quotidiens de la semaine actuelle et génère ou met à jour le briefing hebdomadaire.
    """
    logger.info("Début de la génération/mise à jour du briefing hebdomadaire...")
    
    now = timezone.localtime(timezone.now()).date()
    # Déterminer le début et la fin de la semaine actuelle (du lundi au dimanche)
    start_of_week = now - timedelta(days=now.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # 1. Sélectionner tous les résumés de la semaine actuelle
    week_summaries = list(PeriodicSummary.objects.filter(start_time__date__range=(start_of_week, end_of_week)).order_by('start_time'))
    
    if not week_summaries:
        logger.info("Aucun résumé quotidien disponible cette semaine pour un briefing hebdomadaire.")
        return None
        
    logger.info(f"Compilation de {len(week_summaries)} résumés quotidiens pour la semaine du {start_of_week} au {end_of_week}.")
    summary_ids = [s.id for s in week_summaries]
    
    # Formater les résumés pour le LLM
    summaries_formatted = []
    for s in week_summaries:
        period_str = f"Date: {s.start_time.strftime('%Y-%m-%d')}"
        summaries_formatted.append(f"### Résumé Quotidien #{s.id} ({period_str})\n\n{s.summary_text}")
        
    summaries_text = "\n\n---\n\n".join(summaries_formatted)
    
    # Prompt pour le LLM extrait de prompts.py
    prompt = get_weekly_briefing_prompt(
        str(start_of_week),
        str(end_of_week),
        summaries_text
    )
    
    # 2. Appel au LLM (I/O réseau lente hors transaction)
    briefing_text = generate_llm_content(prompt, tier="heavy")
    
    if not briefing_text:
        logger.error("Le LLM n'a pas retourné de briefing hebdomadaire.")
        return None
        
    # 3. Transaction d'écriture ultra-rapide en base (création ou mise à jour)
    with transaction.atomic():
        briefing = WeeklyBriefing.objects.filter(start_date=start_of_week, end_date=end_of_week).first()
        
        if briefing:
            logger.info(f"Mise à jour du briefing hebdomadaire existant #{briefing.id}.")
            briefing.briefing_text = briefing_text
            briefing.save()
        else:
            logger.info("Création d'un nouveau briefing hebdomadaire.")
            briefing = WeeklyBriefing.objects.create(
                briefing_text=briefing_text,
                start_date=start_of_week,
                end_date=end_of_week
            )
        
        # Assigner ce briefing aux résumés périodiques correspondants
        PeriodicSummary.objects.filter(id__in=summary_ids).update(weekly_briefing=briefing)
        
    logger.info(f" Briefing hebdomadaire #{briefing.id} généré/mis à jour avec succès.")
    return briefing


def generate_monthly_report(year=None, month=None) -> MonthlyReport:
    """
    Prend tous les briefings hebdomadaires du mois actuel et génère ou met à jour le bilan mensuel.
    """
    logger.info("Début de la génération/mise à jour du bilan mensuel...")
    
    # Déterminer le mois actuel ou précédent si non spécifié
    today = timezone.localtime(timezone.now()).date()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
        
    # 1. Sélectionner tous les briefings du mois actuel
    month_briefings = list(WeeklyBriefing.objects.filter(start_date__year=year, start_date__month=month).order_by('start_date'))
    
    if not month_briefings:
        logger.info(f"Aucun briefing hebdomadaire disponible pour le mois {month}/{year}.")
        return None
        
    logger.info(f"Compilation de {len(month_briefings)} briefings hebdomadaires pour le mois {month}/{year}.")
    briefing_ids = [b.id for b in month_briefings]
    
    # Formater les briefings pour le LLM
    briefings_formatted = []
    for b in month_briefings:
        briefings_formatted.append(f"### Briefing Hebdomadaire #{b.id} (Du {b.start_date} au {b.end_date})\n\n{b.briefing_text}")
        
    briefings_text = "\n\n---\n\n".join(briefings_formatted)
    
    # Prompt pour le LLM extrait de prompts.py
    prompt = get_monthly_report_prompt(
        year,
        month,
        briefings_text
    )
    
    # 2. Appel au LLM (I/O réseau lente hors transaction)
    report_text = generate_llm_content(prompt, tier="heavy")
    
    if not report_text:
        logger.error("Le LLM n'a pas retourné de bilan mensuel.")
        return None
        
    # 3. Transaction d'écriture ultra-rapide en base (création ou mise à jour)
    with transaction.atomic():
        report = MonthlyReport.objects.filter(year=year, month=month).first()
        
        if report:
            logger.info(f"Mise à jour du bilan mensuel existant #{report.id}.")
            report.report_text = report_text
            report.save()
        else:
            logger.info("Création d'un nouveau bilan mensuel.")
            report = MonthlyReport.objects.create(
                report_text=report_text,
                year=year,
                month=month
            )
        
        # Assigner ce rapport aux briefings hebdomadaires correspondants
        WeeklyBriefing.objects.filter(id__in=briefing_ids).update(monthly_report=report)
        
    logger.info(f" Bilan mensuel #{report.id} généré/mis à jour avec succès pour {month}/{year}.")
    return report

