from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Acknowledgement

class AcknowledgementAPITests(APITestCase):
    def setUp(self):
        self.fire_url = reverse('acquittement-incendie')
        self.tech_url = reverse('acquittement-technique')
        
        self.valid_fire_payload = {
            "dev_eui": "002590ffff123456",
            "location": {
                "site": "paris",
                "batiment": "batiment_a",
                "salle": "serveurs_1",
                "machine": "rack_3"
            },
            "motifs": ["Surchauffe machine / Surcharge"],
            "actions": ["Ventilation forcée de la salle", "Appel des secours (18/112)"],
            "impact": "Mineur",
            "comment": "Ventilateurs activés, température stabilisée.",
            "duration": 120,
            "timestamp": "18:05:00"
        }

        self.valid_tech_payload = {
            "dev_eui": "002590ffff789012",
            "location": {
                "site": "lyon",
                "batiment": "batiment_b",
                "salle": "stockage",
                "machine": ""
            },
            "motifs": ["Usure normale de la batterie"],
            "actions": ["Remplacement de la pile / batterie"],
            "impact": "Aucun",
            "comment": "Remplacement effectué lors de la ronde.",
            "duration": 0,
            "timestamp": "14:20:00"
        }

    def test_create_valid_fire_acknowledgement(self):
        """Vérifie qu'un acquittement incendie valide est accepté et stocké."""
        response = self.client.post(self.fire_url, self.valid_fire_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Acknowledgement.objects.count(), 1)
        
        ack = Acknowledgement.objects.first()
        self.assertEqual(ack.alert_type, 'fire')
        self.assertEqual(ack.dev_eui, "002590ffff123456")
        self.assertEqual(ack.site, "paris")
        self.assertEqual(ack.motifs, ["Surchauffe machine / Surcharge"])
        self.assertEqual(ack.impact, "Mineur")

    def test_create_invalid_fire_motif(self):
        """Vérifie qu'un motif non autorisé pour un incendie est rejeté."""
        payload = self.valid_fire_payload.copy()
        payload["motifs"] = ["Usure normale de la batterie"]  # Motif technique dans un incendie
        
        response = self.client.post(self.fire_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("motifs", response.data)

    def test_create_empty_motifs_or_actions(self):
        """Vérifie que des motifs ou actions vides sont rejetés."""
        payload = self.valid_fire_payload.copy()
        payload["motifs"] = []
        
        response = self.client.post(self.fire_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_impact(self):
        """Vérifie qu'un impact non répertorié est rejeté."""
        payload = self.valid_fire_payload.copy()
        payload["impact"] = "Catastrophique"  # Hors choix : Aucun, Mineur, Majeur
        
        response = self.client.post(self.fire_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_valid_technical_acknowledgement(self):
        """Vérifie qu'un acquittement technique valide est accepté."""
        response = self.client.post(self.tech_url, self.valid_tech_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Acknowledgement.objects.count(), 1)
        
        ack = Acknowledgement.objects.first()
        self.assertEqual(ack.alert_type, 'technical')
        self.assertEqual(ack.site, "lyon")
        self.assertEqual(ack.actions, ["Remplacement de la pile / batterie"])

    def test_create_invalid_technical_action(self):
        """Vérifie qu'une action non autorisée pour un incident technique est rejetée."""
        payload = self.valid_tech_payload.copy()
        payload["actions"] = ["Appel des secours (18/112)"]  # Action incendie dans un technique
        
        response = self.client.post(self.tech_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("actions", response.data)
