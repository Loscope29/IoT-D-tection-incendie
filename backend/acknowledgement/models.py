from django.db import models

class Acknowledgement(models.Model):
    ALERT_TYPES = [
        ('fire', 'Incendie'),
        ('technical', 'Technique'),
    ]
    
    IMPACT_CHOICES = [
        ('Aucun', 'Aucun'),
        ('Mineur', 'Mineur'),
        ('Majeur', 'Majeur'),
    ]

    dev_eui = models.CharField(max_length=50, verbose_name="Identifiant unique du capteur")
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, verbose_name="Type d'alerte")
    site = models.CharField(max_length=100)
    batiment = models.CharField(max_length=100)
    salle = models.CharField(max_length=100)
    machine = models.CharField(max_length=100, blank=True, null=True)
    
    # Stockage sous forme de listes (JSON)
    motifs = models.JSONField(default=list, verbose_name="Motifs de l'alerte")
    actions = models.JSONField(default=list, verbose_name="Actions menées")
    
    impact = models.CharField(max_length=20, choices=IMPACT_CHOICES, default='Aucun')
    comment = models.TextField(blank=True, null=True, verbose_name="Précisions / Commentaires")
    duration = models.IntegerField(default=0, verbose_name="Durée de l'alerte (secondes)")
    
    # Horodatage
    timestamp = models.CharField(max_length=50, blank=True, null=True, verbose_name="Heure signalée par le dashboard")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'enregistrement backend")

    def __str__(self):
        return f"Acquittement {self.get_alert_type_display()} - {self.site}/{self.batiment}/{self.salle} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
