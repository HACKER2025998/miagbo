import csv  # Exporter des données interopérables pour l'administration.
import hashlib  # Calculer la signature des événements de paiement.
import hmac  # Comparer les signatures en temps constant.
import json  # Décoder un webhook JSON signé.
import math  # Refuser les coordonnées non finies et borner la recherche locale.
import secrets  # Créer des références financières imprévisibles.
from datetime import timedelta  # Définir l'expiration du statut manuel et la rétention.
from django.core.cache import cache  # Réutiliser un cache spatial éphémère sans enregistrer la position en clair.
from django.conf import settings  # Lire les clés et le domaine de l'application.
from django.contrib.auth import authenticate, login, logout  # Utiliser l'authentification et les sessions standard.
from django.contrib.auth.password_validation import validate_password  # Réutiliser la politique de sécurité.
from django.contrib.auth.tokens import default_token_generator  # Signer les liens de récupération à usage unique.
from django.core.exceptions import ValidationError as DjangoValidationError  # Adapter les erreurs de mot de passe.
from django.core.mail import send_mail  # Envoyer les emails transactionnels.
from django.db import transaction, connection  # Sérialiser les changements et sélectionner PostGIS.
from django.db.models import Q, F, Count, Sum, Prefetch  # Filtrer, compter et incrémenter sans perte concurrente.
from django.db.models.expressions import RawSQL  # Exécuter une requête PostGIS paramétrée.
from django.http import HttpResponse, JsonResponse  # Retourner un export CSV.
from django.shortcuts import render, get_object_or_404  # Servir la page et résoudre les objets autorisés.
from django.utils import timezone  # Manipuler les instants UTC.
from django.utils.encoding import force_bytes, force_str  # Encoder les identifiants des liens de récupération.
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode  # Construire un identifiant compatible URL.
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect  # Protéger aussi la connexion anonyme.
from rest_framework import serializers, status, viewsets  # Déclarer routes et validations REST.
from rest_framework.decorators import api_view, permission_classes, throttle_classes, action  # Exposer des routes métier avec permissions.
from rest_framework.exceptions import PermissionDenied, ValidationError  # Répondre aux refus de droits ou données invalides.
from rest_framework.permissions import AllowAny, IsAuthenticated  # Distinguer découverte publique et actions privées.
from rest_framework.response import Response  # Uniformiser les réponses JSON.
from rest_framework.throttling import AnonRateThrottle  # Limiter les routes sensibles.
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter  # Documenter les routes spécifiques.
from .models import User, Vendor, Product, Category, OpeningHour, OpeningException, Review, Report, Favorite, Notification, Subscription, Payment, Audit, SearchEvent, Configuration, Device  # Charger les entités métier.
from .serializers import UserSerializer, RegisterSerializer, VendorSerializer, VendorDetailSerializer, ProductSerializer, CategorySerializer, HourSerializer, ExceptionSerializer, ReviewSerializer, NotificationSerializer, PaymentSerializer, ReportSerializer, DeviceSerializer  # Contrôler les échanges API.
from .services import PLANS, add_months, plan_key, product_limit, visible_products, is_open, distance_m, rating, quote, confirm_payment, audit, active_subscription  # Réutiliser les règles centralisées.
class AuthThrottle(AnonRateThrottle):  # Freiner la connexion et l'inscription publiques.
    scope = 'auth'  # Utiliser la limite dédiée aux identités.
class ResetThrottle(AnonRateThrottle):  # Freiner les demandes de récupération.
    scope = 'reset'  # Utiliser trois demandes par heure et adresse IP.
def parse(request, **fields):  # Valider les corps des petites actions sans accès brut non contrôlé.
    serializer_type = type('ActionInput', (serializers.Serializer,), fields)  # Créer un schéma à partir des champs explicitement autorisés.
    serializer = serializer_type(data=request.data)  # Décoder le corps selon ce schéma.
    serializer.is_valid(raise_exception=True)  # Retourner une erreur 400 si un champ est invalide.
    return serializer.validated_data  # Fournir uniquement les valeurs validées.
def require_admin(request, permission):  # Appliquer les permissions fines du back-office.
    if not request.user.is_authenticated or not request.user.is_staff or not request.user.has_perm('core.' + permission):  # Vérifier identité, statut staff et droit effectif.
        raise PermissionDenied('Permission administrative requise.')  # Interdire une simple élévation du champ role.
def owned_vendor(request, pk=None):  # Résoudre exclusivement le commerce du vendeur connecté.
    vendor = get_object_or_404(Vendor, owner=request.user, **({'pk': pk} if pk is not None else {}))  # Empêcher l'accès au commerce d'un tiers.
    if request.user.role != 'vendor':  # Confirmer la cohérence du compte.
        raise PermissionDenied('Compte vendeur requis.')  # Refuser un parcours non autorisé.
    return vendor  # Retourner le commerce autorisé.
@ensure_csrf_cookie  # Poser le cookie utilisé par les formulaires et fetch.
def index(request):  # Fournir la même interface au navigateur et au conteneur mobile.
    return render(request, 'index.html')  # Garder le jeton CSRF côté serveur.
@extend_schema(request=RegisterSerializer, responses=UserSerializer)  # Décrire l'inscription dans OpenAPI.
@api_view(['POST'])  # Autoriser seulement une création explicite.
@permission_classes([AllowAny])  # Permettre l'inscription sans compte.
@throttle_classes([AuthThrottle])  # Limiter les créations automatisées.
@csrf_protect  # Bloquer une inscription forcée depuis un autre site.
def register(request):  # Créer un compte public validé.
    data = RegisterSerializer(data=request.data)  # Appliquer le schéma d'inscription.
    data.is_valid(raise_exception=True)  # Exiger un profil et un mot de passe valides.
    values = dict(data.validated_data)  # Copier les données sans les muter dans le serializer.
    values.pop('consent')  # Ne pas transmettre ce champ virtuel au modèle.
    user = User.objects.create_user(**values, consent_at=timezone.now())  # Hacher le mot de passe et dater l'acceptation.
    login(request, user)  # Ouvrir une session protégée par cookie HttpOnly.
    return Response(UserSerializer(user).data, status=201)  # Retourner le profil sans secret.
@extend_schema(request=inline_serializer(name='LoginInput', fields={'identifier': serializers.CharField(), 'password': serializers.CharField()}), responses=UserSerializer)  # Documenter le compte par email, téléphone ou identifiant.
@api_view(['POST'])  # Refuser une connexion par GET.
@permission_classes([AllowAny])  # Accepter une connexion anonyme.
@throttle_classes([AuthThrottle])  # Limiter les essais de mot de passe.
@csrf_protect  # Protéger la création de session contre le login CSRF.
def session_login(request):  # Connecter un navigateur ou l'application mobile partagée.
    values = parse(request, identifier=serializers.CharField(max_length=150), password=serializers.CharField(max_length=256))  # Borner les deux champs.
    identifier = values['identifier'].strip()  # Enlever les espaces de saisie.
    account = User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier) | Q(phone=identifier)).first()  # Résoudre les trois modes de connexion.
    user = authenticate(request, username=account.username if account else identifier, password=values['password'])  # Vérifier le hash via Django.
    if not user:  # Ne pas révéler si le compte existe ou est suspendu.
        raise ValidationError('Identifiants incorrects ou compte indisponible.')  # Fournir une erreur générique.
    login(request, user)  # Renouveler la session pour éviter sa fixation.
    return Response(UserSerializer(user).data)  # Présenter le compte connecté.
@extend_schema(request=None, responses=None)  # Documenter une déconnexion sans corps.
@api_view(['POST'])  # Modifier l'état seulement via une requête CSRF protégée.
def session_logout(request):  # Fermer la session navigateur.
    Device.objects.filter(user=request.user).delete()  # Arrêter les envois mobiles après déconnexion du compte.
    logout(request)  # Supprimer la session du serveur et du cookie.
    return Response(status=204)  # Confirmer sans renvoyer de données personnelles.
@extend_schema(responses=UserSerializer)  # Exposer le profil courant.
@api_view(['GET', 'PATCH'])  # Lire ou mettre à jour ses informations.
def me(request):  # Fournir un profil limité au propriétaire.
    if request.method == 'PATCH':  # Traiter uniquement les modifications explicites.
        data = UserSerializer(request.user, data=request.data, partial=True)  # Empêcher la modification de rôle via read_only.
        data.is_valid(raise_exception=True)  # Contrôler les champs du profil.
        data.save()  # Persister les données valides.
    return Response(UserSerializer(request.user).data)  # Renvoyer l'état courant.
@extend_schema(request=inline_serializer(name='ResetRequest', fields={'email': serializers.EmailField()}), responses=dict)  # Documenter la récupération email.
@api_view(['POST'])  # Demander un lien par formulaire.
@permission_classes([AllowAny])  # Autoriser un utilisateur déconnecté.
@throttle_classes([ResetThrottle])  # Réduire les envois abusifs.
@csrf_protect  # Prévenir les envois déclenchés depuis un site tiers.
def password_reset(request):  # Initier une récupération sans divulguer les comptes.
    values = parse(request, email=serializers.EmailField())  # Vérifier le format de l'adresse.
    user = User.objects.filter(email__iexact=values['email'], is_active=True).first()  # Rechercher un compte actif.
    if user:  # Envoyer le lien seulement si un compte est présent.
        uid = urlsafe_base64_encode(force_bytes(user.pk))  # Encoder son identifiant.
        token = default_token_generator.make_token(user)  # Produire un jeton expirant après utilisation ou changement de mot de passe.
        link = f'{settings.PUBLIC_URL}/?reset={uid}&token={token}'  # Construire le lien vers le formulaire web.
        send_mail('MIAGBO — nouveau mot de passe', f'Utilisez ce lien personnel pour changer votre mot de passe : {link}', settings.DEFAULT_FROM_EMAIL, [user.email])  # Utiliser le transport SMTP configuré.
    return Response({'message': 'Si ce compte existe, un lien de récupération a été envoyé.'})  # Conserver la même réponse pour tous.
@extend_schema(request=inline_serializer(name='ResetConfirm', fields={'uid': serializers.CharField(), 'token': serializers.CharField(), 'password': serializers.CharField()}), responses=dict)  # Décrire le changement de mot de passe.
@api_view(['POST'])  # Exiger une confirmation explicite.
@permission_classes([AllowAny])  # Accepter le lien d'un utilisateur déconnecté.
@throttle_classes([AuthThrottle])  # Limiter les tentatives de jeton.
@csrf_protect  # Protéger la confirmation web.
def password_confirm(request):  # Consommer un lien de récupération valide.
    values = parse(request, uid=serializers.CharField(max_length=100), token=serializers.CharField(max_length=200), password=serializers.CharField(max_length=256))  # Borner les valeurs.
    try:  # Traiter les identifiants encodés incorrectement.
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(values['uid'])), is_active=True)  # Rechercher l'utilisateur cible actif.
    except (ValueError, TypeError, User.DoesNotExist, UnicodeDecodeError):  # Ne pas exposer la nature du compte.
        raise ValidationError('Lien invalide ou expiré.')  # Répondre uniformément.
    if not default_token_generator.check_token(user, values['token']):  # Vérifier signature, expiration et usage unique.
        raise ValidationError('Lien invalide ou expiré.')  # Refuser une réutilisation.
    try:  # Contrôler le nouveau mot de passe.
        validate_password(values['password'], user)  # Appliquer tous les validateurs du projet.
    except DjangoValidationError as exc:  # Adapter les erreurs utilisateur.
        raise ValidationError({'password': exc.messages})  # Renvoyer les exigences non respectées.
    user.set_password(values['password'])  # Produire un nouveau hash sécurisé.
    user.save(update_fields=['password'])  # Invalider aussi les anciennes sessions via le hash.
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken  # Révoquer les jetons refresh existants.
    for token in OutstandingToken.objects.filter(user=user):  # Examiner les sessions API du compte.
        BlacklistedToken.objects.get_or_create(token=token)  # Empêcher leur renouvellement après reset.
    return Response({'message': 'Mot de passe modifié. Reconnectez-vous.'})  # Confirmer sans connexion automatique.
class VendorViewSet(viewsets.ModelViewSet):  # Exposer découverte et gestion sécurisée des commerces.
    queryset = Vendor.objects.select_related('owner').prefetch_related('hours', 'exceptions', 'subscriptions', 'reviews', Prefetch('products', queryset=Product.objects.select_related('category')))  # Réduire les requêtes répétitives.
    serializer_class = VendorSerializer  # Valider les écritures et afficher les cartes.
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']  # Éviter une suppression accidentelle de commerce via l'API.
    def get_permissions(self):  # Autoriser uniquement la découverte anonyme.
        return [AllowAny()] if self.action in ['list', 'retrieve', 'search'] else [IsAuthenticated()]  # Protéger les actions commerciales.
    def get_queryset(self):  # Masquer les commerces en attente ou appartenant à un compte suspendu.
        if self.action in ['partial_update', 'status', 'products', 'hours', 'exceptions', 'subscriptions', 'dashboard', 'quote']:  # Résoudre les objets de l'espace pro.
            return self.queryset.filter(owner=self.request.user) if self.request.user.is_authenticated else self.queryset.none()  # Éviter toute fuite entre vendeurs.
        return self.queryset.filter(moderation='approved', owner__is_active=True)  # Publier uniquement les commerces valides.
    def perform_create(self, serializer):  # Enrôler un nouveau commerce.
        if self.request.user.role != 'vendor' or Vendor.objects.filter(owner=self.request.user).exists():  # Exiger un vendeur sans commerce existant.
            raise ValidationError('Compte vendeur requis, avec un seul commerce par compte.')  # Expliquer la règle MVP.
        with transaction.atomic():  # Créer profil et trial ensemble.
            User.objects.select_for_update().get(pk=self.request.user.pk)  # Sérialiser deux inscriptions simultanées.
            vendor = serializer.save(owner=self.request.user)  # Fixer le propriétaire côté serveur.
            now = timezone.now()  # Figer le début de l'essai.
            Subscription.objects.create(vendor=vendor, plan='discovery', start=now, end=add_months(now, 1))  # Accorder un seul mois gratuit initial.
            audit(self.request.user, 'vendor.create', vendor.id)  # Journaliser l'enrôlement.
    def perform_update(self, serializer):  # Soumettre les modifications importantes à nouveau contrôle.
        vendor = serializer.save(moderation='pending', moderation_reason='Profil modifié : nouvelle validation nécessaire.')  # Empêcher de transformer un commerce validé en faux profil.
        audit(self.request.user, 'vendor.update', vendor.id)  # Tracer le changement.
    def retrieve(self, request, *args, **kwargs):  # Fournir une fiche détaillée.
        vendor = self.get_object()  # Vérifier la publication.
        Vendor.objects.filter(pk=vendor.pk).update(views=F('views') + 1)  # Incrémenter sans écrasement concurrent.
        vendor.views += 1  # Refléter le nouveau compteur dans la réponse.
        return Response(VendorDetailSerializer(vendor, context={'request': request}).data)  # Afficher catalogue, horaires et avis.
    @extend_schema(parameters=[OpenApiParameter('lat', float, required=True), OpenApiParameter('lng', float, required=True), OpenApiParameter('radius', int), OpenApiParameter('q', str), OpenApiParameter('open', bool), OpenApiParameter('category', int)], responses=VendorSerializer(many=True))  # Décrire les filtres géographiques.
    @action(detail=False, methods=['get'])  # Exposer /vendors/search/ avant les identifiants.
    def search(self, request):  # Rechercher les produits publiés dans un rayon précis.
        try:  # Valider aussi NaN et inf qui passent un simple float().
            lat, lng = float(request.query_params['lat']), float(request.query_params['lng'])  # Lire l'origine consentie.
            radius = int(request.query_params.get('radius', 2000))  # Utiliser deux kilomètres par défaut.
            if not all(math.isfinite(v) for v in [lat, lng]) or not -90 <= lat <= 90 or not -180 <= lng <= 180 or not 100 <= radius <= 20000:  # Encadrer les coordonnées et le coût de recherche.
                raise ValueError()  # Utiliser un message de validation unique.
        except (KeyError, ValueError, TypeError):  # Gérer paramètres absents ou invalides.
            raise ValidationError('Coordonnées valides et rayon entre 100 et 20 000 mètres requis.')  # Indiquer les unités exactes.
        keyword = request.query_params.get('q', '').strip()[:100]  # Borner le terme enregistré et recherché.
        category = request.query_params.get('category', '')  # Lire le filtre facultatif.
        if category and not category.isdigit():  # Empêcher une erreur SQL due au type de catégorie.
            raise ValidationError('Catégorie invalide.')  # Refuser une entrée non numérique.
        rows = self.get_queryset()  # Partir uniquement des commerces publiés.
        cache_key = 'spatial:' + hashlib.sha256(f'{lat}:{lng}:{radius}'.encode()).hexdigest()  # Ne conserver qu'une empreinte de la requête dans les clés du cache.
        cached_ids = cache.get(cache_key) if settings.CACHE_REDIS else None  # Activer la présélection partagée uniquement avec Redis.
        if cached_ids is not None:  # Réutiliser une présélection géographique de moins de trente secondes.
            rows = rows.filter(pk__in=cached_ids)  # Revérifier quand même publication et suspension sur les données actuelles.
        elif connection.vendor == 'postgresql':  # Utiliser l'index géographique en production.
            geo = 'ST_SetSRID(ST_MakePoint(longitude, latitude),4326)::geography'  # Correspondre exactement à l'index d'expression.
            rows = rows.annotate(in_radius=RawSQL(f'ST_DWithin({geo}, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s)', [lng, lat, radius * 1.01])).filter(in_radius=True)  # Surinclure légèrement avant Haversine pour éviter les écarts sphère/sphéroïde aux bornes.
        else:  # Réduire les candidats avant Haversine pour le développement.
            delta = radius / 110000  # Convertir approximativement le rayon en latitude.
            rows = rows.filter(latitude__range=(lat - delta, lat + delta))  # Ne pas utiliser un filtre longitude incorrect près de l'antiméridien.
        if cached_ids is None and settings.CACHE_REDIS:  # Mettre en cache seulement les identifiants géographiques, jamais les fiches ni les statuts.
            rows = list(rows)  # Exécuter la présélection avec les relations nécessaires déjà préchargées.
            cache.set(cache_key, [vendor.pk for vendor in rows], 30)  # Limiter l'apparition d'un nouveau commerce à trente secondes de latence de cache.
        matches = []  # Collecter les commerces répondant à tous les critères.
        for vendor in rows:  # Appliquer les règles de catalogue réellement visible.
            dist = distance_m(lat, lng, vendor.latitude, vendor.longitude)  # Calculer la distance affichée uniformément.
            if dist > radius or (request.query_params.get('open') in ['1', 'true'] and not is_open(vendor)):  # Respecter strictement rayon et disponibilité.
                continue  # Ignorer ce commerce.
            products = visible_products(vendor)  # Ne jamais retrouver un produit masqué par abonnement.
            candidates = [p for p in products if not category or p.category_id == int(category)]  # Restreindre les produits à la catégorie choisie.
            if category and not candidates:  # Exiger une offre correspondante.
                continue  # Écarter les commerces hors catégorie.
            if keyword and keyword.casefold() not in vendor.name.casefold() and not any(keyword.casefold() in (p.name + ' ' + p.description).casefold() for p in candidates):  # Rechercher nom et catalogue actif.
                continue  # Écarter les commerces ne proposant pas le terme.
            vendor.distance = dist  # Transmettre la distance au serializer.
            matches.append(vendor)  # Conserver le résultat.
        matches.sort(key=lambda v: (-int(plan_key(v) == 'performance'), round(v.distance / 50), -PLANS[plan_key(v)]['priority'], v.distance, v.pk))  # Prioriser Premium dans le rayon puis proximité et formule à distance comparable.
        SearchEvent.objects.create(keyword=keyword, vendor_ids=[v.id for v in matches[:100]])  # Enregistrer les tendances sans position personnelle.
        page = self.paginate_queryset(matches)  # Limiter les résultats renvoyés à trente par page.
        return self.get_paginated_response(VendorSerializer(page, many=True, context={'request': request}).data)  # Fournir pagination et résultats.
    @action(detail=False, methods=['get'], url_path='mine')  # Fournir le profil vendeur même avant validation.
    def mine(self, request):  # Charger son propre commerce.
        vendor = owned_vendor(request)  # Vérifier l'identité du responsable.
        return Response(VendorDetailSerializer(vendor, context={'request': request}).data)  # Fournir les informations de travail.
    @action(detail=True, methods=['patch'], url_path='status')  # Gérer un état manuel temporaire.
    def status(self, request, pk=None):  # Alterner entre horaires et dérogation de douze heures.
        vendor = owned_vendor(request, pk)  # Vérifier le propriétaire.
        values = parse(request, status=serializers.ChoiceField(choices=['auto', 'open', 'closed']))  # Refuser les statuts arbitraires.
        vendor.status_override = values['status']  # Stocker le choix.
        vendor.override_until = timezone.now() + timedelta(hours=12) if values['status'] != 'auto' else None  # Ne pas laisser un statut manuel périmé indéfiniment.
        vendor.save(update_fields=['status_override', 'override_until'])  # Modifier uniquement le statut.
        return Response(VendorSerializer(vendor).data)  # Afficher la disponibilité effective.
    @extend_schema(request=ProductSerializer, responses=ProductSerializer(many=True))  # Documenter le catalogue vendeur.
    @action(detail=True, methods=['get', 'post'])  # Lire ses produits ou en ajouter.
    def products(self, request, pk=None):  # Gérer un catalogue en contrôlant le quota à l'écriture.
        vendor = owned_vendor(request, pk)  # Empêcher un ajout chez un autre vendeur.
        if request.method == 'GET':  # Afficher aussi les produits conservés après expiration.
            return Response(ProductSerializer(vendor.products.all().order_by('id'), many=True, context={'request': request}).data)  # Préserver l'accès du propriétaire à tout son catalogue.
        data = ProductSerializer(data=request.data)  # Vérifier prix, catégorie et média.
        data.is_valid(raise_exception=True)  # Refuser un produit invalide.
        with transaction.atomic():  # Protéger le quota contre deux ajouts simultanés.
            Vendor.objects.select_for_update().get(pk=vendor.pk)  # Verrouiller le commerce.
            limit = product_limit(vendor)  # Consulter les droits au moment de l'écriture.
            if limit is not None and vendor.products.count() >= limit:  # Compter aussi les produits indisponibles.
                raise ValidationError(f'Votre formule permet {limit} produits ; supprimez un produit ou changez de formule.')  # Expliquer le quota.
            product = data.save(vendor=vendor)  # Attribuer le produit au commerce validé.
        return Response(ProductSerializer(product, context={'request': request}).data, status=201)  # Confirmer l'ajout.
    @extend_schema(request=HourSerializer(many=True), responses=HourSerializer(many=True))  # Décrire le remplacement atomique des horaires.
    @action(detail=True, methods=['put'])  # Remplacer le planning entier.
    def hours(self, request, pk=None):  # Valider toutes les plages avant toute suppression.
        vendor = owned_vendor(request, pk)  # Vérifier le commerce.
        data = HourSerializer(data=request.data, many=True)  # Contrôler chaque plage.
        data.is_valid(raise_exception=True)  # Conserver l'ancien planning si la saisie échoue.
        if len(data.validated_data) > 28:  # Limiter les plages abusives.
            raise ValidationError('Au plus 28 plages hebdomadaires.')  # Fournir une borne raisonnable.
        with transaction.atomic():  # Rendre le remplacement indivisible.
            Vendor.objects.select_for_update().get(pk=vendor.pk)  # Sérialiser les changements.
            vendor.hours.all().delete()  # Retirer l'ancien planning après validation.
            for hour in data.validated_data:  # Parcourir les plages correctes.
                OpeningHour.objects.create(vendor=vendor, **hour)  # Enregistrer chaque horaire.
        return Response(HourSerializer(vendor.hours.all(), many=True).data)  # Retourner le planning enregistré.
    @extend_schema(request=ExceptionSerializer(many=True), responses=ExceptionSerializer(many=True))  # Décrire le calendrier exceptionnel.
    @action(detail=True, methods=['put'])  # Remplacer les exceptions atomiquement.
    def exceptions(self, request, pk=None):  # Gérer jours fériés et fermetures ponctuelles.
        vendor = owned_vendor(request, pk)  # Vérifier le responsable.
        data = ExceptionSerializer(data=request.data, many=True)  # Contrôler toutes les dates.
        data.is_valid(raise_exception=True)  # Refuser une plage incohérente.
        dates = [item['date'] for item in data.validated_data]  # Rassembler les journées.
        if len(dates) > 366 or len(set(dates)) != len(dates):  # Refuser doublons et calendrier illimité.
            raise ValidationError('Dates uniques requises, au plus 366 exceptions.')  # Expliquer l'invariant.
        with transaction.atomic():  # Garantir le remplacement complet.
            Vendor.objects.select_for_update().get(pk=vendor.pk)  # Éviter les modifications concurrentes.
            vendor.exceptions.all().delete()  # Retirer le calendrier précédent.
            for item in data.validated_data:  # Parcourir les exceptions contrôlées.
                OpeningException.objects.create(vendor=vendor, **item)  # Persister les décisions.
        return Response(ExceptionSerializer(vendor.exceptions.all(), many=True).data)  # Confirmer les exceptions.
    @action(detail=True, methods=['get'])  # Fournir les statistiques pro.
    def dashboard(self, request, pk=None):  # Mesurer les consultations et évaluations.
        vendor = owned_vendor(request, pk)  # Garder les métriques privées.
        current = active_subscription(vendor)  # Fournir l'échéance des droits effectifs.
        hits = sum(vendor.pk in event.vendor_ids for event in SearchEvent.objects.filter(created_at__gte=timezone.now() - timedelta(days=30)))  # Compter les apparitions récentes sans coordonnées client.
        return Response({'views': vendor.views, 'review_count': vendor.reviews.filter(visible=True).count(), 'rating': rating(vendor), 'search_hits_30d': hits if plan_key(vendor) != 'discovery' else None, 'plan': plan_key(vendor), 'expires': current.end if current else None, 'product_limit': product_limit(vendor), 'payments': PaymentSerializer(vendor.payments.order_by('-created_at')[:50], many=True).data})  # Exposer les chiffres correspondant à la formule.
    @action(detail=True, methods=['post'], url_path='quote')  # Calculer un devis avant une demande.
    def quote(self, request, pk=None):  # Expliquer le crédit et le montant demandé.
        vendor = owned_vendor(request, pk)  # Vérifier le propriétaire.
        values = parse(request, plan=serializers.ChoiceField(choices=list(PLANS)))  # Limiter aux formules connues.
        return Response(quote(vendor, values['plan']))  # Retourner un devis calculé côté serveur.
    @action(detail=True, methods=['post'])  # Créer une transaction en attente sans simuler un encaissement.
    def subscriptions(self, request, pk=None):  # Demander un abonnement payable selon le moyen local validé.
        vendor = owned_vendor(request, pk)  # Vérifier le responsable du commerce.
        values = parse(request, plan=serializers.ChoiceField(choices=list(PLANS)))  # Refuser les offres inconnues.
        with transaction.atomic():  # Sérialiser les demandes d'un commerce.
            Vendor.objects.select_for_update().get(pk=vendor.pk)  # Verrouiller l'identité métier.
            existing = vendor.payments.filter(status='pending', created_at__gte=timezone.now() - timedelta(hours=24)).first()  # Éviter deux devis actifs simultanés.
            if existing:  # Ne pas réutiliser une transaction pour une autre formule.
                raise ValidationError('Une demande est déjà en attente ; faites-la traiter avant une nouvelle demande.')  # Expliquer la marche à suivre.
            price = quote(vendor, values['plan'])  # Figer le calcul monétaire du serveur.
            payment = Payment.objects.create(vendor=vendor, base_subscription=active_subscription(vendor), plan=values['plan'], amount=price['amount'], reference='MGB-' + secrets.token_hex(10).upper())  # Créer une référence unique.
        audit(request.user, 'payment.request', payment.id, amount=payment.amount)  # Tracer le devis.
        return Response({'payment': PaymentSerializer(payment).data, 'message': 'Demande créée. Effectuez le règlement selon les instructions de l’opérateur MIAGBO ; les droits seront activés après vérification du reçu.', 'checkout_url': None}, status=201)  # Ne jamais prétendre disposer d'un checkout non configuré.
class ProductViewSet(viewsets.GenericViewSet):  # Permettre modification et suppression de son catalogue.
    serializer_class = ProductSerializer  # Valider prix et médias.
    queryset = Product.objects.all()  # Définir le modèle pour le routeur et OpenAPI.
    def get_queryset(self):  # Restreindre les objets au propriétaire connecté.
        return self.queryset.filter(vendor__owner=self.request.user)  # Empêcher l'accès par simple identifiant tiers.
    def partial_update(self, request, pk=None):  # Modifier un produit existant.
        product = self.get_object()  # Vérifier la propriété.
        data = self.get_serializer(product, data=request.data, partial=True)  # Appliquer les validations même en PATCH.
        data.is_valid(raise_exception=True)  # Refuser un prix ou fichier invalide.
        data.save()  # Persister le changement.
        return Response(data.data)  # Retourner le produit modifié.
    def destroy(self, request, pk=None):  # Supprimer un produit de son propre commerce.
        product = self.get_object()  # Vérifier les droits sur l'objet.
        product.delete()  # Retirer le produit demandé.
        return Response(status=204)  # Confirmer la suppression.
class ReviewViewSet(viewsets.GenericViewSet):  # Gérer les avis et les réponses vendeur.
    serializer_class = ReviewSerializer  # Contrôler note et texte.
    queryset = Review.objects.select_related('author', 'vendor')  # Éviter les requêtes supplémentaires d'identité.
    def create(self, request):  # Déposer un avis unique.
        data = self.get_serializer(data=request.data)  # Vérifier le schéma public.
        data.is_valid(raise_exception=True)  # Refuser note hors plage.
        vendor = data.validated_data['vendor']  # Charger le commerce évalué.
        if request.user.role != 'client' or vendor.moderation != 'approved' or not vendor.owner.is_active:  # Interdire auto-avis, faux commerces et vendeurs suspendus.
            raise ValidationError('Seul un client peut évaluer un commerce publié.')  # Expliquer la règle.
        if Review.objects.filter(author=request.user, vendor=vendor).exists():  # Répondre proprement au doublon.
            raise ValidationError('Vous avez déjà évalué ce commerce.')  # Ne pas multiplier les notes d'un même compte.
        review = data.save(author=request.user)  # Fixer le véritable auteur.
        Notification.objects.create(user=vendor.owner, title='Nouvel avis', message=f'Un client a évalué votre commerce : {review.rating}/5.')  # Informer le commerçant.
        return Response(ReviewSerializer(review).data, status=201)  # Renvoyer l'avis créé.
    @action(detail=True, methods=['post'])  # Réserver la réponse au commerçant concerné.
    def reply(self, request, pk=None):  # Répondre à un avis reçu.
        review = get_object_or_404(Review, pk=pk, vendor__owner=request.user, visible=True)  # Empêcher la réponse aux avis d'un tiers.
        values = parse(request, reply=serializers.CharField(max_length=1500))  # Limiter la longueur de la réponse.
        review.reply = values['reply']  # Stocker le texte validé.
        review.save(update_fields=['reply'])  # Modifier uniquement la réponse.
        Notification.objects.create(user=review.author, title='Le commerçant vous a répondu', message=review.reply)  # Prévenir le client dans sa boîte de réception.
        return Response(ReviewSerializer(review).data)  # Afficher la réponse.
class ReportViewSet(viewsets.GenericViewSet):  # Collecter les signalements sans exposer les déclarants.
    serializer_class = ReportSerializer  # Exiger une cible unique.
    queryset = Report.objects.none()  # Interdire la consultation publique des dossiers.
    def create(self, request):  # Enregistrer un abus présumé.
        data = self.get_serializer(data=request.data)  # Contrôler la déclaration.
        data.is_valid(raise_exception=True)  # Valider la cible et le motif.
        data.save(author=request.user)  # Fixer le déclarant connecté.
        return Response(data.data, status=201)  # Confirmer la prise en compte.
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):  # Donner accès uniquement à la boîte de réception personnelle.
    serializer_class = NotificationSerializer  # Exposer titre, contenu et lecture.
    queryset = Notification.objects.all()  # Définir la source générale.
    def get_queryset(self):  # Isoler les messages de chaque compte.
        return self.queryset.filter(user=self.request.user).order_by('-created_at')  # Trier du plus récent au plus ancien.
    @action(detail=True, methods=['post'])  # Marquer un message lu.
    def read(self, request, pk=None):  # Modifier uniquement sa notification.
        item = self.get_object()  # Vérifier la propriété par le queryset.
        item.read = True  # Marquer la consultation.
        item.save(update_fields=['read'])  # Persister l'indicateur.
        return Response(self.get_serializer(item).data)  # Confirmer l'état.
@extend_schema(responses=CategorySerializer(many=True))  # Documenter la taxonomie publique.
@api_view(['GET'])  # Fournir une liste stable aux formulaires.
@permission_classes([AllowAny])  # Autoriser la découverte anonyme.
def categories(request):  # Charger les catégories disponibles.
    return Response(CategorySerializer(Category.objects.order_by('name'), many=True).data)  # Fournir la hiérarchie.
@extend_schema(responses=dict)  # Décrire les offres publiques.
@api_view(['GET'])  # Permettre la consultation sans engagement.
@permission_classes([AllowAny])  # Afficher les prix avant inscription.
def plans(request):  # Afficher le référentiel tarifaire.
    return Response([{'key': key, **value} for key, value in PLANS.items()])  # Ajouter les clés des formules.
@extend_schema(responses=VendorSerializer(many=True))  # Documenter les favoris personnels.
@api_view(['GET', 'POST', 'DELETE'])  # Lire, ajouter ou retirer explicitement un favori.
def favorites(request):  # Gérer une liste réservée à son propriétaire.
    if request.method == 'GET':  # Afficher les favoris encore publiés.
        rows = Vendor.objects.filter(favorite__user=request.user, moderation='approved', owner__is_active=True)  # Masquer les commerces retirés.
        return Response(VendorSerializer(rows, many=True, context={'request': request}).data)  # Renvoyer les fiches légères.
    values = parse(request, vendor=serializers.IntegerField(min_value=1))  # Contrôler l'identifiant.
    vendor = get_object_or_404(Vendor, pk=values['vendor'], moderation='approved', owner__is_active=True)  # Vérifier que le commerce est public.
    if request.method == 'POST':  # Ajouter sans duplication.
        Favorite.objects.get_or_create(user=request.user, vendor=vendor)  # Rendre l'action idempotente.
    else:  # Traiter la suppression explicite.
        Favorite.objects.filter(user=request.user, vendor=vendor).delete()  # Retirer uniquement son propre favori.
    return Response(status=204)  # Confirmer sans exposer d'autre compte.
@extend_schema(request=DeviceSerializer, responses=dict)  # Documenter l'inscription d'un terminal mobile.
@api_view(['POST'])  # Modifier les préférences seulement après authentification.
def devices(request):  # Associer un token consenti à son utilisateur.
    data = DeviceSerializer(data=request.data)  # Valider plateforme et token.
    data.is_valid(raise_exception=True)  # Refuser les entrées incohérentes.
    Device.objects.update_or_create(token=data.validated_data['token'], defaults={'user': request.user, 'platform': data.validated_data['platform']})  # Réattribuer le terminal lors d'un changement de compte.
    return Response({'registered': True, 'push_transport': 'expo' if settings.PUSH_ENABLED else 'not_configured'})  # Indiquer honnêtement que le transport distant reste à configurer.
@extend_schema(responses=dict)  # Documenter l'export personnel.
@api_view(['GET', 'DELETE'])  # Fournir portabilité et fermeture du compte.
def account(request):  # Permettre à l'utilisateur de contrôler ses données.
    if request.method == 'GET':  # Produire une archive JSON personnelle.
        data = {'profile': UserSerializer(request.user).data, 'reviews': ReviewSerializer(request.user.reviews.all(), many=True).data, 'favorites': list(request.user.favorites.values_list('vendor_id', flat=True)), 'notifications': NotificationSerializer(request.user.notifications.all(), many=True).data, 'alert_zone': AlertZoneSerializer(AlertZone.objects.filter(user=request.user).first()).data if AlertZone.objects.filter(user=request.user).exists() else None}  # Inclure aussi la seule zone géographique volontairement enregistrée.
        vendor = Vendor.objects.filter(owner=request.user).first()  # Rechercher un commerce possédé par ce compte seulement.
        if vendor:  # Inclure l'ensemble du catalogue propriétaire, même au-delà du quota public.
            data.update({'vendor':VendorDetailSerializer(vendor,context={'request':request}).data,'products':ProductSerializer(vendor.products.all(),many=True,context={'request':request}).data,'payments':PaymentSerializer(vendor.payments.all(),many=True).data,'subscriptions':list(vendor.subscriptions.values('plan','start','end','amount'))})  # Permettre une portabilité complète du commerce sans secrets financiers.
        return Response(data)  # Exclure hashes, tokens et données tierces privées.
    values = parse(request, password=serializers.CharField(max_length=256))  # Exiger une preuve supplémentaire avant désactivation.
    if not request.user.check_password(values['password']) or request.user.is_staff:  # Protéger le compte et le dernier accès administratif.
        raise ValidationError('Mot de passe incorrect ou compte administratif à traiter par un autre administrateur.')  # Refuser une fermeture non autorisée.
    request.user.is_active = False  # Retirer immédiatement l'accès et la publication du commerce.
    request.user.save(update_fields=['is_active'])  # Conserver temporairement l'historique financier.
    Device.objects.filter(user=request.user).delete()  # Cesser les envois à ce compte.
    AlertZone.objects.filter(user=request.user).delete()  # Retirer la zone consentie dès la fermeture du compte.
    audit(request.user, 'account.close', request.user.pk)  # Tracer la demande de fermeture.
    logout(request)  # Fermer la session actuelle.
    return Response({'message': 'Compte désactivé. Contactez le responsable MIAGBO pour l’effacement définitif des données soumises aux obligations de conservation.'})  # Distinguer suspension immédiate et traitement d'effacement.
@extend_schema(responses=dict)  # Documenter les données du tableau de bord.
@api_view(['GET'])  # Lire les métriques avec permission explicite.
def admin_dashboard(request):  # Fournir un aperçu de la modération et des revenus.
    require_admin(request, 'view_user')  # Vérifier le rôle et son droit de lecture.
    return Response({'users': User.objects.count(), 'vendors': Vendor.objects.count(), 'pending': VendorSerializer(Vendor.objects.filter(moderation='pending'), many=True, context={'request': request}).data if request.user.has_perm('core.change_vendor') else [], 'reports': ReportSerializer(Report.objects.filter(resolved=False), many=True).data if request.user.has_perm('core.change_report') else [], 'payments': PaymentSerializer(Payment.objects.filter(status='pending'), many=True).data if request.user.has_perm('core.change_payment') else [], 'revenue': Payment.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0, 'searches': SearchEvent.objects.count(), 'top_keywords': list(SearchEvent.objects.exclude(keyword='').values('keyword').annotate(count=Count('id')).order_by('-count')[:10]), 'top_vendors': list(Vendor.objects.order_by('-views').values('id', 'name', 'views')[:10])})  # Ne pas exposer un dossier sans son droit métier.
@extend_schema(responses=UserSerializer(many=True))  # Documenter le registre utilisateurs.
@api_view(['GET'])  # Accéder aux comptes avec une permission de lecture.
def admin_users(request):  # Rechercher les utilisateurs du back-office.
    require_admin(request, 'view_user')  # Bloquer les comptes ordinaires.
    keyword = request.query_params.get('q', '')[:100]  # Borner le filtre.
    rows = User.objects.filter(Q(username__icontains=keyword) | Q(email__icontains=keyword) | Q(first_name__icontains=keyword)).order_by('-date_joined')[:100]  # Limiter la liste aux cent premiers résultats.
    return Response([{**UserSerializer(user).data, 'is_active': user.is_active} for user in rows])  # Ajouter l'état administratif.
@extend_schema(responses=dict)  # Documenter la décision sur un compte.
@api_view(['POST'])  # Exiger une action explicite de suspension.
def admin_user_status(request, pk):  # Suspendre ou réactiver un compte.
    require_admin(request, 'change_user')  # Vérifier le droit de gestion des comptes.
    user = get_object_or_404(User, pk=pk)  # Résoudre la cible.
    if user.is_staff or user.pk == request.user.pk:  # Éviter les verrouillages du back-office et manipulations de collègues via l'outil simplifié.
        raise ValidationError('Gérez les comptes administratifs dans le back-office avancé.')  # Orienter vers les permissions Django.
    values = parse(request, active=serializers.BooleanField())  # Exiger un booléen réel.
    user.is_active = values['active']  # Appliquer la décision.
    user.save(update_fields=['is_active'])  # Persister seulement le statut.
    audit(request.user, 'user.status', user.pk, active=user.is_active)  # Tracer la suspension ou réactivation.
    return Response({'is_active': user.is_active})  # Confirmer la décision.
@extend_schema(responses=VendorSerializer)  # Documenter la validation commerciale.
@api_view(['POST'])  # Valider ou rejeter explicitement un profil.
def admin_vendor(request, pk):  # Décider de la publication d'un commerce.
    require_admin(request, 'change_vendor')  # Vérifier le droit de modération.
    vendor = get_object_or_404(Vendor, pk=pk)  # Charger le dossier.
    values = parse(request, decision=serializers.ChoiceField(choices=['approved', 'rejected']), reason=serializers.CharField(max_length=1000))  # Exiger décision et justification.
    vendor.moderation, vendor.moderation_reason = values['decision'], values['reason']  # Conserver le motif.
    vendor.save(update_fields=['moderation', 'moderation_reason'])  # Appliquer la publication ou le retrait.
    Notification.objects.create(user=vendor.owner, title='Validation de votre commerce', message=values['reason'])  # Informer le responsable.
    audit(request.user, 'vendor.moderate', vendor.pk, decision=values['decision'], reason=values['reason'])  # Journaliser la décision.
    return Response(VendorSerializer(vendor).data)  # Confirmer l'état.
@extend_schema(responses=ReportSerializer)  # Documenter le traitement d'un abus.
@api_view(['POST'])  # Décider explicitement du signalement.
def admin_report(request, pk):  # Résoudre et éventuellement masquer le contenu signalé.
    require_admin(request, 'change_report')  # Vérifier le droit de traitement.
    report = get_object_or_404(Report, pk=pk)  # Charger le dossier.
    values = parse(request, resolution=serializers.CharField(max_length=1000), hide=serializers.BooleanField(default=False))  # Exiger un motif et un choix explicite.
    if values['hide']:  # Vérifier aussi le droit sur la cible à retirer.
        require_admin(request, 'change_review' if report.review_id else 'change_vendor')  # Empêcher un modérateur de dépasser ses permissions.
    with transaction.atomic():  # Enregistrer retrait et résolution ensemble.
        if values['hide'] and report.review_id:  # Masquer l'avis abusif.
            Review.objects.filter(pk=report.review_id).update(visible=False)  # Retirer aussi sa note des moyennes publiques.
        elif values['hide']:  # Retirer un commerce signalé.
            Vendor.objects.filter(pk=report.vendor_id).update(moderation='rejected', moderation_reason=values['resolution'])  # Cesser sa publication.
        report.resolved, report.resolution = True, values['resolution']  # Décrire le traitement.
        report.save(update_fields=['resolved', 'resolution'])  # Persister la décision.
        audit(request.user, 'report.resolve', report.pk, hide=values['hide'], resolution=values['resolution'])  # Tracer l'opération.
    return Response(ReportSerializer(report).data)  # Confirmer la résolution.
@extend_schema(responses=PaymentSerializer)  # Documenter la validation de reçu.
@api_view(['POST'])  # Confirmer ou rejeter un paiement explicitement.
def admin_payment(request, pk):  # Vérifier manuellement les règlements tant que l'opérateur n'est pas intégré.
    require_admin(request, 'change_payment')  # Réserver l'action aux opérateurs financiers.
    values = parse(request, decision=serializers.ChoiceField(choices=['paid', 'rejected']), external_reference=serializers.CharField(max_length=120))  # Exiger la référence du reçu ou le motif de rejet.
    payment = get_object_or_404(Payment, pk=pk)  # Charger la transaction.
    if values['decision'] == 'paid':  # Accorder des droits après vérification externe par l'opérateur.
        confirm_payment(payment.pk, request.user, values['external_reference'])  # Utiliser le service transactionnel idempotent.
    else:  # Rejeter sans modifier les droits.
        with transaction.atomic():  # Protéger la décision concurrente avec un webhook.
            payment = Payment.objects.select_for_update().get(pk=pk)  # Verrouiller l'état financier.
            if payment.status != 'pending':  # Ne jamais annuler un paiement déjà confirmé depuis cet écran.
                raise ValidationError('Seul un paiement en attente peut être rejeté.')  # Expliquer le conflit.
            payment.status, payment.external_reference = 'rejected', values['external_reference']  # Conserver le motif dans la référence du dossier.
            payment.save(update_fields=['status', 'external_reference'])  # Persister le refus.
            audit(request.user, 'payment.reject', payment.pk, reason=values['external_reference'])  # Tracer le rejet.
    payment.refresh_from_db()  # Relire l'état modifié par le service.
    return Response(PaymentSerializer(payment).data)  # Retourner l'état définitif.
@extend_schema(responses=dict)  # Décrire la diffusion de messages internes.
@api_view(['POST'])  # Publier un message après validation administrative.
def admin_broadcast(request):  # Diffuser à tous ou à un rôle précis avec une borne de volume.
    require_admin(request, 'add_notification')  # Vérifier le droit de communication.
    values = parse(request, title=serializers.CharField(max_length=120), message=serializers.CharField(max_length=2000), role=serializers.ChoiceField(choices=['all', 'client', 'vendor']))  # Contrôler la cible et le contenu.
    users = User.objects.filter(is_active=True)  # Exclure les comptes suspendus.
    if values['role'] != 'all':  # Appliquer le ciblage demandé.
        users = users.filter(role=values['role'])  # Limiter aux clients ou vendeurs.
    count = users.count()  # Mesurer le volume.
    if count > 10000:  # Éviter une diffusion massive synchrone.
        raise ValidationError('Au-delà de 10 000 destinataires, utilisez un traitement asynchrone.')  # Documenter la limite opérationnelle.
    Notification.objects.bulk_create([Notification(user=user, title=values['title'], message=values['message']) for user in users], batch_size=500)  # Enregistrer efficacement la boîte de réception.
    audit(request.user, 'notification.broadcast', values['role'], recipients=count)  # Tracer la campagne.
    return Response({'recipients': count, 'transport': 'inbox'})  # Distinguer messages internes et push distant.
@extend_schema(responses=bytes)  # Décrire le fichier de portabilité administrative.
@api_view(['GET'])  # Exporter sans mutation.
def admin_export(request):  # Fournir un CSV protégé contre les formules de tableur.
    require_admin(request, 'view_user')  # Restreindre les données personnelles aux opérateurs autorisés.
    response = HttpResponse(content_type='text/csv; charset=utf-8')  # Déclarer le format téléchargé.
    response['Content-Disposition'] = 'attachment; filename="miagbo-utilisateurs.csv"'  # Proposer un nom de fichier clair.
    writer = csv.writer(response)  # Échapper les séparateurs conformément au format CSV.
    writer.writerow(['id', 'identifiant', 'nom', 'email', 'role', 'actif'])  # Donner des en-têtes stables.
    for user in User.objects.order_by('id').iterator():  # Exporter sans charger toute la base.
        fields = [user.pk, user.username, user.first_name, user.email, user.role, user.is_active]  # Limiter le contenu utile.
        writer.writerow(["'" + v if isinstance(v, str) and (v.lstrip().startswith(('=', '+', '-', '@')) or v.startswith(('\t', '\r', '\n'))) else v for v in fields])  # Neutraliser l'exécution de formules à l'ouverture.
    audit(request.user, 'users.export', 'csv')  # Tracer l'accès de masse aux données.
    return response  # Envoyer le fichier.
@extend_schema(responses=dict)  # Documenter l'état de disponibilité.
@api_view(['GET'])  # Fournir une sonde publique minimale.
@permission_classes([AllowAny])  # Permettre la supervision sans compte.
def health(request):  # Vérifier que le serveur et la base répondent.
    with connection.cursor() as cursor:  # Utiliser la connexion configurée.
        cursor.execute('SELECT 1')  # Effectuer une requête SQL triviale.
    return Response({'status': 'ok'})  # Ne divulguer aucun secret ni détail d'infrastructure.
@extend_schema(responses=dict)  # Documenter les paramètres publics.
@api_view(['GET'])  # Fournir les réglages non secrets.
@permission_classes([AllowAny])  # Afficher les rayons avant connexion.
def configuration(request):  # Publier seulement une liste blanche de configuration.
    values = {'radii': [500, 1000, 2000, 5000, 10000], 'default_radius': 2000, 'minimum_android': '1.0.0', 'minimum_ios': '1.0.0'}  # Garantir des valeurs de secours.
    for item in Configuration.objects.filter(key__in=values):  # Exclure tout paramètre interne.
        values[item.key] = item.value  # Charger les valeurs administrées.
    values['google_enabled'] = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)  # Afficher la connexion sociale seulement lorsqu'elle est configurée.
    values['push_enabled'] = settings.PUSH_ENABLED  # Afficher l'activation mobile seulement si le transport est activé.
    return Response(values)  # Fournir des paramètres publics uniquement.
from drf_spectacular.utils import extend_schema_view, OpenApiTypes  # Compléter les actions qui utilisent des schémas de petits formulaires.
def input_schema(name, **fields):  # Donner un nom stable à chaque corps d'action dans OpenAPI.
    return inline_serializer(name=name, fields=fields)  # Construire le contrat documentaire des champs validés par parse().
me = extend_schema(request=UserSerializer)(me)  # Documenter aussi la mise à jour du profil.
favorites = extend_schema(request=input_schema('FavoriteInput', vendor=serializers.IntegerField(min_value=1)))(favorites)  # Décrire les ajouts et retraits de favoris.
account = extend_schema(request=input_schema('AccountCloseInput', password=serializers.CharField()))(account)  # Décrire la preuve de fermeture.
admin_user_status = extend_schema(request=input_schema('UserStatusInput', active=serializers.BooleanField()))(admin_user_status)  # Décrire le statut administratif.
admin_vendor = extend_schema(request=input_schema('VendorDecisionInput', decision=serializers.ChoiceField(choices=['approved','rejected']), reason=serializers.CharField(max_length=1000)))(admin_vendor)  # Décrire les décisions de publication.
admin_report = extend_schema(request=input_schema('ReportResolutionInput', resolution=serializers.CharField(max_length=1000), hide=serializers.BooleanField(default=False)))(admin_report)  # Décrire clôture et retrait d'un contenu.
admin_payment = extend_schema(request=input_schema('PaymentDecisionInput', decision=serializers.ChoiceField(choices=['paid','rejected']), external_reference=serializers.CharField(max_length=120)))(admin_payment)  # Décrire la vérification d'un reçu.
admin_broadcast = extend_schema(request=input_schema('BroadcastInput', title=serializers.CharField(max_length=120), message=serializers.CharField(max_length=2000), role=serializers.ChoiceField(choices=['all','client','vendor'])))(admin_broadcast)  # Décrire le ciblage des messages système.
VendorViewSet = extend_schema_view(retrieve=extend_schema(responses=VendorDetailSerializer), mine=extend_schema(responses=VendorDetailSerializer), status=extend_schema(request=input_schema('VendorStatusInput',status=serializers.ChoiceField(choices=['auto','open','closed'])),responses=VendorSerializer), quote=extend_schema(request=input_schema('QuoteInput',plan=serializers.ChoiceField(choices=list(PLANS))),responses=OpenApiTypes.OBJECT), subscriptions=extend_schema(request=input_schema('SubscriptionInput',plan=serializers.ChoiceField(choices=list(PLANS))),responses=OpenApiTypes.OBJECT), dashboard=extend_schema(responses=OpenApiTypes.OBJECT))(VendorViewSet)  # Décrire les réponses détaillées et les droits des actions pro.
ReviewViewSet = extend_schema_view(reply=extend_schema(request=input_schema('ReplyInput',reply=serializers.CharField(max_length=1500)),responses=ReviewSerializer))(ReviewViewSet)  # Décrire la réponse commerçante sans exposer une édition arbitraire de l'avis.
NotificationViewSet = extend_schema_view(read=extend_schema(request=None,responses=NotificationSerializer))(NotificationViewSet)  # Décrire le marquage lu sans corps obligatoire.
from .models import AlertZone, Promotion  # Charger le ciblage explicite des notifications locales.
from .serializers import AlertZoneSerializer  # Valider la zone et son consentement.
@extend_schema(request=AlertZoneSerializer,responses=AlertZoneSerializer)  # Documenter la seule conservation volontaire de position cliente.
@api_view(['GET','POST','DELETE'])  # Permettre lecture, activation et retrait immédiat du consentement.
def alerts(request):  # Gérer une zone d'alerte privée par compte client.
    if request.user.role != 'client':  # Réserver les alertes de découverte aux clients.
        raise PermissionDenied('Les alertes de proximité sont destinées aux clients.')  # Séparer recherche commerciale et zone personnelle.
    zone = AlertZone.objects.filter(user=request.user).first()  # Rechercher seulement la zone du compte connecté.
    if request.method == 'GET':  # Lire la préférence existante.
        return Response(AlertZoneSerializer(zone).data) if zone else JsonResponse(None,safe=False)  # Retourner un vrai JSON null, pas un corps HTTP vide, sans consentement.
    if request.method == 'DELETE':  # Retirer le consentement et la donnée en une seule opération.
        AlertZone.objects.filter(user=request.user).delete()  # Effacer les coordonnées privées conservées.
        return Response(status=204)  # Confirmer sans historique de position.
    data = AlertZoneSerializer(data=request.data)  # Vérifier les coordonnées, le rayon et l'accord distinct.
    data.is_valid(raise_exception=True)  # Refuser toute conservation involontaire.
    values = dict(data.validated_data); values.pop('consent')  # Retirer le champ virtuel de consentement.
    zone, _ = AlertZone.objects.update_or_create(user=request.user,defaults={**values,'consent_at':timezone.now()})  # Dater chaque nouvelle préférence explicite.
    return Response(AlertZoneSerializer(zone).data)  # Montrer la zone réellement enregistrée.
@extend_schema(request=input_schema('PromotionInput',message=serializers.CharField(max_length=500)),responses=OpenApiTypes.OBJECT)  # Documenter les campagnes comprises dans l'abonnement.
@api_view(['POST'])  # Déclencher une mise en avant à l'initiative du vendeur.
def promote(request,pk):  # Diffuser aux clients ayant volontairement conservé une zone proche.
    vendor = owned_vendor(request,pk)  # Vérifier le propriétaire avant tout ciblage.
    values = parse(request,message=serializers.CharField(max_length=500))  # Borner le message commercial.
    with transaction.atomic():  # Sérialiser les demandes pour contrôler le quota Croissance.
        Vendor.objects.select_for_update().get(pk=vendor.pk)  # Verrouiller les droits du commerce.
        plan = plan_key(vendor)  # Utiliser l'abonnement actif au moment de la campagne.
        if plan not in ['growth','performance'] or vendor.moderation != 'approved':  # Réserver la mise en avant aux commerces publiés de formule supérieure.
            raise ValidationError('Commerce validé et formule Croissance ou Performance requis.')  # Expliquer les droits nécessaires.
        now = timezone.now(); month = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)  # Définir le mois civil de référence UTC.
        if plan == 'growth' and vendor.promotions.filter(created_at__gte=month).exists():  # Appliquer la campagne mensuelle Croissance.
            raise ValidationError('La mise en avant Croissance de ce mois a déjà été utilisée.')  # Ne pas débiter un quota supplémentaire.
        campaign = Promotion.objects.create(vendor=vendor,message=values['message'])  # Tracer la demande indépendamment du nombre de clients proches.
        for zone in AlertZone.objects.filter(user__is_active=True).select_related('user'):  # Cibler seulement des zones volontairement activées.
            if distance_m(zone.latitude,zone.longitude,vendor.latitude,vendor.longitude) > zone.radius:  # Respecter le rayon choisi par le client.
                continue  # Écarter les destinataires hors zone.
            _, created = Notification.objects.get_or_create(dedupe_key=f'promo:{vendor.pk}:{zone.user_id}:{now:%Y%m%d}',defaults={'user':zone.user,'title':f'{vendor.name} · mise en avant','message':values['message']})  # Limiter chaque commerce à un message quotidien par client, même en Performance.
            campaign.recipients += int(created)  # Compter seulement les nouveaux messages réellement créés.
        campaign.save(update_fields=['recipients'])  # Persister le bilan de ciblage.
        audit(request.user,'vendor.promote',campaign.pk,recipients=campaign.recipients)  # Tracer les campagnes sans coordonnées clientes.
    return Response({'recipients':campaign.recipients,'message':'Campagne créée. Les destinataires sont limités à un message par commerce et par jour.'},status=201)  # Expliquer l'anti-spam indépendamment du quota mensuel.
