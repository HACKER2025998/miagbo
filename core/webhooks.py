import hashlib  # Calculer l'empreinte du message fournisseur.
import hmac  # Vérifier la signature sans comparaison temporelle vulnérable.
import json  # Décoder seulement un corps signé.
import time  # Limiter la fenêtre de rejeu réseau.
from django.db import IntegrityError  # Refuser proprement un reçu déjà consommé par une autre transaction.
from django.conf import settings  # Charger le secret de l'adaptateur.
from django.http import JsonResponse  # Retourner un accusé de réception minimal.
from django.views.decorators.csrf import csrf_exempt  # Remplacer CSRF par la signature pour ce serveur externe uniquement.
from django.views.decorators.http import require_POST  # Refuser tout accès autre qu'une notification POST.
from rest_framework.exceptions import ValidationError  # Gérer les conflits de règles financières.
from .models import Payment  # Résoudre la transaction locale.
from .services import confirm_payment  # Réutiliser l'activation idempotente.
@csrf_exempt  # Autoriser un serveur fournisseur qui ne possède pas de cookie navigateur.
@require_POST  # Exiger une notification explicite.
def payment_webhook(request):  # Contrat interne d'adaptateur, à raccorder au fournisseur retenu.
    if not settings.PAYMENT_WEBHOOK_SECRET:  # Refuser tout événement avant configuration du secret.
        return JsonResponse({'detail': 'Adaptateur de paiement non configuré.'}, status=503)  # Éviter un faux succès.
    if len(request.body) > 10000:  # Limiter la charge à un événement financier simple.
        return JsonResponse({'detail': 'Événement trop volumineux.'}, status=413)  # Refuser un corps abusif.
    timestamp = request.headers.get('X-Miagbo-Timestamp', '')  # Lire l'instant signé par l'adaptateur.
    try:  # Traiter un en-tête mal formé.
        valid_time = abs(time.time() - int(timestamp)) <= 300  # Accepter une dérive de cinq minutes maximum.
    except ValueError:  # Refuser les dates non numériques.
        valid_time = False  # Marquer l'événement comme invalide.
    expected = hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), timestamp.encode() + b'.' + request.body, hashlib.sha256).hexdigest()  # Signer les octets exacts et leur date.
    if not valid_time or not hmac.compare_digest(expected, request.headers.get('X-Miagbo-Signature', '')):  # Vérifier expiration et authenticité.
        return JsonResponse({'detail': 'Signature invalide ou événement expiré.'}, status=401)  # Ne modifier aucune donnée.
    try:  # Valider aussi le contenu d'un événement signé.
        payload = json.loads(request.body)  # Décoder le JSON après validation cryptographique.
        if not isinstance(payload, dict):  # Exiger un objet événement.
            raise ValueError()  # Rejeter les tableaux arbitraires.
        payment = Payment.objects.get(reference=payload['reference'])  # Résoudre la référence générée par notre serveur.
        if payload.get('status') != 'paid' or type(payload.get('amount')) is not int or payload['amount'] != payment.amount or payload.get('currency') != 'XOF' or not isinstance(payload.get('external_reference'), str) or len(payload['external_reference']) > 120:  # Valider statut, montant exact, devise et reçu.
            raise ValueError()  # Refuser toute divergence.
        confirm_payment(payment.pk, external_reference=payload['external_reference'])  # Activer une seule fois les droits.
    except (ValueError, KeyError, TypeError, Payment.DoesNotExist, ValidationError, IntegrityError):  # Adapter erreurs de données et conflits métier.
        return JsonResponse({'detail': 'Événement invalide ou paiement non confirmable.'}, status=400)  # Ne divulguer aucun état financier détaillé.
    return JsonResponse({'accepted': True})  # Accuser réception après transaction réussie.
