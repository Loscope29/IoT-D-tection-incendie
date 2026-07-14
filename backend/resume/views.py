from rest_framework import generics, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.utils import timezone
from .models import PeriodicSummary, WeeklyBriefing, MonthlyReport, RawEvent
from .serializers import (
    PeriodicSummarySerializer,
    WeeklyBriefingSerializer,
    MonthlyReportSerializer
)
from .services import (
    generate_periodic_summary,
    generate_weekly_briefing,
    generate_monthly_report
)

# Sérialiseurs de documentation pour Swagger (drf-spectacular)
class DashboardResponseSerializer(serializers.Serializer):
    latest_periodic = PeriodicSummarySerializer(allow_null=True)
    latest_weekly = WeeklyBriefingSerializer(allow_null=True)
    latest_monthly = MonthlyReportSerializer(allow_null=True)
    recent_summaries = PeriodicSummarySerializer(many=True)
    unprocessed_events_count = serializers.IntegerField()

class TriggerJobDetailSerializer(serializers.Serializer):
    type = serializers.CharField(help_text="Type de job (periodic_summary, weekly_briefing, monthly_report)")
    id = serializers.IntegerField(help_text="Identifiant de l'objet créé")
    events_count = serializers.IntegerField(required=False, help_text="Nombre d'événements traités (pour le résumé périodique)")
    message = serializers.CharField(help_text="Message de succès")

class TriggerResponseSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="Statut global ('success')")
    triggered_jobs_count = serializers.IntegerField(help_text="Nombre de jobs déclenchés et exécutés")
    triggered_jobs = TriggerJobDetailSerializer(many=True, help_text="Détails des jobs exécutés")
    message = serializers.CharField(help_text="Message global")


class PeriodicSummaryListAPIView(generics.ListAPIView):
    """
    API pour lister tous les résumés périodiques (10-15 minutes).
    """
    queryset = PeriodicSummary.objects.all().order_by('-created_at')
    serializer_class = PeriodicSummarySerializer


class PeriodicSummaryDetailAPIView(generics.RetrieveAPIView):
    """
    API pour récupérer un résumé périodique spécifique.
    """
    queryset = PeriodicSummary.objects.all()
    serializer_class = PeriodicSummarySerializer


class WeeklyBriefingListAPIView(generics.ListAPIView):
    """
    API pour lister tous les briefings hebdomadaires.
    """
    queryset = WeeklyBriefing.objects.all().order_by('-created_at')
    serializer_class = WeeklyBriefingSerializer


class WeeklyBriefingDetailAPIView(generics.RetrieveAPIView):
    """
    API pour récupérer un briefing hebdomadaire spécifique.
    """
    queryset = WeeklyBriefing.objects.all()
    serializer_class = WeeklyBriefingSerializer


class MonthlyReportListAPIView(generics.ListAPIView):
    """
    API pour lister tous les bilans mensuels.
    """
    queryset = MonthlyReport.objects.all().order_by('-created_at')
    serializer_class = MonthlyReportSerializer


class MonthlyReportDetailAPIView(generics.RetrieveAPIView):
    """
    API pour récupérer un bilan mensuel spécifique.
    """
    queryset = MonthlyReport.objects.all()
    serializer_class = MonthlyReportSerializer


class AssistantDashboardAPIView(APIView):
    """
    Endpoint agrégé conçu spécialement pour alimenter l'onglet Assistant du dashboard.
    Retourne le dernier résumé périodique, le dernier briefing hebdo, le dernier bilan mensuel,
    ainsi que l'historique récent des résumés périodiques.
    """
    serializer_class = DashboardResponseSerializer

    @extend_schema(
        summary="Données du dashboard de l'Assistant IA",
        description="Retourne le dernier résumé périodique, briefing hebdomadaire et bilan mensuel, ainsi que la liste des derniers résumés.",
        responses={200: DashboardResponseSerializer}
    )
    def get(self, request, *args, **kwargs):
        latest_periodic = PeriodicSummary.objects.order_by('-created_at').first()
        latest_weekly = WeeklyBriefing.objects.order_by('-created_at').first()
        latest_monthly = MonthlyReport.objects.order_by('-created_at').first()
        
        recent_summaries = PeriodicSummary.objects.order_by('-created_at')[:10]
        unprocessed_events_count = RawEvent.objects.filter(processed=False).count()
        
        # Déterminer le rapport actif à afficher
        now = timezone.localtime(timezone.now())
        active_report = None
        
        # 1. Règle Mensuelle : Le 30 du mois -> afficher le rapport mensuel
        if now.day == 30 and latest_monthly:
            active_report = {
                "type": "monthly",
                "title": "Bilan Mensuel",
                "subtitle": f"Mois de {latest_monthly.month}/{latest_monthly.year}",
                "content": latest_monthly.report_text,
                "created_at": latest_monthly.created_at.isoformat()
            }
        
        # 2. Règle Hebdomadaire : Le lundi entre 7h00 et 23h00 -> afficher le briefing hebdomadaire
        elif now.weekday() == 0 and 7 <= now.hour < 23 and latest_weekly:
            active_report = {
                "type": "weekly",
                "title": "Briefing Hebdomadaire",
                "subtitle": f"Semaine du {latest_weekly.start_date} au {latest_weekly.end_date}",
                "content": latest_weekly.briefing_text,
                "created_at": latest_weekly.created_at.isoformat()
            }
            
        # 3. Règle par défaut : Résumé quotidien/périodique
        elif latest_periodic:
            active_report = {
                "type": "periodic",
                "title": "Résumé Quotidien",
                "subtitle": f"Aujourd'hui, {latest_periodic.start_time.strftime('%d/%m/%Y')} (Dernière mise à jour à {latest_periodic.end_time.strftime('%H:%M:%S')})",
                "content": latest_periodic.summary_text,
                "created_at": latest_periodic.created_at.isoformat()
            }
        
        # Fallback si aucune règle n'a abouti mais qu'un autre rapport existe
        if not active_report:
            if latest_periodic:
                active_report = {
                    "type": "periodic",
                    "title": "Résumé Quotidien",
                    "subtitle": f"Aujourd'hui, {latest_periodic.start_time.strftime('%d/%m/%Y')} (Dernière mise à jour à {latest_periodic.end_time.strftime('%H:%M:%S')})",
                    "content": latest_periodic.summary_text,
                    "created_at": latest_periodic.created_at.isoformat()
                }
            elif latest_weekly:
                active_report = {
                    "type": "weekly",
                    "title": "Briefing Hebdomadaire",
                    "subtitle": f"Semaine du {latest_weekly.start_date} au {latest_weekly.end_date}",
                    "content": latest_weekly.briefing_text,
                    "created_at": latest_weekly.created_at.isoformat()
                }
            elif latest_monthly:
                active_report = {
                    "type": "monthly",
                    "title": "Bilan Mensuel",
                    "subtitle": f"Mois de {latest_monthly.month}/{latest_monthly.year}",
                    "content": latest_monthly.report_text,
                    "created_at": latest_monthly.created_at.isoformat()
                }
        
        data = {
            "active_report": active_report,
            "latest_periodic": PeriodicSummarySerializer(latest_periodic).data if latest_periodic else None,
            "latest_weekly": WeeklyBriefingSerializer(latest_weekly).data if latest_weekly else None,
            "latest_monthly": MonthlyReportSerializer(latest_monthly).data if latest_monthly else None,
            "recent_summaries": PeriodicSummarySerializer(recent_summaries, many=True).data,
            "unprocessed_events_count": unprocessed_events_count
        }
        return Response(data, status=status.HTTP_200_OK)


class AssistantManualTriggerAPIView(APIView):
    """
    Endpoint de déclenchement manuel.
    Permet de forcer immédiatement la compilation des résumés périodique, hebdomadaire et mensuel.
    Très utile pour tester la fonctionnalité sans attendre le planificateur de tâches de fond.
    """
    serializer_class = TriggerResponseSerializer

    @extend_schema(
        summary="Déclenchement manuel des compilations de l'Assistant",
        description="Force immédiatement la compilation de tous les événements bruts non traités en un résumé périodique, puis en un briefing hebdomadaire et bilan mensuel si possible.",
        responses={200: TriggerResponseSerializer}
    )
    def post(self, request, *args, **kwargs):

        triggered_jobs = []
        
        # 1. Générer le résumé périodique s'il y a des événements non traités
        unprocessed_exists = RawEvent.objects.filter(processed=False).exists()
        periodic_summary = None
        if unprocessed_exists:
            periodic_summary = generate_periodic_summary()
            if periodic_summary:
                triggered_jobs.append({
                    "type": "periodic_summary",
                    "id": periodic_summary.id,
                    "events_count": periodic_summary.events_count,
                    "message": "Résumé périodique généré avec succès."
                })
        
        # 2. Générer le briefing hebdomadaire s'il y a des résumés périodiques non associés
        unbriefed_exists = PeriodicSummary.objects.filter(weekly_briefing__isnull=True).exists()
        weekly_briefing = None
        if unbriefed_exists:
            weekly_briefing = generate_weekly_briefing()
            if weekly_briefing:
                triggered_jobs.append({
                    "type": "weekly_briefing",
                    "id": weekly_briefing.id,
                    "message": "Briefing hebdomadaire généré avec succès."
                })
                
        # 3. Générer le bilan mensuel s'il y a des briefings hebdos non associés
        unreported_exists = WeeklyBriefing.objects.filter(monthly_report__isnull=True).exists()
        monthly_report = None
        if unreported_exists:
            monthly_report = generate_monthly_report()
            if monthly_report:
                triggered_jobs.append({
                    "type": "monthly_report",
                    "id": monthly_report.id,
                    "message": "Bilan mensuel généré avec succès."
                })
                
        response_data = {
            "status": "success",
            "triggered_jobs_count": len(triggered_jobs),
            "triggered_jobs": triggered_jobs,
            "message": "Le déclenchement manuel des tâches de l'Assistant IA s'est exécuté."
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


