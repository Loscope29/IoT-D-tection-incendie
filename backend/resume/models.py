from django.db import models

class MonthlyReport(models.Model):
    report_text = models.TextField(verbose_name="Contenu du bilan mensuel (Markdown)")
    year = models.IntegerField(verbose_name="Année")
    month = models.IntegerField(verbose_name="Mois (1-12)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Généré le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Bilan Mensuel - {self.year}/{self.month:02d} (Généré le {self.created_at.strftime('%Y-%m-%d')})"


class WeeklyBriefing(models.Model):
    briefing_text = models.TextField(verbose_name="Contenu du briefing hebdomadaire (Markdown)")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    monthly_report = models.ForeignKey(
        MonthlyReport,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='weekly_briefings',
        verbose_name="Bilan mensuel associé"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Généré le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Briefing Hebdomadaire - Du {self.start_date} au {self.end_date}"


class PeriodicSummary(models.Model):
    summary_text = models.TextField(verbose_name="Contenu du résumé (Markdown)")
    events_count = models.IntegerField(verbose_name="Nombre d'événements inclus")
    start_time = models.DateTimeField(verbose_name="Début de la période")
    end_time = models.DateTimeField(verbose_name="Fin de la période")
    weekly_briefing = models.ForeignKey(
        WeeklyBriefing,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='periodic_summaries',
        verbose_name="Briefing hebdomadaire associé"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Généré le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Résumé Périodique #{self.id} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class RawEvent(models.Model):
    topic = models.CharField(max_length=255, verbose_name="Topic Kafka")
    payload = models.JSONField(verbose_name="Payload JSON brut")
    processed = models.BooleanField(default=False, db_index=True, verbose_name="Traité pour résumé")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"RawEvent {self.topic} - Reçu le {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

