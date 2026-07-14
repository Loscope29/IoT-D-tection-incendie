from rest_framework import serializers
from .models import Acknowledgement

class LocationSerializer(serializers.Serializer):
    site = serializers.CharField(max_length=100)
    batiment = serializers.CharField(max_length=100)
    salle = serializers.CharField(max_length=100)
    machine = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)

class AcknowledgementBaseSerializer(serializers.ModelSerializer):
    location = LocationSerializer(write_only=True)
    
    # Validation du champ motifs et actions
    motifs = serializers.ListField(
        child=serializers.CharField(max_length=200),
        allow_empty=False,
        error_messages={"not_empty": "Au moins un motif doit être sélectionné."}
    )
    actions = serializers.ListField(
        child=serializers.CharField(max_length=200),
        allow_empty=False,
        error_messages={"not_empty": "Au moins une action doit être menée."}
    )

    class Meta:
        model = Acknowledgement
        fields = [
            'id', 'dev_eui', 'location', 'motifs', 'actions', 
            'impact', 'comment', 'duration', 'timestamp', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_impact(self, value):
        valid_impacts = [choice[0] for choice in Acknowledgement.IMPACT_CHOICES]
        if value not in valid_impacts:
            raise serializers.ValidationError(f"Impact invalide. Choix possibles : {valid_impacts}")
        return value

    def create(self, validated_data):
        # Extraire la localisation pour aplatir le modèle
        location_data = validated_data.pop('location')
        
        # Le type d'alerte sera injecté par le sous-sérialiseur
        alert_type = self.context.get('alert_type')
        
        acknowledgement = Acknowledgement.objects.create(
            alert_type=alert_type,
            site=location_data.get('site'),
            batiment=location_data.get('batiment'),
            salle=location_data.get('salle'),
            machine=location_data.get('machine', ''),
            **validated_data
        )
        return acknowledgement


class FireAcknowledgementSerializer(AcknowledgementBaseSerializer):
    ALLOWED_MOTIFS = [
        "Surchauffe machine / Surcharge",
        "Fausse alerte (poussière/vapeur)",
        "Exercice de sécurité / Test",
        "Court-circuit / Problème électrique",
        "Dysfonctionnement capteur",
        "Porte ou enceinte mal isolée"
    ]
    
    ALLOWED_ACTIONS = [
        "Appel des secours (18/112)",
        "Ventilation forcée de la salle",
        "Évacuation de la zone concernée",
        "Coupure d'urgence de l'alimentation",
        "Aucune anomalie constatée",
        "Intervention équipe technique"
    ]

    def validate_motifs(self, value):
        for motif in value:
            if motif not in self.ALLOWED_MOTIFS:
                raise serializers.ValidationError(
                    f"Le motif '{motif}' n'est pas autorisé pour une alerte incendie. Choix autorisés : {self.ALLOWED_MOTIFS}"
                )
        return value

    def validate_actions(self, value):
        for action in value:
            if action not in self.ALLOWED_ACTIONS:
                raise serializers.ValidationError(
                    f"L'action '{action}' n'est pas autorisée pour une alerte incendie. Choix autorisés : {self.ALLOWED_ACTIONS}"
                )
        return value


class TechnicalAcknowledgementSerializer(AcknowledgementBaseSerializer):
    ALLOWED_MOTIFS = [
        "Usure normale de la batterie",
        "Déconnexion radio LoRaWAN",
        "Capteur arraché / Vandalisé",
        "Changement d'emplacement de la pièce",
        "Incident matériel / Panne capteur",
        "Interférences radio / Obstacle"
    ]
    
    ALLOWED_ACTIONS = [
        "Remplacement de la pile / batterie",
        "Redémarrage du boîtier",
        "Repositionnement physique du capteur",
        "Remplacement complet de l'équipement",
        "Appel au support technique / Constructeur",
        "Enquête sur site pour perte de liaison"
    ]

    def validate_motifs(self, value):
        for motif in value:
            if motif not in self.ALLOWED_MOTIFS:
                raise serializers.ValidationError(
                    f"Le motif '{motif}' n'est pas autorisé pour une alerte technique. Choix autorisés : {self.ALLOWED_MOTIFS}"
                )
        return value

    def validate_actions(self, value):
        for action in value:
            if action not in self.ALLOWED_ACTIONS:
                raise serializers.ValidationError(
                    f"L'action '{action}' n'est pas autorisée pour une alerte technique. Choix autorisés : {self.ALLOWED_ACTIONS}"
                )
        return value
