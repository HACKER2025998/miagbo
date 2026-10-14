from datetime import timedelta  # Restreindre la découverte aux nouveaux commerces récents.
from django.core.management.base import BaseCommand  # Exposer le calcul des alertes au worker.
from django.utils import timezone  # Dater la fenêtre de découverte.
from core.models import AlertZone, Vendor, Notification  # Utiliser seulement des zones clientes explicitement consenties.
from core.services import distance_m  # Appliquer le même calcul géographique que la recherche.
class Command(BaseCommand):  # Déclarer nearby_alerts.
    help = 'Signale les commerces créés dans les sept derniers jours aux zones d’alerte consenties.'  # Définir exactement le comportement observable.
    def handle(self,*args,**options):  # Générer des notifications personnelles sans suivi GPS permanent.
        vendors = list(Vendor.objects.filter(moderation='approved',owner__is_active=True,created_at__gte=timezone.now()-timedelta(days=7)))  # Exclure anciens commerces, dossiers en attente et comptes suspendus.
        count = 0  # Compter les nouveaux messages du passage.
        for zone in AlertZone.objects.filter(user__is_active=True).select_related('user'):  # Respecter le consentement et la suspension du destinataire.
            emitted = 0  # Borner la découverte à trois nouveautés par passage et destinataire.
            for vendor in vendors:  # Examiner les nouveaux commerces publiés.
                if distance_m(zone.latitude,zone.longitude,vendor.latitude,vendor.longitude) > zone.radius:  # Comparer au rayon choisi, jamais à la dernière position de recherche.
                    continue  # Ignorer un commerce hors zone.
                _, created = Notification.objects.get_or_create(dedupe_key=f'nearby:{zone.user_id}:{vendor.pk}',defaults={'user':zone.user,'title':'Une nouvelle adresse près de votre zone','message':f'Découvrez {vendor.name}, un commerce récemment inscrit sur MIAGBO.'})  # Notifier un commerce au plus une fois par compte.
                emitted += int(created); count += int(created)  # Compter seulement les créations et éviter les doublons de cron.
                if emitted >= 3:  # Limiter la charge d'un passage de worker.
                    break  # Laisser les autres nouveautés au passage suivant.
        self.stdout.write(f'{count} nouvelles alertes créées.')  # Ne pas écrire les coordonnées clientes dans les logs.
