from django.contrib.auth.models import AbstractUser  # Réutiliser le hachage, les groupes et les permissions Django.
from django.db import models  # Déclarer les tables et contraintes relationnelles.
from django.core.validators import MinValueValidator, MaxValueValidator  # Encadrer coordonnées, prix et étoiles.
from django.core.exceptions import ValidationError  # Valider les règles croisées aussi dans les formulaires administratifs.
from django.db.models.functions import Lower  # Empêcher les doublons de comptes indépendamment de la casse.
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Valider les fuseaux horaires dans les outils administratifs.
from django.utils import timezone  # Produire des dates conscientes du fuseau.
class User(AbstractUser):  # Enrichir le compte standard sans réinventer l'authentification.
    role = models.CharField(max_length=10, choices=[('client', 'Client'), ('vendor', 'Vendeur'), ('admin', 'Administrateur')], default='client')  # Distinguer les parcours métier.
    phone = models.CharField(max_length=20, blank=True, unique=True, null=True)  # Accepter un téléphone unique normalisé à l'inscription.
    email = models.EmailField(unique=True)  # Empêcher les doublons d'adresse email.
    consent_at = models.DateTimeField(null=True, blank=True)  # Tracer l'acceptation des conditions.
    class Meta(AbstractUser.Meta):  # Ajouter des invariants de compte sans perdre les options standard Django.
        constraints = [models.UniqueConstraint(Lower('username'),name='unique_username_casefold'),models.UniqueConstraint(Lower('email'),name='unique_email_casefold')]  # Empêcher des identités ambiguës lors de créations concurrentes.
class Category(models.Model):  # Organiser les produits en catégories hiérarchiques.
    name = models.CharField(max_length=80, unique=True)  # Identifier une catégorie sans ambiguïté.
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)  # Conserver les enfants si leur parent est supprimé.
    def clean(self):  # Bloquer les cycles de catégorie aussi depuis le back-office.
        ancestor = self.parent  # Partir du parent proposé.
        seen = set()  # Détecter même une chaîne déjà corrompue.
        while ancestor:  # Remonter les parents sans boucle infinie.
            if ancestor.pk == self.pk or ancestor.pk in seen:  # Refuser un retour vers un ancêtre connu.
                raise ValidationError({'parent': 'La hiérarchie ne peut pas contenir de cycle.'})  # Expliquer le champ fautif.
            seen.add(ancestor.pk); ancestor = ancestor.parent  # Avancer dans la chaîne valide.
    def __str__(self):  # Présenter un nom lisible dans l'administration.
        return self.name  # Retourner le libellé métier.
class Vendor(models.Model):  # Représenter un commerce rattaché à son responsable.
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor')  # Limiter le MVP à un commerce par vendeur.
    name = models.CharField(max_length=120)  # Enregistrer le nom commercial.
    description = models.TextField(max_length=2000, blank=True)  # Décrire l'offre locale.
    phone = models.CharField(max_length=20)  # Permettre un contact direct.
    address = models.CharField(max_length=250, blank=True)  # Donner un repère au-delà du GPS.
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])  # Valider la latitude.
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])  # Valider la longitude.
    timezone = models.CharField(max_length=60, default='Africa/Lome')  # Interpréter les horaires dans le fuseau du commerce.
    moderation = models.CharField(max_length=10, choices=[('pending', 'À valider'), ('approved', 'Validé'), ('rejected', 'Rejeté')], default='pending', db_index=True)  # Masquer les commerces non validés.
    moderation_reason = models.TextField(blank=True, max_length=1000)  # Expliquer un rejet ou une décision.
    status_override = models.CharField(max_length=6, choices=[('auto', 'Horaires'), ('open', 'Ouvert'), ('closed', 'Fermé')], default='auto')  # Permettre une dérogation manuelle explicite.
    override_until = models.DateTimeField(null=True, blank=True)  # Expirer automatiquement les statuts manuels.
    photo = models.ImageField(upload_to='vendors/', blank=True)  # Conserver une photo réencodée du commerce.
    views = models.PositiveIntegerField(default=0)  # Compter les consultations publiques de fiches.
    created_at = models.DateTimeField(auto_now_add=True)  # Tracer l'enrôlement.
    def clean(self):  # Valider le fuseau aussi depuis une édition administrative.
        try:  # Tester le registre IANA.
            ZoneInfo(self.timezone)  # Vérifier le fuseau déclaré.
        except (ZoneInfoNotFoundError, ValueError):  # Adapter un identifiant absent.
            raise ValidationError({'timezone': 'Fuseau IANA inconnu.'})  # Garder la fiche exploitable par les horaires.
    def __str__(self):  # Faciliter la recherche humaine en administration.
        return self.name  # Afficher le commerce.
class Product(models.Model):  # Décrire une offre disponible dans un commerce.
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')  # Rattacher le produit au catalogue.
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')  # Empêcher de supprimer une catégorie utilisée.
    name = models.CharField(max_length=100)  # Stocker le libellé visible dans la recherche.
    description = models.TextField(blank=True, max_length=1000)  # Décrire ingrédients ou particularités.
    price = models.PositiveIntegerField(validators=[MaxValueValidator(10000000)])  # Représenter un prix entier en FCFA.
    available = models.BooleanField(default=True)  # Gérer la rupture sans détruire le produit.
    photo = models.ImageField(upload_to='products/', blank=True)  # Stocker uniquement une image vérifiée.
class OpeningHour(models.Model):  # Déclarer les plages récurrentes, y compris plusieurs par jour.
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='hours')  # Associer les horaires à leur commerce.
    weekday = models.PositiveSmallIntegerField(validators=[MaxValueValidator(6)])  # Numéroter lundi=0 à dimanche=6.
    start = models.TimeField()  # Définir l'heure locale d'ouverture.
    end = models.TimeField()  # Accepter une fermeture le lendemain si end < start.
    def clean(self):  # Protéger aussi une édition directe de planning.
        if self.start == self.end:  # Refuser une durée nulle.
            raise ValidationError('Les heures d’ouverture et de fermeture doivent être différentes.')  # Expliquer la plage invalide.
class OpeningException(models.Model):  # Remplacer les plages d'une journée exceptionnelle.
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='exceptions')  # Relier le jour spécial au commerce.
    date = models.DateField()  # Identifier la date locale concernée.
    closed = models.BooleanField(default=True)  # Fermer complètement ou utiliser les heures exceptionnelles.
    start = models.TimeField(null=True, blank=True)  # Définir l'ouverture exceptionnelle.
    end = models.TimeField(null=True, blank=True)  # Définir la fermeture exceptionnelle.
    def clean(self):  # Contrôler la plage exceptionnelle depuis l'administration.
        if not self.closed and (not self.start or not self.end or self.start >= self.end):  # Exiger une plage complète dans la même journée.
            raise ValidationError('Une journée exceptionnellement ouverte exige début < fin.')  # Éviter un calcul de disponibilité impossible.
    class Meta:  # Déclarer les invariants SQL.
        constraints = [models.UniqueConstraint(fields=['vendor', 'date'], name='one_exception_per_date')]  # Éviter deux décisions contradictoires le même jour.
class Review(models.Model):  # Recueillir un avis par client et commerce.
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')  # Identifier le déposant.
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='reviews')  # Relier l'avis au commerce.
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])  # Limiter la note à cinq étoiles.
    text = models.TextField(max_length=1500)  # Limiter la longueur du commentaire.
    reply = models.TextField(blank=True, max_length=1500)  # Conserver la réponse du commerçant.
    visible = models.BooleanField(default=True)  # Masquer un contenu modéré sans effacer l'historique.
    created_at = models.DateTimeField(auto_now_add=True)  # Dater l'expérience déclarée.
    class Meta:  # Garantir les règles même lors d'écritures concurrentes.
        constraints = [models.UniqueConstraint(fields=['author', 'vendor'], name='one_review_per_vendor'), models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='rating_between_one_and_five')]  # Interdire doublons et notes hors plage.
class Favorite(models.Model):  # Enregistrer les commerces préférés des clients.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')  # Protéger la liste personnelle par son propriétaire.
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)  # Pointer le commerce préféré.
    class Meta:  # Empêcher les doublons.
        constraints = [models.UniqueConstraint(fields=['user', 'vendor'], name='one_favorite_per_vendor')]  # Rendre l'ajout idempotent.
class Notification(models.Model):  # Fournir une boîte de réception persistante indépendamment du push.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')  # Cibler le destinataire.
    title = models.CharField(max_length=120)  # Résumer le message.
    message = models.TextField(max_length=2000)  # Conserver son contenu.
    read = models.BooleanField(default=False)  # Suivre la lecture.
    dedupe_key = models.CharField(max_length=160, null=True, blank=True, unique=True)  # Éviter les rappels répétés par le cron.
    created_at = models.DateTimeField(auto_now_add=True)  # Ordonner les notifications.
class Report(models.Model):  # Centraliser les signalements de commerces et d'avis.
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # Identifier le déclarant sans le rendre public.
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.CASCADE)  # Désigner un faux commerce éventuel.
    review = models.ForeignKey(Review, null=True, blank=True, on_delete=models.CASCADE)  # Désigner un avis problématique éventuel.
    reason = models.TextField(max_length=1000)  # Décrire le problème.
    resolved = models.BooleanField(default=False)  # Suivre le traitement.
    resolution = models.TextField(max_length=1000, blank=True)  # Expliquer la décision administrative.
    created_at = models.DateTimeField(auto_now_add=True)  # Dater le signalement.
    class Meta:  # Valider les cibles en base.
        constraints = [models.CheckConstraint(condition=(models.Q(vendor__isnull=False, review__isnull=True) | models.Q(vendor__isnull=True, review__isnull=False)), name='report_exactly_one_target')]  # Exiger une et une seule cible.
class Subscription(models.Model):  # Garder l'historique des droits acquis par un commerce.
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='subscriptions')  # Rattacher l'abonnement au commerce.
    plan = models.CharField(max_length=12)  # Stocker une clé de formule contrôlée par le service métier.
    start = models.DateTimeField(default=timezone.now)  # Dater l'activation réelle.
    end = models.DateTimeField(db_index=True)  # Déterminer les droits sans attendre le cron.
    amount = models.PositiveIntegerField(default=0)  # Stocker le montant réglé après prorata.
    reminder7 = models.BooleanField(default=False)  # Éviter un deuxième rappel à J-7.
    reminder1 = models.BooleanField(default=False)  # Éviter un deuxième rappel à J-1.
    expired_notified = models.BooleanField(default=False)  # Tracer la notification de rétrogradation.
class Payment(models.Model):  # Représenter une demande de paiement sans accorder de droits avant vérification.
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='payments')  # Attribuer le paiement au bon commerce.
    plan = models.CharField(max_length=12)  # Mémoriser la formule demandée.
    amount = models.PositiveIntegerField()  # Figer le montant serveur au moment de la demande.
    reference = models.CharField(max_length=64, unique=True)  # Identifier la transaction auprès de l'opérateur.
    external_reference = models.CharField(max_length=120, blank=True)  # Conserver la référence du reçu vérifié.
    status = models.CharField(max_length=10, choices=[('pending', 'En attente'), ('paid', 'Confirmé'), ('rejected', 'Rejeté')], default='pending')  # Rendre l'état explicite.
    base_subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL, related_name='quotes')  # Figer les droits servant au calcul du crédit.
    subscription = models.OneToOneField(Subscription, null=True, blank=True, on_delete=models.SET_NULL)  # Empêcher deux activations pour un paiement.
    created_at = models.DateTimeField(auto_now_add=True)  # Tracer la demande.
    class Meta:  # Empêcher de réutiliser un même reçu pour plusieurs abonnements.
        constraints = [models.UniqueConstraint(fields=['external_reference'],condition=models.Q(status='paid'),name='unique_confirmed_external_receipt')]  # Garantir l'unicité même entre confirmations concurrentes.
class Audit(models.Model):  # Conserver les actions sensibles pour l'exploitation.
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)  # Préserver le journal si un opérateur disparaît.
    action = models.CharField(max_length=100)  # Nommer l'opération.
    target = models.CharField(max_length=120)  # Identifier l'objet concerné.
    detail = models.JSONField(default=dict)  # Garder seulement des métadonnées non secrètes.
    created_at = models.DateTimeField(auto_now_add=True)  # Dater l'opération.
class SearchEvent(models.Model):  # Mesurer les recherches sans enregistrer la position du client.
    keyword = models.CharField(max_length=100, db_index=True)  # Conserver uniquement le terme recherché.
    vendor_ids = models.JSONField(default=list)  # Mesurer les commerces présentés.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # Permettre une purge de rétention.
class Configuration(models.Model):  # Centraliser les paramètres administratifs validés.
    key = models.CharField(max_length=80, unique=True)  # Identifier un paramètre métier.
    value = models.JSONField()  # Conserver rayons, versions et autres valeurs structurées.
class Device(models.Model):  # Enregistrer les terminaux consentant aux notifications distantes.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')  # Relier le terminal à son propriétaire.
    token = models.CharField(max_length=300, unique=True)  # Éviter une double diffusion au même terminal.
    platform = models.CharField(max_length=10, choices=[('android', 'Android'), ('ios', 'iOS')])  # Sélectionner le transport futur.
class SocialIdentity(models.Model):  # Associer une identité externe vérifiée à un compte interne.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_identities')  # Rattacher le fournisseur au propriétaire réel.
    subject = models.CharField(max_length=255, unique=True)  # Utiliser le sub immuable Google plutôt que l'email comme identité.
    created_at = models.DateTimeField(auto_now_add=True)  # Tracer la liaison initiale.
class PushDelivery(models.Model):  # Suivre les envois push sans les confondre avec la lecture du message.
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)  # Désigner le message interne d'origine.
    device = models.ForeignKey(Device, on_delete=models.CASCADE)  # Cibler un terminal autorisé.
    attempts = models.PositiveSmallIntegerField(default=0)  # Borner les reprises après une panne fournisseur.
    ticket = models.CharField(max_length=120, blank=True)  # Conserver le ticket de prise en charge Expo.
    status = models.CharField(max_length=12, default='pending')  # Distinguer attente, ticket accepté, reçu et échec.
    next_attempt = models.DateTimeField(default=timezone.now)  # Planifier un délai exponentiel entre reprises.
    error = models.CharField(max_length=100, blank=True)  # Conserver un code technique sans texte privé.
    class Meta:  # Garantir l'unicité d'un envoi par message et terminal.
        constraints = [models.UniqueConstraint(fields=['notification', 'device'], name='unique_push_delivery')]  # Éviter une double création de tâche.
class AlertZone(models.Model):  # Enregistrer une zone uniquement après un consentement spécifique aux alertes de proximité.
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='alert_zone')  # Conserver une zone privée par compte client.
    latitude = models.FloatField(validators=[MinValueValidator(-90),MaxValueValidator(90)])  # Vérifier le centre de la zone consentie.
    longitude = models.FloatField(validators=[MinValueValidator(-180),MaxValueValidator(180)])  # Vérifier sa longitude.
    radius = models.PositiveIntegerField(default=2000,validators=[MinValueValidator(100),MaxValueValidator(20000)])  # Limiter le voisinage surveillé à vingt kilomètres.
    consent_at = models.DateTimeField(default=timezone.now)  # Dater l'activation volontaire et permettre son retrait.
class Promotion(models.Model):  # Tracer les mises en avant incluses dans les formules supérieures.
    vendor = models.ForeignKey(Vendor,on_delete=models.CASCADE,related_name='promotions')  # Identifier le commerçant bénéficiaire.
    message = models.TextField(max_length=500)  # Limiter le contenu diffusé aux clients consentants.
    recipients = models.PositiveIntegerField(default=0)  # Mesurer les messages effectivement créés.
    created_at = models.DateTimeField(auto_now_add=True)  # Contrôler le quota mensuel Croissance.
