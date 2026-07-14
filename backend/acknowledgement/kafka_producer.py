import json
import logging
from django.conf import settings
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger("acknowledgement.kafka")

class KafkaProducerHelper:
    _instance = None
    _producer = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(KafkaProducerHelper, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def get_producer(self):
        if self._producer is not None:
            return self._producer

        bootstrap_servers = getattr(settings, 'KAFKA_BOOTSTRAP_SERVERS', ['localhost:29092'])
        try:
            logger.info(f"Initialisation du KafkaProducer avec les serveurs: {bootstrap_servers}")
            self._producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',  # Garantir la livraison à tous les réplicas synchronisés
                retries=3,
                request_timeout_ms=5000
            )
            logger.info("✅ KafkaProducer initialisé avec succès.")
            return self._producer
        except KafkaError as e:
            logger.error(f"❌ Impossible de se connecter à Kafka : {e}")
            return None

    def publish(self, topic, key, message):
        producer = self.get_producer()
        if not producer:
            logger.error(f"Impossible de publier le message sur le topic '{topic}' car le producteur n'est pas disponible.")
            return False

        try:
            # Envoi asynchrone avec un rappel de succès/erreur
            key_bytes = key.encode('utf-8') if key else None
            future = producer.send(topic, key=key_bytes, value=message)
            
            # Attendre la confirmation si on veut être sûr (synchrone pour ce cas critique)
            record_metadata = future.get(timeout=5)
            logger.info(f"✅ Message publié avec succès sur {record_metadata.topic} partition [{record_metadata.partition}] offset {record_metadata.offset}")
            return True
        except Exception as e:
            logger.error(f"❌ Échec de la publication sur Kafka : {e}")
            # Si le producteur est défectueux, on le réinitialise pour la prochaine tentative
            self._producer = None
            return False

# Instance globale
kafka_helper = KafkaProducerHelper()

def publish_acknowledgement(ack_instance):
    """
    Publie un acquittement d'alerte sur Kafka.
    """
    topic = getattr(settings, 'KAFKA_TOPIC_ACKNOWLEDGEMENT', 'topic-acknowledgement')
    
    payload = {
        "id": ack_instance.id,
        "dev_eui": ack_instance.dev_eui,
        "alert_type": ack_instance.alert_type,
        "location": {
            "site": ack_instance.site,
            "batiment": ack_instance.batiment,
            "salle": ack_instance.salle,
            "machine": ack_instance.machine
        },
        "motifs": ack_instance.motifs,
        "actions": ack_instance.actions,
        "impact": ack_instance.impact,
        "comment": ack_instance.comment,
        "duration": ack_instance.duration,
        "dashboard_timestamp": ack_instance.timestamp,
        "created_at": ack_instance.created_at.isoformat() if ack_instance.created_at else None
    }
    
    key = ack_instance.dev_eui
    return kafka_helper.publish(topic, key, payload)
