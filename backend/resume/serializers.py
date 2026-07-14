from rest_framework import serializers
from .models import RawEvent, PeriodicSummary, WeeklyBriefing, MonthlyReport

class MonthlyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyReport
        fields = ['id', 'report_text', 'year', 'month', 'created_at']


class WeeklyBriefingSerializer(serializers.ModelSerializer):
    monthly_report_detail = MonthlyReportSerializer(source='monthly_report', read_only=True)
    
    class Meta:
        model = WeeklyBriefing
        fields = ['id', 'briefing_text', 'start_date', 'end_date', 'monthly_report', 'monthly_report_detail', 'created_at']


class PeriodicSummarySerializer(serializers.ModelSerializer):
    weekly_briefing_detail = WeeklyBriefingSerializer(source='weekly_briefing', read_only=True)

    class Meta:
        model = PeriodicSummary
        fields = ['id', 'summary_text', 'events_count', 'start_time', 'end_time', 'weekly_briefing', 'weekly_briefing_detail', 'created_at']


class RawEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawEvent
        fields = ['id', 'topic', 'payload', 'processed', 'created_at']
