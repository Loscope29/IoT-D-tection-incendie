from django.urls import path
from .views import (
    PeriodicSummaryListAPIView,
    PeriodicSummaryDetailAPIView,
    WeeklyBriefingListAPIView,
    WeeklyBriefingDetailAPIView,
    MonthlyReportListAPIView,
    MonthlyReportDetailAPIView,
    AssistantDashboardAPIView,
    AssistantManualTriggerAPIView
)

urlpatterns = [
    # Dashboard agrégé & Trigger manuel
    path('dashboard/', AssistantDashboardAPIView.as_view(), name='assistant-dashboard'),
    path('trigger/', AssistantManualTriggerAPIView.as_view(), name='assistant-trigger'),
    
    # Résumés périodiques
    path('periodic/', PeriodicSummaryListAPIView.as_view(), name='periodic-summary-list'),
    path('periodic/<int:pk>/', PeriodicSummaryDetailAPIView.as_view(), name='periodic-summary-detail'),
    
    # Briefings hebdomadaires
    path('weekly/', WeeklyBriefingListAPIView.as_view(), name='weekly-briefing-list'),
    path('weekly/<int:pk>/', WeeklyBriefingDetailAPIView.as_view(), name='weekly-briefing-detail'),
    
    # Bilans mensuels
    path('monthly/', MonthlyReportListAPIView.as_view(), name='monthly-report-list'),
    path('monthly/<int:pk>/', MonthlyReportDetailAPIView.as_view(), name='monthly-report-detail'),
]

