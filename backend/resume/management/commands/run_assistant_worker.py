import json
import logging
import time
import threading
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from kafka import KafkaConsumer
from resume.models import RawEvent, PeriodicSummary, WeeklyBriefing
from resume.services import (
    generate_periodic_summary,
    generate_weekly_briefing,
    generate_monthly_report
)

logger = logging.getLogger("resume.worker")

class Command(BaseCommand):
    help = "Démarre le worker de l'Assistant IA (Consommateur Kafka + Planificateur de résumés)"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(" Démarrage du worker de l'Assistant IA..."))
        
        # 1. Lancement du thread du consommateur Kafka
        kafka_thread = threading.Thread(target=self.run_kafka_consumer, daemon=True)
        kafka_thread.start()
        
        # 2. Lancement du planificateur dans le thread principal
        self.run_scheduler()

    def run_kafka_consumer(self):
        bootstrap_servers = getattr(settings, 'KAFKA_BOOTSTRAP_SERVERS', ['localhost:29092'])
        topics = getattr(settings, 'KAFKA_TOPICS_TO_CONSUME', ['fire-alerts', 'fire-telemetry', 'topic-acknowledgement'])
        
        logger.info(f"Consommateur Kafka initialisé pour écouter les topics: {topics}")
        
        def safe_deserializer(m):
            try:
                return json.loads(m.decode('utf-8'))
            except Exception:
                return {"raw_data": m.decode('utf-8', errors='replace')}

        consumer = None
        while self.running:
            try:
                logger.info(f"Connexion au broker Kafka ({bootstrap_servers})...")
                consumer = KafkaConsumer(
                    *topics,
                    bootstrap_servers=bootstrap_servers,
                    value_deserializer=safe_deserializer,
                    group_id='django-assistant-worker',
                    auto_offset_reset='latest',
                    enable_auto_commit=True
                )
                logger.info(" KafkaConsumer connecté avec succès.")
                break
            except Exception as e:
                logger.warning(f"Impossible de se connecter à Kafka ({e}). Nouvelle tentative dans 5 secondes...")
                time.sleep(5)

        if not consumer:
            logger.error(" Échec critique de connexion à Kafka pour le consommateur.")
            return

        try:
            for msg in consumer:
                if not self.running:
                    break
                
                try:
                    logger.info(f"Message Kafka reçu sur le topic '{msg.topic}'")
                    from django.db import close_old_connections
                    close_old_connections()
                    
                    RawEvent.objects.create(
                        topic=msg.topic,
                        payload=msg.value
                    )
                    close_old_connections()
                    logger.info(" Événement stocké brut en base de données.")
                except Exception as ex:
                    logger.error(f" Erreur lors du stockage de l'événement : {ex}")
        except Exception as e:
            logger.error(f" Erreur critique dans la boucle de consommation Kafka : {e}")
        finally:
            if consumer:
                consumer.close()
            logger.info("Consommateur Kafka arrêté.")

    def run_scheduler(self):
        logger.info(" Planificateur de résumés démarré (Fréquence de vérification : 30 secondes).")
        
        while self.running:
            try:
                self.check_and_run_jobs()
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\nArrêt du worker demandé..."))
                self.running = False
                break
            except Exception as e:
                logger.error(f" Erreur dans la boucle du planificateur : {e}")
                
            time.sleep(30)

    def check_and_run_jobs(self):
        from django.db import close_old_connections
        close_old_connections()
        
        try:
            # 1. Résumé périodique (toutes les 10 minutes)
            unprocessed_exists = RawEvent.objects.filter(processed=False).exists()
            if unprocessed_exists:
                last_summary = PeriodicSummary.objects.order_by('-created_at').first()
                should_run_periodic = False
                
                if not last_summary:
                    should_run_periodic = True
                else:
                    elapsed = (timezone.now() - last_summary.created_at).total_seconds()
                    # 1800 secondes = 30 minutes
                    if elapsed >= 1800:
                        should_run_periodic = True
                        
                if should_run_periodic:
                    logger.info("Planificateur : Lancement du résumé périodique (30 min écoulées ou premier lancement).")
                    generate_periodic_summary()

            # 2. Briefing hebdomadaire (si le plus ancien résumé non compilé a plus de 7 jours)
            unbriefed_exists = PeriodicSummary.objects.filter(weekly_briefing__isnull=True).exists()
            if unbriefed_exists:
                oldest_unbriefed = PeriodicSummary.objects.filter(weekly_briefing__isnull=True).order_by('created_at').first()
                elapsed_days = (timezone.now() - oldest_unbriefed.created_at).days
                if elapsed_days >= 7:
                    logger.info(f"Planificateur : Déclenchement du briefing hebdomadaire ({elapsed_days} jours de données en attente).")
                    generate_weekly_briefing()

            # 3. Bilan mensuel (si le plus ancien briefing non compilé a plus de 30 jours)
            unreported_exists = WeeklyBriefing.objects.filter(monthly_report__isnull=True).exists()
            if unreported_exists:
                oldest_unreported = WeeklyBriefing.objects.filter(monthly_report__isnull=True).order_by('created_at').first()
                elapsed_days = (timezone.now() - oldest_unreported.created_at).days
                if elapsed_days >= 30:
                    logger.info(f"Planificateur : Déclenchement du bilan mensuel ({elapsed_days} jours de briefings en attente).")
                    generate_monthly_report()
                    
        except Exception as ex:
            logger.error(f" Erreur dans check_and_run_jobs : {ex}")
        finally:
            close_old_connections()
