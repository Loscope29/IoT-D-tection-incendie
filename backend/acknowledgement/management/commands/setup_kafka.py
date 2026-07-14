from django.core.management.base import BaseCommand
from django.conf import settings
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import logging

logger = logging.getLogger("acknowledgement.kafka_setup")

class Command(BaseCommand):
    help = "S'assure que le topic Kafka requis pour les acquittements existe"

    def handle(self, *args, **options):
        bootstrap_servers = getattr(settings, 'KAFKA_BOOTSTRAP_SERVERS', ['localhost:29092'])
        topic_name = getattr(settings, 'KAFKA_TOPIC_ACKNOWLEDGEMENT', 'topic-acknowledgement')

        self.stdout.write(f"Connexion à Kafka pour vérifier/créer le topic '{topic_name}'...")
        
        try:
            admin_client = KafkaAdminClient(
                bootstrap_servers=bootstrap_servers,
                client_id='acknowledgement-setup-admin'
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Échec de la connexion à Kafka : {e}"))
            return

        try:
            existing_topics = admin_client.list_topics()
            if topic_name in existing_topics:
                self.stdout.write(self.style.SUCCESS(f"✅ Le topic '{topic_name}' existe déjà."))
                return

            self.stdout.write(f"Le topic '{topic_name}' n'existe pas. Création en cours...")
            
            topic = NewTopic(
                name=topic_name,
                num_partitions=1,
                replication_factor=1
            )
            
            admin_client.create_topics(new_topics=[topic], validate_only=False)
            self.stdout.write(self.style.SUCCESS(f"🚀 Le topic '{topic_name}' a été créé avec succès !"))
            
        except TopicAlreadyExistsError:
            self.stdout.write(self.style.SUCCESS(f"✅ Le topic '{topic_name}' existe déjà (concurrence)."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Une erreur s'est produite : {e}"))
        finally:
            admin_client.close()
