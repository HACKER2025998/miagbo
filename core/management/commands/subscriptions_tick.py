from django.core.management.base import BaseCommand  # Exposer une tâche planifiable avec manage.py.
from django.core.mail import send_mail  # Envoyer les rappels contractuels.
from django.conf import settings  # Lire l'expéditeur configuré.
from django.utils import timezone  # Calculer les échéances UTC.
from django.db import transaction  # Éviter des rappels doublés lors d'exécutions concurrentes.
from core.models import Subscription, Notification  # Parcourir l'historique des droits.
from core.services import PLANS  # Utiliser les libellés commerciaux centralisés.
class Command(BaseCommand):  # Déclarer subscriptions_tick.
    help = 'Rappels J-7/J-1 et notification de rétrogradation, sans destruction de catalogue.'  # Expliquer l'effet de la tâche.
    def handle(self, *args, **options):  # Exécuter une vérification complète et idempotente.
        now = timezone.now()  # Figer l'heure de référence.
        for identifier in Subscription.objects.filter(vendor__owner__is_active=True).values_list('id', flat=True):  # Examiner les abonnements de comptes actifs.
            with transaction.atomic():  # Verrouiller chaque abonnement indépendamment.
                sub = Subscription.objects.select_for_update().select_related('vendor__owner').get(pk=identifier)  # Empêcher deux tâches de prendre le même rappel.
                days = (sub.end - now).total_seconds() / 86400  # Calculer le temps restant.
                if sub.vendor.subscriptions.filter(start__gt=sub.start).exists():  # Ignorer les anciennes formules remplacées par un upgrade.
                    continue  # Ne pas annoncer une fausse expiration.
                for threshold, field in [(7, 'reminder7'), (1, 'reminder1'), (0, 'expired_notified')]:  # Définir les trois transitions surveillées.
                    if days > threshold or getattr(sub, field):  # Garder uniquement les événements arrivés à échéance.
                        continue  # Éviter les répétitions.
                    if threshold == 7 and days <= 1:  # Éviter un rappel J-7 en retard le jour précédent l'échéance.
                        continue  # Laisser le rappel J-1 prendre le relais.
                    if threshold == 1 and days <= 0:  # Ne pas annoncer une échéance future déjà passée.
                        continue  # Envoyer seulement la rétrogradation.
                    message = 'Votre abonnement a expiré. Votre catalogue est conservé ; dix produits restent visibles.' if threshold == 0 else f"Votre formule {PLANS[sub.plan]['name']} expire le {sub.end:%d/%m/%Y}. Pensez au renouvellement."  # Produire un message exact.
                    Notification.objects.get_or_create(dedupe_key=f'sub:{sub.pk}:{field}', defaults={'user': sub.vendor.owner, 'title': 'Échéance MIAGBO', 'message': message})  # Garantir l'unicité du message interne.
                    send_mail('Échéance MIAGBO', message, settings.DEFAULT_FROM_EMAIL, [sub.vendor.owner.email])  # Envoyer via SMTP et laisser une erreur remonter pour permettre une reprise.
                    setattr(sub, field, True)  # Marquer le rappel traité.
                    sub.save(update_fields=[field])  # Persister l'avancement.
        self.stdout.write(self.style.SUCCESS('Abonnements vérifiés.'))  # Confirmer la fin de la tâche.
