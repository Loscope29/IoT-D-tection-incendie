from rest_framework import generics, status
from rest_framework.response import Response
from .models import Acknowledgement
from .serializers import FireAcknowledgementSerializer, TechnicalAcknowledgementSerializer
from .kafka_producer import publish_acknowledgement
import logging

logger = logging.getLogger("acknowledgement.views")

class FireAcknowledgementView(generics.CreateAPIView):
    queryset = Acknowledgement.objects.filter(alert_type='fire')
    serializer_class = FireAcknowledgementSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['alert_type'] = 'fire'
        return context

    def perform_create(self, serializer):
        instance = serializer.save()
        
        # Tentative de publication sur Kafka
        kafka_published = publish_acknowledgement(instance)
        
        # Attacher le statut de publication Kafka aux métadonnées de réponse
        self.kafka_published = kafka_published

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        response_data = serializer.data
        response_data["kafka_published"] = getattr(self, "kafka_published", False)
        
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)


class TechnicalAcknowledgementView(generics.CreateAPIView):
    queryset = Acknowledgement.objects.filter(alert_type='technical')
    serializer_class = TechnicalAcknowledgementSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['alert_type'] = 'technical'
        return context

    def perform_create(self, serializer):
        instance = serializer.save()
        
        # Tentative de publication sur Kafka
        kafka_published = publish_acknowledgement(instance)
        
        # Attacher le statut de publication Kafka aux métadonnées de réponse
        self.kafka_published = kafka_published

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        response_data = serializer.data
        response_data["kafka_published"] = getattr(self, "kafka_published", False)
        
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
