from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
from .models import RawEvent, PeriodicSummary, WeeklyBriefing, MonthlyReport
from .services import (
    generate_periodic_summary,
    generate_weekly_briefing,
    generate_monthly_report
)

class AssistantModelsTestCase(TestCase):
    """
    Tests pour vérifier le fonctionnement et l'intégrité des modèles de données.
    """
    def test_model_creation(self):
        # 1. Test RawEvent
        event = RawEvent.objects.create(
            topic="fire-alerts",
            payload={"location": {"site": "SiteA"}, "value": 45.5}
        )
        self.assertEqual(event.topic, "fire-alerts")
        self.assertFalse(event.processed)
        self.assertIn("RawEvent", str(event))

        # 2. Test MonthlyReport
        report = MonthlyReport.objects.create(
            report_text="Bilan Mensuel de Test",
            year=2026,
            month=7
        )
        self.assertEqual(report.year, 2026)
        self.assertIn("Bilan Mensuel", str(report))

        # 3. Test WeeklyBriefing
        briefing = WeeklyBriefing.objects.create(
            briefing_text="Briefing Hebdo de Test",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            monthly_report=report
        )
        self.assertEqual(briefing.monthly_report, report)
        self.assertIn("Briefing Hebdomadaire", str(briefing))

        # 4. Test PeriodicSummary
        summary = PeriodicSummary.objects.create(
            summary_text="Résumé Périodique de Test",
            events_count=1,
            start_time=timezone.now(),
            end_time=timezone.now(),
            weekly_briefing=briefing
        )
        self.assertEqual(summary.weekly_briefing, briefing)
        self.assertIn("Résumé Périodique", str(summary))


class AssistantServicesTestCase(TestCase):
    """
    Tests pour vérifier les services de compilation (génération de résumés/briefings).
    """
    def setUp(self):
        # Mocker l'appel LLM
        self.llm_patcher = patch('resume.services.generate_llm_content', return_value="Mocked LLM Response")
        self.mock_llm = self.llm_patcher.start()

        # Créer des événements bruts de test
        RawEvent.objects.create(
            topic="fire-telemetry",
            payload={"location": {"site": "SiteA", "batiment": "Bat1", "salle": "S1", "machine": "M1"}, "data_type": "temperature", "value": 22.4}
        )
        RawEvent.objects.create(
            topic="fire-alerts",
            payload={"location": {"site": "SiteA", "batiment": "Bat1", "salle": "S1", "machine": "M1"}, "data_type": "smoke", "value": "HIGH"}
        )

    def tearDown(self):
        self.llm_patcher.stop()

    def test_periodic_summary_generation(self):
        self.assertEqual(RawEvent.objects.filter(processed=False).count(), 2)
        
        # Lancer le service (qui utilisera le mock LLM)
        summary = generate_periodic_summary()
        
        self.assertIsNotNone(summary)
        self.assertEqual(summary.events_count, 2)
        self.assertEqual(summary.summary_text, "Mocked LLM Response")
        # Vérifier que les événements ont été marqués comme traités
        self.assertEqual(RawEvent.objects.filter(processed=False).count(), 0)

    def test_weekly_briefing_generation(self):
        # D'abord générer un résumé périodique
        summary = generate_periodic_summary()
        self.assertIsNotNone(summary)
        self.assertIsNone(summary.weekly_briefing)
        
        # Lancer le briefing hebdomadaire
        briefing = generate_weekly_briefing()
        
        self.assertIsNotNone(briefing)
        self.assertEqual(briefing.briefing_text, "Mocked LLM Response")
        # Vérifier que le résumé périodique est maintenant associé
        summary.refresh_from_db()
        self.assertEqual(summary.weekly_briefing, briefing)

    def test_monthly_report_generation(self):
        # Générer un résumé périodique et un briefing hebdo
        summary = generate_periodic_summary()
        briefing = generate_weekly_briefing()
        self.assertIsNotNone(briefing)
        self.assertIsNone(briefing.monthly_report)
        
        # Lancer le rapport mensuel
        report = generate_monthly_report(2026, 7)
        
        self.assertIsNotNone(report)
        self.assertEqual(report.report_text, "Mocked LLM Response")
        briefing.refresh_from_db()
        self.assertEqual(briefing.monthly_report, report)


class AssistantAPIsTestCase(APITestCase):
    """
    Tests pour valider les endpoints DRF.
    """
    def setUp(self):
        # Mocker l'appel LLM
        self.llm_patcher = patch('resume.services.generate_llm_content', return_value="Mocked LLM Response")
        self.mock_llm = self.llm_patcher.start()

        # Créer des données initiales
        self.event = RawEvent.objects.create(
            topic="fire-telemetry",
            payload={"location": {"site": "SiteA", "batiment": "Bat1", "salle": "S1", "machine": "M1"}, "data_type": "temperature", "value": 25.0}
        )
        
        # Générer périodique & briefing pour peupler les tables
        self.summary = generate_periodic_summary()
        self.briefing = generate_weekly_briefing()
        self.report = generate_monthly_report(2026, 7)

    def tearDown(self):
        self.llm_patcher.stop()

    def test_get_dashboard(self):
        url = reverse('assistant-dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIsNotNone(data["active_report"])
        self.assertEqual(data["active_report"]["title"], "Résumé Quotidien")
        self.assertIsNotNone(data["latest_periodic"])
        self.assertIsNotNone(data["latest_weekly"])
        self.assertIsNotNone(data["latest_monthly"])
        self.assertEqual(len(data["recent_summaries"]), 1)
        self.assertEqual(data["unprocessed_events_count"], 0)

    def test_manual_trigger(self):
        # Ajouter un nouvel événement brut
        RawEvent.objects.create(
            topic="fire-alerts",
            payload={"location": {"site": "SiteB"}, "value": 90.0}
        )
        
        url = reverse('assistant-trigger')
        # POST sur le trigger manuel
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(data["triggered_jobs_count"], 1)

    def test_list_summaries(self):
        url = reverse('periodic-summary-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_swagger_endpoints(self):
        # Tester le schéma OpenAPI
        schema_url = reverse('schema')
        schema_response = self.client.get(schema_url)
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        
        # Tester l'interface Swagger UI
        swagger_url = reverse('swagger-ui')
        swagger_response = self.client.get(swagger_url)
        self.assertEqual(swagger_response.status_code, status.HTTP_200_OK)


from resume.llm_client import generate_llm_content, TIER_CONFIG
from django.test import override_settings
import json

class LLMClientTestCase(TestCase):
    """
    Tests pour valider le comportement de llm_client.py et la gestion des tiers.
    """
    @patch('urllib.request.urlopen')
    @override_settings(GROQ_API_KEY="test_key_123", GROQ_MODEL="")
    def test_groq_api_call_tiers(self, mock_urlopen):
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Groq Response"}}]
        }).encode('utf-8')

        # 1. Tester le tier light (valeur par défaut)
        res = generate_llm_content("Hello", tier="light")
        self.assertEqual(res, "Groq Response")
        self.assertTrue(mock_urlopen.called)
        
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(req.headers["Authorization"], "Bearer test_key_123")
        
        sent_data = json.loads(req.data.decode('utf-8'))
        self.assertEqual(sent_data["model"], "llama-3.1-8b-instant")
        self.assertEqual(sent_data["max_tokens"], 512)

        mock_urlopen.reset_mock()
        
        # 2. Tester le tier heavy
        res_heavy = generate_llm_content("Hello Heavy", tier="heavy")
        self.assertEqual(res_heavy, "Groq Response")
        
        req_heavy = mock_urlopen.call_args[0][0]
        sent_data_heavy = json.loads(req_heavy.data.decode('utf-8'))
        self.assertEqual(sent_data_heavy["model"], "llama-3.3-70b-versatile")
        self.assertEqual(sent_data_heavy["max_tokens"], 2048)




