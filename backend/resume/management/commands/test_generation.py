import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from resume.models import RawEvent, PeriodicSummary, WeeklyBriefing, MonthlyReport
from resume.services import (
    generate_periodic_summary,
    generate_weekly_briefing,
    generate_monthly_report
)

class Command(BaseCommand):
    help = "Insere des evenements de test et genere un cycle complet (resume, briefing, bilan) pour tester l'IA"

    def write_safe(self, text, style_func=None):
        # Evite les plantages Unicode sur Windows Terminal en remplacant les caracteres incompatibles par des '?'
        safe_text = text.encode('cp1252', errors='replace').decode('cp1252')
        if style_func:
            self.stdout.write(style_func(safe_text))
        else:
            self.stdout.write(safe_text)

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("--- Nettoyage des anciennes donnees de test..."))
        RawEvent.objects.all().delete()
        PeriodicSummary.objects.all().delete()
        WeeklyBriefing.objects.all().delete()
        MonthlyReport.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("--- Insertion d'evenements IoT factices dans la base de donnees..."))
        
        # 1. Événement Télémétrie
        event_tel = RawEvent.objects.create(
            topic="fire-telemetry",
            payload={
                "mqtt_topic": "fire/Site-A/Batiment-1/Salle-Serveur/Machine-Rack3/telemetry",
                "timestamp": timezone.now().timestamp(),
                "location": {
                    "site": "Site-A",
                    "batiment": "Batiment-1",
                    "salle": "Salle-Serveur",
                    "machine": "Machine-Rack3"
                },
                "data_type": "temperature",
                "value": 42.5
            }
        )
        self.stdout.write(f"  - Cree : {event_tel}")

        # 2. Événement Alerte Fumée
        event_alert = RawEvent.objects.create(
            topic="fire-alerts",
            payload={
                "mqtt_topic": "fire/Site-A/Batiment-1/Salle-Serveur/Machine-Rack3/smoke",
                "timestamp": timezone.now().timestamp(),
                "location": {
                    "site": "Site-A",
                    "batiment": "Batiment-1",
                    "salle": "Salle-Serveur",
                    "machine": "Machine-Rack3"
                },
                "data_type": "smoke",
                "value": "WARNING"
            }
        )
        self.stdout.write(f"  - Cree : {event_alert}")

        # 3. Événement Acquittement d'opérateur
        event_ack = RawEvent.objects.create(
            topic="topic-acknowledgement",
            payload={
                "id": 45,
                "dev_eui": "70b3d57ed005e1a2",
                "alert_type": "fire",
                "location": {
                    "site": "Site-A",
                    "batiment": "Batiment-1",
                    "salle": "Salle-Serveur",
                    "machine": "Machine-Rack3"
                },
                "motifs": ["Fumee de poussiere lors de maintenance"],
                "actions": ["Nettoyage du capteur", "Ventilation forcee de la piece"],
                "impact": "Aucun",
                "comment": "L'alerte a ete identifiee comme fausse suite a des travaux de maintenance.",
                "duration": 180,
                "created_at": timezone.now().isoformat()
            }
        )
        self.stdout.write(f"  - Cree : {event_ack}")

        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Etape 1 : Generation du resume periodique (10-15 minutes)..."))
        self.stdout.write("="*50)
        
        summary = generate_periodic_summary()
        if summary:
            self.stdout.write(self.style.SUCCESS(f"\n[OK] Resume periodique #{summary.id} genere !"))
            self.stdout.write(f"Evenements resumes : {summary.events_count}")
            self.stdout.write("-" * 30)
            self.write_safe(summary.summary_text)
            self.stdout.write("-" * 30)
        else:
            self.stdout.write(self.style.ERROR("[-] Echec de la generation du resume periodique."))
            return

        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Etape 2 : Generation du briefing hebdomadaire..."))
        self.stdout.write("="*50)
        
        briefing = generate_weekly_briefing()
        if briefing:
            self.stdout.write(self.style.SUCCESS(f"\n[OK] Briefing hebdomadaire #{briefing.id} genere !"))
            self.stdout.write(f"Periode : Du {briefing.start_date} au {briefing.end_date}")
            self.stdout.write("-" * 30)
            self.write_safe(briefing.briefing_text)
            self.stdout.write("-" * 30)
        else:
            self.stdout.write(self.style.ERROR("[-] Echec de la generation du briefing hebdomadaire."))
            return

        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Etape 3 : Generation du bilan mensuel..."))
        self.stdout.write("="*50)
        
        report = generate_monthly_report(timezone.now().year, timezone.now().month)
        if report:
            self.stdout.write(self.style.SUCCESS(f"\n[OK] Bilan mensuel #{report.id} genere pour {report.month}/{report.year} !"))
            self.stdout.write("-" * 30)
            self.write_safe(report.report_text)
            self.stdout.write("-" * 30)
        else:
            self.stdout.write(self.style.ERROR("[-] Echec de la generation du bilan mensuel."))
            return
        
        self.stdout.write("\n" + self.style.SUCCESS("Test de generation termine avec succes !"))


