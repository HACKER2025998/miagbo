import math  # Rejeter NaN et les infinis avant tout stockage de coordonnées.
import re  # Normaliser et vérifier les numéros téléphoniques.
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Valider le fuseau d'un commerce.
from django.contrib.auth.password_validation import validate_password  # Appliquer la politique de mots de passe.
from django.core.exceptions import ValidationError as DjangoValidationError  # Convertir les erreurs de validation Django.
from rest_framework import serializers  # Déclarer les entrées et sorties de l'API.
from .models import User, Vendor, Product, Category, OpeningHour, OpeningException, Review, Report, Notification, Payment, Device  # Charger les entités exposées.
from .services import is_open, rating, plan_key, safe_image, visible_products  # Réutiliser les règles métier communes.
class FiniteFloatField(serializers.FloatField):  # Compléter les bornes numériques par une vérification de finitude.
    def to_internal_value(self, data):  # Contrôler même une chaîne comme NaN que float() accepterait.
        value = super().to_internal_value(data)  # Appliquer les conversions et erreurs de type DRF.
        if not math.isfinite(value):  # Refuser un nombre sans position géographique réelle.
            raise serializers.ValidationError('Une coordonnée finie est requise.')  # Produire un refus 400, jamais une erreur PostGIS.
        return value  # Fournir une coordonnée exploitable aux validateurs de bornes.
class UserSerializer(serializers.ModelSerializer):  # Exposer seulement les données du compte utiles au propriétaire.
    def validate_email(self, value):  # Garder une unicité indépendante de la casse lors d'une mise à jour.
        value = value.strip().lower()  # Uniformiser la clé de connexion email.
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():  # Exclure le compte modifié de la recherche de doublon.
            raise serializers.ValidationError('Adresse déjà utilisée.')  # Éviter une ambiguïté de connexion.
        return value  # Conserver l'adresse normalisée.
    def validate_phone(self, value):  # Garder le téléphone unique après normalisation du profil.
        value = re.sub(r'[\s()-]', '', value or '')  # Retirer la ponctuation de présentation.
        if value and not re.fullmatch(r'\+[1-9]\d{7,14}', value):  # Exiger le format international.
            raise serializers.ValidationError('Format international attendu, par exemple +22890000000.')  # Préciser la saisie attendue.
        if value and User.objects.filter(phone=value).exclude(pk=self.instance.pk).exists():  # Vérifier l'unicité après normalisation.
            raise serializers.ValidationError('Numéro déjà utilisé.')  # Refuser le doublon.
        return value or None  # Ne pas utiliser une chaîne vide unique.
    class Meta:  # Choisir explicitement les champs publics.
        model = User  # Sérialiser l'utilisateur MIAGBO.
        fields = ['id', 'username', 'first_name', 'email', 'phone', 'role', 'is_staff']  # Ne jamais exposer hash ou permissions internes.
        read_only_fields = ['id', 'role', 'is_staff', 'username']  # Empêcher une auto-promotion administrative.
class RegisterSerializer(serializers.ModelSerializer):  # Contrôler l'inscription publique.
    role = serializers.ChoiceField(choices=[('client','Client'),('vendor','Vendeur')], default='client')  # Annoncer dans OpenAPI seulement les deux rôles réellement autorisés à l'inscription.
    password = serializers.CharField(write_only=True, min_length=10)  # Ne jamais renvoyer le mot de passe.
    consent = serializers.BooleanField(write_only=True)  # Exiger l'acceptation informée.
    class Meta:  # Configurer le schéma d'inscription.
        model = User  # Créer des utilisateurs MIAGBO.
        fields = ['username', 'first_name', 'email', 'phone', 'role', 'password', 'consent']  # Limiter les champs acceptés.
    def validate_username(self, value):  # Empêcher des collisions entre identifiant, téléphone et email.
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', value) or User.objects.filter(username__iexact=value).exists():  # Exiger un identifiant simple et unique sans casse.
            raise serializers.ValidationError('Identifiant déjà utilisé ou invalide ; utilisez lettres, chiffres, point, tiret ou underscore.')  # Donner les caractères autorisés.
        return value  # Retourner une clé de connexion non ambiguë.
    def validate_role(self, value):  # Bloquer la création d'un administrateur public.
        if value not in ['client', 'vendor']:  # Autoriser uniquement les rôles grand public.
            raise serializers.ValidationError('Rôle client ou vendeur requis.')  # Refuser toute élévation.
        return value  # Conserver le rôle validé.
    def validate_consent(self, value):  # Vérifier un consentement explicite.
        if not value:  # Refuser les inscriptions sans acceptation.
            raise serializers.ValidationError('Acceptez les conditions et la politique de confidentialité.')  # Indiquer l'action requise.
        return value  # Conserver la preuve d'acceptation.
    def validate_phone(self, value):  # Normaliser le contact saisi.
        value = re.sub(r'[\s()-]', '', value or '')  # Retirer la ponctuation de présentation.
        if value and not re.fullmatch(r'\+[1-9]\d{7,14}', value):  # Exiger le format international E.164.
            raise serializers.ValidationError('Format international attendu, par exemple +22890000000.')  # Guider la saisie.
        if value and User.objects.filter(phone=value).exists():  # Contrôler l'unicité après normalisation.
            raise serializers.ValidationError('Numéro déjà utilisé.')  # Éviter les doublons.
        return value or None  # Stocker NULL pour un téléphone absent.
    def validate_email(self, value):  # Éviter les variantes de casse d'un même compte.
        value = value.strip().lower()  # Uniformiser les emails.
        if User.objects.filter(email__iexact=value).exists():  # Vérifier l'unicité insensible à la casse.
            raise serializers.ValidationError('Adresse déjà utilisée.')  # Refuser le doublon.
        return value  # Retourner la valeur normalisée.
    def validate(self, attrs):  # Valider la robustesse du mot de passe avec le profil.
        try:  # Adapter les erreurs de la politique Django.
            validate_password(attrs['password'], User(username=attrs['username'], email=attrs['email']))  # Refuser les mots de passe trop proches du compte.
        except DjangoValidationError as exc:  # Convertir les messages en erreurs de formulaire.
            raise serializers.ValidationError({'password': exc.messages})  # Indiquer tous les défauts détectés.
        return attrs  # Retourner l'inscription validée.
class CategorySerializer(serializers.ModelSerializer):  # Fournir les catégories et leur hiérarchie.
    class Meta:  # Définir la représentation.
        model = Category  # Sérialiser une catégorie.
        fields = ['id', 'name', 'parent']  # Exposer les identifiants nécessaires au catalogue.
    def validate_parent(self, value):  # Empêcher les cycles hiérarchiques.
        ancestor = value  # Partir du parent proposé.
        while ancestor:  # Parcourir la chaîne existante.
            if self.instance and ancestor.pk == self.instance.pk:  # Détecter une boucle vers la catégorie modifiée.
                raise serializers.ValidationError('Une catégorie ne peut pas être son propre ancêtre.')  # Refuser le cycle.
            ancestor = ancestor.parent  # Remonter d'un niveau.
        return value  # Conserver le parent sûr.
class ProductSerializer(serializers.ModelSerializer):  # Exposer le catalogue et contrôler ses médias.
    category_name = serializers.CharField(source='category.name', read_only=True)  # Donner un libellé utile sans requête frontend supplémentaire.
    class Meta:  # Sélectionner les propriétés métier.
        model = Product  # Sérialiser les produits.
        fields = ['id', 'vendor', 'name', 'description', 'price', 'category', 'category_name', 'available', 'photo']  # Inclure la disponibilité et l'image.
        read_only_fields = ['vendor']  # Fixer le commerce côté serveur.
    def validate_photo(self, value):  # Assainir chaque upload.
        return safe_image(value) if value else value  # Réencoder le média reçu.
class HourSerializer(serializers.ModelSerializer):  # Valider les plages récurrentes.
    class Meta:  # Définir les colonnes exposées.
        model = OpeningHour  # Utiliser une plage d'ouverture.
        fields = ['id', 'weekday', 'start', 'end']  # Garder le commerce implicite.
    def validate(self, attrs):  # Rejeter une plage ambiguë de durée nulle.
        if attrs.get('start') == attrs.get('end'):  # Identifier deux heures identiques.
            raise serializers.ValidationError('Les heures doivent être différentes ; scindez une ouverture de 24 h en deux plages.')  # Préciser comment exprimer le besoin.
        return attrs  # Accepter aussi une plage nocturne.
class ExceptionSerializer(serializers.ModelSerializer):  # Valider les fermetures exceptionnelles.
    class Meta:  # Définir le format des exceptions.
        model = OpeningException  # Cibler la date exceptionnelle.
        fields = ['id', 'date', 'closed', 'start', 'end']  # Garder le vendeur côté serveur.
    def validate(self, attrs):  # Exiger des heures cohérentes pour une journée ouverte.
        if not attrs.get('closed', True) and (not attrs.get('start') or not attrs.get('end') or attrs['start'] >= attrs['end']):  # Refuser les exceptions incomplètes ou traversant minuit.
            raise serializers.ValidationError('Une exception ouverte doit avoir début < fin, dans la même journée.')  # Expliquer la restriction.
        return attrs  # Retourner la décision valide.
class ReviewSerializer(serializers.ModelSerializer):  # Afficher les avis sans révéler les contacts des auteurs.
    author_name = serializers.CharField(source='author.first_name', read_only=True)  # Utiliser seulement le prénom public.
    class Meta:  # Définir la fiche d'avis.
        model = Review  # Cibler les évaluations.
        fields = ['id', 'vendor', 'author_name', 'rating', 'text', 'reply', 'created_at']  # Exposer avis et réponse.
        read_only_fields = ['reply', 'created_at']  # Réserver la réponse au propriétaire via une route dédiée.
class VendorSerializer(serializers.ModelSerializer):  # Présenter une fiche commerce avec droits et disponibilité calculés.
    latitude = FiniteFloatField(min_value=-90,max_value=90)  # Valider les latitudes finies dans le domaine terrestre.
    longitude = FiniteFloatField(min_value=-180,max_value=180)  # Valider les longitudes finies dans le domaine terrestre.
    is_open = serializers.SerializerMethodField()  # Calculer le statut actuel.
    rating = serializers.SerializerMethodField()  # Agréger seulement les avis visibles.
    plan = serializers.SerializerMethodField()  # Afficher la formule réellement active.
    distance = serializers.SerializerMethodField()  # Exposer la distance lorsqu'une recherche l'a calculée.
    class Meta:  # Définir les champs des commerces.
        model = Vendor  # Sérialiser les points de vente.
        fields = ['id', 'name', 'description', 'phone', 'address', 'latitude', 'longitude', 'timezone', 'photo', 'moderation', 'moderation_reason', 'status_override', 'override_until', 'is_open', 'rating', 'plan', 'distance', 'views']  # Préparer client et espace pro.
        read_only_fields = ['moderation', 'moderation_reason', 'views', 'status_override', 'override_until']  # Empêcher la validation ou les compteurs auto-attribués.
    def get_is_open(self, obj) -> bool:  # Évaluer les horaires avec les dérogations.
        return is_open(obj)  # Réutiliser le service testé.
    def get_rating(self, obj) -> float:  # Produire la moyenne publique.
        return rating(obj)  # Utiliser les avis encore visibles.
    def get_plan(self, obj) -> str:  # Calculer les droits à cet instant.
        return plan_key(obj)  # Appliquer le repli après expiration.
    def get_distance(self, obj) -> int | None:  # Gérer aussi les fiches hors recherche.
        return round(obj.distance) if hasattr(obj, 'distance') else None  # Fournir des mètres arrondis ou aucune distance.
    def validate_timezone(self, value):  # Empêcher un fuseau invalide de casser le calcul horaire.
        try:  # Tester la base des fuseaux IANA.
            ZoneInfo(value)  # Vérifier que le fuseau existe.
        except (ZoneInfoNotFoundError, ValueError):  # Adapter les fuseaux inconnus.
            raise serializers.ValidationError('Fuseau IANA inconnu.')  # Produire un message utilisateur.
        return value  # Conserver un fuseau valide.
    def validate_photo(self, value):  # Vérifier la couverture du commerce.
        return safe_image(value) if value else value  # Réencoder le fichier reçu.
class VendorDetailSerializer(VendorSerializer):  # Ajouter les données complètes à la fiche.
    products = serializers.SerializerMethodField()  # Filtrer le catalogue selon les droits.
    reviews = serializers.SerializerMethodField()  # Masquer les avis retirés.
    hours = HourSerializer(many=True, read_only=True)  # Afficher les plages récurrentes.
    exceptions = ExceptionSerializer(many=True, read_only=True)  # Afficher les jours spéciaux.
    class Meta(VendorSerializer.Meta):  # Étendre les champs communs.
        fields = VendorSerializer.Meta.fields + ['products', 'reviews', 'hours', 'exceptions']  # Ajouter les collections de la fiche.
    def get_products(self, obj) -> list[dict]:  # Appliquer le quota et les disponibilités.
        return ProductSerializer(visible_products(obj), many=True, context=self.context).data  # Construire les URL absolues des médias.
    def get_reviews(self, obj) -> list[dict]:  # Limiter une fiche trop volumineuse.
        return ReviewSerializer(obj.reviews.filter(visible=True).select_related('author').order_by('-created_at')[:50], many=True).data  # Afficher les cinquante derniers avis.
class NotificationSerializer(serializers.ModelSerializer):  # Fournir la boîte de réception personnelle.
    class Meta:  # Limiter les changements du destinataire.
        model = Notification  # Cibler les notifications.
        fields = ['id', 'title', 'message', 'read', 'created_at']  # Inclure l'état de lecture.
        read_only_fields = ['title', 'message', 'created_at']  # Autoriser uniquement le marquage lu.
class PaymentSerializer(serializers.ModelSerializer):  # Exposer le suivi financier au propriétaire.
    class Meta:  # Prévenir la modification des montants ou statuts.
        model = Payment  # Cibler les demandes de paiement.
        fields = ['id', 'plan', 'amount', 'reference', 'external_reference', 'status', 'created_at']  # Fournir un historique traçable.
        read_only_fields = fields  # Fixer toutes les valeurs côté serveur.
class ReportSerializer(serializers.ModelSerializer):  # Contrôler les signalements publics.
    class Meta:  # Choisir les champs acceptés.
        model = Report  # Enregistrer une alerte.
        fields = ['id', 'vendor', 'review', 'reason', 'resolved', 'resolution']  # Garder le déclarant implicite.
        read_only_fields = ['resolved', 'resolution']  # Réserver les décisions au back-office.
    def validate(self, attrs):  # Exiger une cible unique avant la contrainte SQL.
        if bool(attrs.get('vendor')) == bool(attrs.get('review')):  # Détecter zéro ou deux cibles.
            raise serializers.ValidationError('Indiquez un commerce ou un avis, une seule cible.')  # Expliquer le format.
        return attrs  # Conserver le signalement valide.
class DeviceSerializer(serializers.ModelSerializer):  # Collecter les tokens mobiles avec consentement natif.
    token = serializers.RegexField(r'^(ExpoPushToken|ExponentPushToken)\[[A-Za-z0-9_-]+\]$', max_length=300)  # Accepter seulement des tokens Expo et permettre leur réattribution idempotente.
    class Meta:  # Définir le schéma du terminal.
        model = Device  # Enregistrer un terminal.
        fields = ['token', 'platform']  # Ne jamais accepter un utilisateur arbitraire.
from .models import AlertZone  # Décrire les préférences de proximité consenties.
class AlertZoneSerializer(serializers.ModelSerializer):  # Valider une zone privée sans demander un suivi permanent du GPS.
    latitude = FiniteFloatField(min_value=-90,max_value=90)  # Refuser une zone centrée sur NaN ou un infini.
    longitude = FiniteFloatField(min_value=-180,max_value=180)  # Encadrer la seconde coordonnée privée.
    consent = serializers.BooleanField(write_only=True)  # Exiger un accord distinct de celui du compte.
    class Meta:  # Définir le contrat d'activation des alertes.
        model = AlertZone  # Rattacher les données à la zone du compte.
        fields = ['latitude','longitude','radius','consent','consent_at']  # Exposer uniquement la zone de son propriétaire.
        read_only_fields = ['consent_at']  # Dater l'accord côté serveur.
    def validate_consent(self,value):  # Refuser de conserver une zone sans accord explicite.
        if not value:  # Détecter un refus.
            raise serializers.ValidationError('Consentement spécifique requis pour conserver cette zone.')  # Expliquer la donnée supplémentaire.
        return value  # Accepter l'activation volontaire.
