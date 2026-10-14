import calendar  # Ajouter des mois calendaires plutôt qu'un nombre arbitraire de jours.
import math  # Calculer une distance sphérique pour le mode SQLite.
import uuid  # Créer des noms de médias imprévisibles.
from datetime import timedelta  # Définir les échéances relatives.
from decimal import Decimal, ROUND_HALF_UP  # Arrondir les crédits monétaires sans erreur flottante.
from io import BytesIO  # Réencoder les images en mémoire.
from zoneinfo import ZoneInfo  # Interpréter les horaires dans le fuseau du commerce.
from PIL import Image, ImageOps  # Vérifier les images et supprimer les métadonnées EXIF.
from django.core.files.base import ContentFile  # Fournir un fichier sûr au stockage Django.
from django.db import transaction  # Rendre l'activation et les mises à jour atomiques.
from django.db.models import Avg  # Agréger les notes visibles.
from django.utils import timezone  # Utiliser des instants UTC cohérents.
from rest_framework.exceptions import ValidationError  # Produire des erreurs métier lisibles par le client.
from .models import Subscription, Notification, Audit, Payment  # Accéder aux entités du cycle d'abonnement.
PLANS = {'discovery': {'name': 'Découverte', 'months': 1, 'price': 0, 'limit': 10, 'priority': 0}, 'essential': {'name': 'Essentiel', 'months': 3, 'price': 1500, 'limit': 30, 'priority': 0}, 'growth': {'name': 'Croissance', 'months': 6, 'price': 3000, 'limit': None, 'priority': 1}, 'performance': {'name': 'Performance', 'months': 12, 'price': 5000, 'limit': None, 'priority': 2}}  # Centraliser les quatre tarifs exacts du cahier des charges.
def add_months(value, count):  # Respecter la durée contractuelle même en février.
    month = value.month - 1 + count  # Transformer le mois en index cumulatif.
    year = value.year + month // 12  # Reporter le dépassement dans l'année.
    month = month % 12 + 1  # Revenir aux mois de 1 à 12.
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))  # Écrêter les fins de mois inexistantes.
def active_subscription(vendor):  # Consulter les droits valides à l'instant présent.
    now = timezone.now()  # Figer l'instant des droits pour cette évaluation.
    rows = [sub for sub in vendor.subscriptions.all() if sub.start <= now < sub.end]  # Exploiter le préchargement pour éviter une requête par commerce.
    return max(rows, key=lambda sub: (sub.start, sub.pk)) if rows else None  # Ne jamais dépendre de l'exécution du cron pour expirer des droits.
def plan_key(vendor):  # Appliquer le repli fonctionnel sans supprimer les données.
    current = active_subscription(vendor)  # Lire l'abonnement effectif.
    return current.plan if current else 'discovery'  # Conserver dix produits après expiration.
def product_limit(vendor):  # Calculer la taille autorisée du catalogue.
    return PLANS[plan_key(vendor)]['limit']  # Retourner None pour un catalogue illimité.
def visible_products(vendor):  # Préserver les produits excédentaires tout en limitant leur publication.
    rows = sorted([product for product in vendor.products.all() if product.available], key=lambda product: product.pk)  # Favoriser un sous-ensemble stable après rétrogradation.
    limit = product_limit(vendor)  # Charger les droits actuels.
    return rows[:limit] if limit is not None else rows  # Masquer seulement les produits au-delà du quota.
def is_open(vendor, now=None):  # Calculer ouverture manuelle, exceptions et plages nocturnes.
    now = now or timezone.now()  # Permettre des tests déterministes.
    if vendor.status_override != 'auto' and vendor.override_until and vendor.override_until > now:  # Respecter une dérogation encore valide.
        return vendor.status_override == 'open'  # Traduire le statut manuel.
    local = now.astimezone(ZoneInfo(vendor.timezone))  # Convertir l'instant dans le fuseau local.
    today = local.date()  # Identifier le jour local.
    current = local.time().replace(tzinfo=None)  # Comparer des heures civiles.
    exceptions = {item.date: item for item in vendor.exceptions.all()}  # Exploiter le calendrier préchargé sans requêtes répétées.
    hours = list(vendor.hours.all())  # Charger les plages une fois pour le calcul du jour et de la veille.
    exception = exceptions.get(today)  # Chercher une décision exceptionnelle pour aujourd'hui.
    if exception:  # Donner priorité à une exception sur les horaires récurrents.
        return not exception.closed and exception.start <= current < exception.end  # Le MVP exige des exceptions dans une seule journée.
    for hour in hours:  # Examiner les plages récurrentes déjà chargées.
        if hour.weekday != today.weekday():  # Restreindre l'ouverture actuelle au jour local.
            continue  # Ignorer une plage d'un autre jour.
        if hour.start < hour.end and hour.start <= current < hour.end:  # Gérer une plage normale.
            return True  # Signaler un commerce ouvert.
        if hour.start > hour.end and current >= hour.start:  # Gérer le début d'une plage traversant minuit.
            return True  # Signaler une ouverture nocturne.
    yesterday = today - timedelta(days=1)  # Identifier l'origine possible d'une plage nocturne.
    if yesterday not in exceptions:  # Empêcher une plage normale de dépasser une exception passée.
        for hour in hours:  # Examiner la suite des plages nocturnes.
            if hour.weekday == yesterday.weekday() and hour.start > hour.end and current < hour.end:  # Vérifier la partie située après minuit.
                return True  # Maintenir le commerce ouvert.
    return False  # Fermer lorsque aucune plage n'est active.
def distance_m(lat1, lon1, lat2, lon2):  # Mesurer la distance à vol d'oiseau sur une sphère terrestre.
    values = [math.radians(v) for v in [lat1, lon1, lat2, lon2]]  # Convertir les degrés en radians.
    a = math.sin((values[2] - values[0]) / 2) ** 2 + math.cos(values[0]) * math.cos(values[2]) * math.sin((values[3] - values[1]) / 2) ** 2  # Appliquer la formule de Haversine.
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, a)))  # Borner l'arrondi et retourner des mètres.
def rating(vendor):  # Exclure les avis masqués des statistiques publiques.
    notes = [review.rating for review in vendor.reviews.all() if review.visible]  # Exploiter les avis préchargés et ignorer la modération.
    return round(sum(notes) / len(notes), 1) if notes else 0  # Produire une moyenne stable sans requête supplémentaire.
def safe_image(upload):  # Accepter uniquement une image raster sûre et limitée.
    if upload.size > 5 * 1024 * 1024:  # Refuser les fichiers dépassant cinq mégaoctets.
        raise ValidationError('Photo limitée à 5 Mo.')  # Expliquer la limite au vendeur.
    try:  # Traiter aussi les formats corrompus ou trompeurs.
        picture = Image.open(upload)  # Décoder le fichier plutôt que faire confiance à son extension.
        if picture.format not in ['JPEG', 'PNG', 'WEBP'] or picture.width * picture.height > 20000000:  # Refuser les formats actifs et dimensions excessives.
            raise ValueError('Format ou dimensions interdits')  # Utiliser une erreur commune.
        picture = ImageOps.exif_transpose(picture).convert('RGB')  # Orienter puis supprimer les métadonnées GPS.
        picture.thumbnail((1400, 1400))  # Réduire la bande passante mobile.
        output = BytesIO()  # Créer une destination en mémoire.
        picture.save(output, 'JPEG', quality=85)  # Réencoder pour éliminer tout contenu annexe.
        return ContentFile(output.getvalue(), name=f'{uuid.uuid4().hex}.jpg')  # Retourner un nom indépendant du fichier utilisateur.
    except Exception:  # Convertir les erreurs Pillow en réponse métier.
        raise ValidationError('Image invalide : utilisez JPEG, PNG ou WebP, au plus 20 mégapixels.')  # Ne jamais exposer un détail interne.
def audit(actor, action, target, **detail):  # Tracer les opérations sensibles sans contenu secret.
    Audit.objects.create(actor=actor if actor and actor.is_authenticated else None, action=action, target=str(target), detail=detail)  # Enregistrer l'identité et les métadonnées autorisées.
def quote(vendor, target):  # Calculer le montant d'une souscription ou d'un upgrade.
    if target not in PLANS or target == 'discovery':  # Réserver le trial initial aux nouveaux vendeurs.
        raise ValidationError('Choisissez une formule payante valide.')  # Refuser les clés inconnues.
    current = active_subscription(vendor)  # Examiner les droits actuels.
    credit = 0  # Partir sans crédit.
    if current and current.plan != 'discovery':  # Calculer le prorata d'un abonnement encore actif.
        if list(PLANS).index(target) <= list(PLANS).index(current.plan):  # Réserver les changements immédiats aux upgrades.
            raise ValidationError('Un renouvellement ou changement vers une formule inférieure est possible après expiration.')  # Éviter une perte de droits silencieuse.
        total = Decimal(str((current.end - current.start).total_seconds()))  # Représenter la durée de référence sans flottant monétaire.
        remaining = Decimal(str(max(0, (current.end - timezone.now()).total_seconds())))  # Calculer la durée non consommée.
        credit = int((Decimal(current.amount) * remaining / total).quantize(Decimal('1'), rounding=ROUND_HALF_UP))  # Arrondir le solde au FCFA.
    return {'amount': max(0, PLANS[target]['price'] - credit), 'credit': credit, 'plan': target, 'currency': 'XOF'}  # Présenter un devis déterminé par le serveur.
@transaction.atomic  # Garantir une seule activation malgré des webhooks concurrents.
def confirm_payment(payment_id, actor=None, external_reference=''):  # Activer uniquement un règlement vérifié par un opérateur ou un adaptateur.
    payment = Payment.objects.select_for_update().get(pk=payment_id)  # Verrouiller la transaction financière.
    vendor = type(payment.vendor).objects.select_for_update().get(pk=payment.vendor_id)  # Sérialiser les souscriptions d'un même commerce.
    if payment.status == 'paid':  # Rendre les répétitions de webhook idempotentes.
        return payment.subscription  # Réutiliser l'activation existante.
    if payment.status != 'pending' or not external_reference.strip():  # Exiger un reçu et un état compatible.
        raise ValidationError('Paiement non confirmable ou référence externe manquante.')  # Empêcher une activation sans justification.
    if timezone.now() - payment.created_at > timedelta(hours=24):  # Limiter la validité du devis et de son crédit.
        raise ValidationError('Devis expiré ; créez une nouvelle demande.')  # Éviter une souscription à un prix périmé.
    expected = quote(vendor, payment.plan)  # Revérifier les droits pour éviter deux upgrades concurrents.
    if active_subscription(vendor) and active_subscription(vendor).pk != payment.base_subscription_id:  # Refuser une demande fondée sur des droits remplacés.
        raise ValidationError('Les droits ont changé ; créez une nouvelle demande.')  # Conserver le devis original pendant vingt-quatre heures.
    now = timezone.now()  # Figer l'instant d'activation.
    vendor.subscriptions.filter(end__gt=now).update(end=now)  # Terminer les droits précédents.
    sub = Subscription.objects.create(vendor=vendor, plan=payment.plan, start=now, end=add_months(now, PLANS[payment.plan]['months']), amount=payment.amount)  # Créer les nouveaux droits calendaires.
    payment.status, payment.subscription, payment.external_reference = 'paid', sub, external_reference  # Associer paiement, reçu et abonnement.
    payment.save()  # Persister l'état financier atomiquement.
    Notification.objects.create(user=vendor.owner, title='Abonnement activé', message=f"Votre formule {PLANS[payment.plan]['name']} est active jusqu'au {sub.end:%d/%m/%Y}.")  # Informer le commerçant.
    audit(actor, 'payment.confirm', payment.id, amount=payment.amount, reference=external_reference)  # Journaliser la décision vérifiée.
    return sub  # Retourner les droits activés.
