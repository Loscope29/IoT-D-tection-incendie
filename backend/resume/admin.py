from django.contrib import admin
from .models import RawEvent, PeriodicSummary, WeeklyBriefing, MonthlyReport

@admin.register(RawEvent)
class RawEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'topic', 'processed', 'created_at')
    list_filter = ('topic', 'processed', 'created_at')
    search_fields = ('topic', 'payload')
    readonly_fields = ('created_at',)


@admin.register(PeriodicSummary)
class PeriodicSummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'events_count', 'start_time', 'end_time', 'weekly_briefing', 'created_at')
    list_filter = ('created_at', 'start_time', 'end_time')
    search_fields = ('summary_text',)
    readonly_fields = ('created_at',)


@admin.register(WeeklyBriefing)
class WeeklyBriefingAdmin(admin.ModelAdmin):
    list_display = ('id', 'start_date', 'end_date', 'monthly_report', 'created_at')
    list_filter = ('created_at', 'start_date', 'end_date')
    search_fields = ('briefing_text',)
    readonly_fields = ('created_at',)


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'year', 'month', 'created_at')
    list_filter = ('created_at', 'year', 'month')
    search_fields = ('report_text',)
    readonly_fields = ('created_at',)

