from datetime import timedelta  # Définir la durée minimale de conservation des tendances.
from django.core.management.base import BaseCommand  # Fournir une commande d'exploitation.
from django.utils import timezone  # Calculer la date limite UTC.
from core.models import SearchEvent  # Cibler uniquement les recherches anonymes.
class Command(BaseCommand):  # Déclarer la purge des événements de recherche.
    help = 'Supprime les événements de recherche de plus de 90 jours.'  # Expliquer la politique retenue.
    def handle(self, *args, **options):  # Exécuter une suppression bornée par la date.
        count, _ = SearchEvent.objects.filter(created_at__lt=timezone.now() - timedelta(days=90)).delete()  # Réduire les données et la taille des analyses.
        self.stdout.write(f'{count} événements supprimés.')  # Donner un résultat vérifiable.
