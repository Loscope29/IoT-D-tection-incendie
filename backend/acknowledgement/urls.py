from django.urls import path
from .views import FireAcknowledgementView, TechnicalAcknowledgementView

urlpatterns = [
    path('acquittement/incendie/', FireAcknowledgementView.as_view(), name='acquittement-incendie'),
    path('acquittement/technique/', TechnicalAcknowledgementView.as_view(), name='acquittement-technique'),
]
