import json  # Encoder le contrat de notification Expo.
import urllib.request  # Envoyer des appels HTTPS au service push officiel.
from datetime import timedelta  # Définir les reprises et la fenêtre de diffusion.
from django.conf import settings  # Lire l'activation du transport et son secret.
from django.core.management.base import BaseCommand, CommandError  # Exposer un worker planifiable.
from django.db import transaction  # Sérialiser les tentatives concurrentes.
from django.utils import timezone  # Planifier des reprises en UTC.
from core.models import Notification, PushDelivery  # Associer message persistant et envoi distant.
def expo_call(endpoint, payload):  # Limiter tous les appels push à un domaine fixe.
    headers = {'Content-Type':'application/json','Accept':'application/json'}  # Utiliser le contrat JSON officiel.
    if settings.EXPO_PUSH_ACCESS_TOKEN:  # Authentifier le projet si Expo exige un jeton d'accès.
        headers['Authorization'] = 'Bearer ' + settings.EXPO_PUSH_ACCESS_TOKEN  # Garder le secret dans l'en-tête serveur.
    request = urllib.request.Request('https://exp.host/--/api/v2/push/' + endpoint,data=json.dumps(payload).encode(),headers=headers)  # Ne pas accepter de destination provenant d'un utilisateur.
    with urllib.request.urlopen(request,timeout=10) as response:  # Borner l'attente du fournisseur.
        return json.load(response)  # Lire tickets ou reçus sans journaliser le contenu personnel.
class Command(BaseCommand):  # Déclarer le worker send_push.
    help = 'Envoie les notifications récentes via Expo/FCM/APNs et vérifie les reçus ; nécessite PUSH_ENABLED=1.'  # Expliquer le transport réel.
    def handle(self, *args, **options):  # Traiter au plus cent envois par exécution pour borner le travail.
        if not settings.PUSH_ENABLED:  # Ne jamais contacter Expo avant configuration volontaire.
            raise CommandError('PUSH_ENABLED=1 et les credentials FCM/APNs du projet Expo sont requis.')  # Indiquer la dépendance externe.
        now = timezone.now()  # Figer l'heure de traitement.
        for note in Notification.objects.filter(created_at__gte=now - timedelta(hours=24),user__is_active=True).select_related('user'):  # Ne pas pousser un ancien historique complet.
            for device in note.user.devices.all():  # Diffuser uniquement vers les terminaux encore associés au destinataire.
                PushDelivery.objects.get_or_create(notification=note,device=device)  # Créer une tâche unique par terminal.
        now = timezone.now()  # Inclure les tâches créées quelques millisecondes après le début du worker.
        identifiers = list(PushDelivery.objects.filter(status__in=['pending','accepted'],next_attempt__lte=now,device__user__is_active=True).values_list('id',flat=True)[:100])  # Borner les reprises et les reçus à vérifier.
        for identifier in identifiers:  # Traiter chaque tâche indépendamment.
            with transaction.atomic():  # Éviter deux workers simultanés sur la même tâche.
                delivery = PushDelivery.objects.select_for_update().select_related('notification','device').get(pk=identifier)  # Verrouiller l'état d'envoi.
                if delivery.status not in ['pending','accepted'] or delivery.next_attempt > now:  # Revérifier après acquisition du verrou.
                    continue  # Ignorer une tâche déjà traitée par un concurrent.
                if delivery.device.user_id != delivery.notification.user_id:  # Protéger un terminal réattribué à un autre utilisateur.
                    delivery.status = 'failed'; delivery.error = 'RecipientChanged'; delivery.save()  # Annuler le message personnel ancien.
                    continue  # Ne pas envoyer à un nouveau propriétaire.
                try:  # Réessayer les erreurs temporaires sans marquer le message comme reçu.
                    delivery.attempts += 1  # Compter chaque échange fournisseur.
                    if delivery.status == 'pending':  # Envoyer un message non encore accepté.
                        payload = {'to':delivery.device.token,'title':delivery.notification.title,'body':delivery.notification.message,'sound':'default','data':{'notification_id':delivery.notification_id}}  # N'envoyer que les données destinées à ce compte.
                        result = expo_call('send',payload)['data']  # Obtenir le ticket de prise en charge.
                        if result.get('status') == 'ok':  # Ne pas confondre acceptation et réception sur l'appareil.
                            delivery.ticket = result['id']; delivery.status = 'accepted'; delivery.attempts = 0  # Attendre le reçu du transport.
                        else:  # Conserver le code d'erreur pour l'exploitation.
                            delivery.error = result.get('details',{}).get('error','ProviderError')[:100]  # Éviter de stocker une réponse sensible complète.
                            delivery.status = 'failed' if delivery.error == 'DeviceNotRegistered' or delivery.attempts >= 5 else 'pending'  # Arrêter les erreurs définitives.
                    else:  # Vérifier l'acheminement au fournisseur FCM/APNs.
                        result = expo_call('getReceipts',{'ids':[delivery.ticket]}).get('data',{}).get(delivery.ticket)  # Rechercher le reçu du ticket.
                        if result and result.get('status') == 'ok':  # Confirmer la réception par le transport distant.
                            delivery.status = 'received'  # Ne pas prétendre que l'utilisateur a lu le message.
                        elif result:  # Traiter les erreurs définitives du reçu.
                            delivery.status = 'failed'; delivery.error = result.get('details',{}).get('error','ReceiptError')[:100]  # Garder une trace sans réenvoyer un ticket accepté.
                        elif delivery.attempts >= 5:  # Borner la surveillance d'un reçu manquant.
                            delivery.status = 'failed'; delivery.error = 'ReceiptTimeout'  # Demander une investigation d'exploitation.
                except Exception:  # Une panne réseau ne doit pas interrompre toute la file.
                    delivery.error = 'TransportError'  # Ne pas journaliser le token ou le contenu de la notification.
                    if delivery.attempts >= 5:  # Arrêter après cinq erreurs du même stade.
                        delivery.status = 'failed'  # Rendre l'échec consultable.
                delivery.next_attempt = now + timedelta(minutes=15 if delivery.status == 'accepted' else min(60,2 ** delivery.attempts))  # Attendre les reçus et espacer les retries.
                delivery.save()  # Persister le résultat de l'échange fournisseur.
        self.stdout.write(self.style.SUCCESS(f'{len(identifiers)} tâches push examinées.'))  # Donner un bilan sans données personnelles.
