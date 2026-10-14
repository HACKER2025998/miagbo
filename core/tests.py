import hashlib  # Signer les événements de paiement des tests.
import hmac  # Construire des signatures conformes au contrat d'adaptateur.
import json  # Encoder exactement les octets signés.
import time  # Tester la fenêtre de rejeu des webhooks.
from datetime import datetime, timedelta, time as civil_time  # Créer des scénarios horaires déterministes.
from io import BytesIO, StringIO  # Préparer des images et capturer les commandes sans fichier temporaire.
from unittest.mock import patch, MagicMock  # Simuler les fournisseurs externes sans envoyer de mail ni de push réel.
from zoneinfo import ZoneInfo  # Construire des instants locaux conscients de leur fuseau.
from PIL import Image  # Générer des images valides pour les tests d'upload.
from django.core.cache import cache  # Isoler les limites de débit entre les scénarios de test.
from django.conf import settings  # Lire le secret de test du webhook.
from django.contrib.auth.tokens import default_token_generator  # Produire de vrais liens de récupération pour les tests.
from django.contrib.auth.models import Permission  # Vérifier les permissions administratives fines.
from django.core.files.uploadedfile import SimpleUploadedFile  # Envoyer un fichier multipart réaliste.
from django.core.management import call_command  # Tester migrations et tâches planifiées par leur interface réelle.
from django.db import IntegrityError, transaction  # Vérifier les contraintes SQL indépendamment de l'API.
from django.test import TestCase, override_settings  # Isoler base et configuration pour chaque scénario.
from django.utils import timezone  # Calculer les échéances de test en UTC.
from django.utils.http import urlsafe_base64_encode  # Encoder les identifiants de récupération.
from django.utils.encoding import force_bytes  # Construire le lien de récupération officiel.
from rest_framework.test import APIClient  # Effectuer de vrais appels API avec authentification et CSRF.
from rest_framework.exceptions import ValidationError  # Tester les refus métier explicites.
from rest_framework_simplejwt.tokens import RefreshToken  # Vérifier les suspensions avec des JWT réellement signés.
from .models import User, Vendor, Product, Category, OpeningHour, OpeningException, Review, Report, Favorite, Subscription, Payment, Notification, Device, Audit, SearchEvent, PushDelivery  # Observer les effets persistants des parcours.
from .services import is_open, add_months, distance_m, visible_products, plan_key, quote, confirm_payment, safe_image  # Tester les règles sensibles indépendamment des écrans.
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', MEDIA_ROOT='/tmp/miagbo-test-media')  # Éviter tout réseau SMTP et tout média dans le dépôt.
class MiagboTests(TestCase):  # Couvrir métier, sécurité et intégration HTTP avec une base isolée.
    def setUp(self):  # Construire les acteurs minimaux de chaque test.
        cache.clear()  # Ne pas hériter des tentatives de connexion d'un test précédent.
        self.client = APIClient()  # Partir d'une session anonyme.
        self.customer = User.objects.create_user(username='client',email='client@test.local',password='ClientTest2026!',role='client',first_name='Afi')  # Créer un vrai hash utilisateur.
        self.owner = User.objects.create_user(username='vendeur',email='vendeur@test.local',password='VendorTest2026!',role='vendor')  # Préparer un responsable commercial.
        self.other = User.objects.create_user(username='autre',email='autre@test.local',password='OtherTest2026!',role='vendor')  # Préparer une cible d'attaque entre vendeurs.
        self.admin = User.objects.create_superuser(username='admin',email='admin@test.local',password='AdminTest2026!',role='admin')  # Préparer un opérateur habilité.
        self.vendor = Vendor.objects.create(owner=self.owner,name='Chez Afi',description='Recettes locales',phone='+22890000000',latitude=6.13,longitude=1.22,moderation='approved')  # Publier un commerce de référence.
        self.category = Category.objects.create(name='Repas')  # Fournir une catégorie valide.
        self.product = Product.objects.create(vendor=self.vendor,category=self.category,name='Ayimolou',price=700)  # Alimenter la recherche par produit.
        self.sub = Subscription.objects.create(vendor=self.vendor,plan='discovery',end=add_months(timezone.now(),1))  # Fournir les droits initiaux.
    def auth(self, user):  # Choisir l'acteur d'un appel API sans modifier les comptes.
        self.client.force_authenticate(user=user)  # Isoler les permissions de la vérification des mots de passe testée ailleurs.
    def search(self, **params):  # Construire une recherche géographique locale valide.
        return self.client.get('/api/v1/vendors/search/',{'lat':6.13,'lng':1.22,'radius':2000,**params})  # Permettre de remplacer un paramètre pour les cas négatifs.
    def payment(self, plan='essential'):  # Créer un devis financier réellement calculé côté serveur.
        return Payment.objects.create(vendor=self.vendor,base_subscription=self.sub,plan=plan,amount=quote(self.vendor,plan)['amount'],reference='TEST-' + str(Payment.objects.count()))  # Figer montant et droits de référence.
    def test_health(self):  # Vérifier la connexion SQL via la sonde publique.
        self.assertEqual(self.client.get('/api/v1/health/').json(),{'status':'ok'})  # Exiger le contrat minimal de supervision.
    def test_public_categories_and_plans(self):  # Vérifier les tarifs contractuels sans authentification.
        self.assertEqual(self.client.get('/api/v1/categories/').status_code,200)  # Autoriser la découverte de catégories.
        self.assertEqual([p['price'] for p in self.client.get('/api/v1/subscriptions/plans/').json()],[0,1500,3000,5000])  # Empêcher une dérive de la grille FCFA.
    def test_search_product(self):  # Vérifier le cas d'usage central par nom de repas.
        result = self.search(q='ayimolou')  # Utiliser une casse différente du catalogue.
        self.assertEqual(result.status_code,200); self.assertEqual(result.json()['count'],1)  # Retrouver le commerce correspondant.
        self.assertEqual(result.json()['results'][0]['distance'],0)  # Exprimer l'origine identique comme zéro mètre.
    def test_search_unknown_keyword(self):  # Vérifier un état vide réel.
        self.assertEqual(self.search(q='inexistant').json()['count'],0)  # Ne pas renvoyer une adresse sans offre correspondante.
    def test_search_radius_excludes_far_vendor(self):  # Vérifier la borne géographique exacte.
        self.vendor.latitude = 7; self.vendor.save()  # Déplacer le commerce loin de l'origine.
        self.assertEqual(self.search().json()['count'],0)  # Exclure les résultats hors rayon.
    def test_search_invalid_coordinates(self):  # Refuser NaN, inf et valeurs hors domaine.
        for value in ['nan','inf',91,'abc']:  # Couvrir plusieurs conversions malveillantes.
            self.assertEqual(self.search(lat=value).status_code,400)  # Ne pas produire d'erreur serveur ni une recherche globale.
    def test_search_invalid_radius(self):  # Refuser des recherches abusivement larges.
        for value in [0,99,20001,'abc']:  # Couvrir borne basse, haute et type incorrect.
            self.assertEqual(self.search(radius=value).status_code,400)  # Exiger une entrée contrôlée.
    def test_search_requires_origin(self):  # Ne pas deviner une position côté serveur.
        self.assertEqual(self.client.get('/api/v1/vendors/search/').status_code,400)  # Exiger la latitude et la longitude.
    def test_search_category(self):  # Respecter un filtre de catégorie.
        self.assertEqual(self.search(category=self.category.pk).json()['count'],1)  # Retrouver un catalogue correspondant.
        self.assertEqual(self.search(category=999).json()['count'],0)  # Exclure une catégorie absente.
        self.assertEqual(self.search(category='nan').status_code,400)  # Contrôler le type du filtre.
    def test_pending_vendor_hidden(self):  # Empêcher une publication avant validation.
        self.vendor.moderation = 'pending'; self.vendor.save()  # Simuler un nouvel enrôlement.
        self.assertEqual(self.search().json()['count'],0)  # Masquer le commerce dans les résultats.
        self.assertEqual(self.client.get(f'/api/v1/vendors/{self.vendor.pk}/').status_code,404)  # Masquer aussi l'accès direct à la fiche.
    def test_suspended_vendor_hidden(self):  # Retirer les offres d'un compte suspendu immédiatement.
        self.owner.is_active = False; self.owner.save()  # Suspendre le vendeur.
        self.assertEqual(self.search().json()['count'],0)  # Ne pas attendre un job pour masquer son commerce.
    def test_unavailable_product_not_searchable(self):  # Respecter la disponibilité des produits.
        self.product.available = False; self.product.save()  # Mettre le repas en rupture.
        self.assertEqual(self.search(q='ayimolou').json()['count'],0)  # Ne pas attirer un client pour une offre absente.
    def test_hidden_overquota_product_not_searchable(self):  # Éviter de retrouver des produits masqués après expiration.
        for index in range(9): Product.objects.create(vendor=self.vendor,category=self.category,name=f'Produit {index}',price=100)  # Remplir les dix places visibles.
        Product.objects.create(vendor=self.vendor,category=self.category,name='Secret-delà-quota',price=100)  # Conserver un onzième produit dans la base.
        self.assertEqual(self.search(q='Secret-delà-quota').json()['count'],0)  # Appliquer le quota aussi au moteur de recherche.
    def test_search_does_not_store_client_coordinates(self):  # Vérifier la minimisation de géolocalisation.
        self.search(q='repas')  # Produire un événement de tendance.
        event = SearchEvent.objects.get()  # Observer la donnée réellement enregistrée.
        self.assertEqual(event.keyword,'repas'); self.assertFalse(hasattr(event,'latitude'))  # Garder le terme sans position personnelle.
    def test_detail_increments_views(self):  # Vérifier la métrique de consultation réelle.
        self.client.get(f'/api/v1/vendors/{self.vendor.pk}/')  # Ouvrir la fiche publique.
        self.vendor.refresh_from_db(); self.assertEqual(self.vendor.views,1)  # Compter une consultation sans écraser la valeur.
    def test_registration_hashes_password(self):  # Vérifier un parcours d'inscription complet.
        result = self.client.post('/api/v1/auth/register/',{'username':'nouveau','first_name':'Ama','email':'NEW@Test.local','password':'SecureTrial2026!','role':'client','consent':True},format='json')  # Soumettre un profil valide.
        self.assertEqual(result.status_code,201)  # Confirmer la création.
        user = User.objects.get(username='nouveau'); self.assertTrue(user.check_password('SecureTrial2026!')); self.assertNotEqual(user.password,'SecureTrial2026!')  # Vérifier que le secret n'est pas stocké en clair.
        self.assertEqual(user.email,'new@test.local'); self.assertIsNotNone(user.consent_at)  # Normaliser l'email et tracer l'accord.
    def test_registration_admin_forbidden(self):  # Bloquer une élévation de privilèges publique.
        result = self.client.post('/api/v1/auth/register/',{'username':'pirate','email':'p@test.local','password':'SecureTrial2026!','role':'admin','consent':True},format='json')  # Demander un rôle interne.
        self.assertEqual(result.status_code,400)  # Refuser avant toute création de compte.
    def test_registration_consent_required(self):  # Exiger un accord explicite aux conditions.
        result = self.client.post('/api/v1/auth/register/',{'username':'sans-consentement','email':'n@test.local','password':'SecureTrial2026!','role':'client','consent':False},format='json')  # Refuser le consentement.
        self.assertEqual(result.status_code,400)  # Ne pas créer silencieusement un compte.
    def test_weak_password_forbidden(self):  # Vérifier la politique de mots de passe réels.
        result = self.client.post('/api/v1/auth/register/',{'username':'faible','email':'f@test.local','password':'1234567890','role':'client','consent':True},format='json')  # Utiliser une suite numérique faible.
        self.assertEqual(result.status_code,400)  # Appliquer les validateurs standard.
    def test_login_email_and_phone(self):  # Vérifier les deux modes de connexion demandés.
        self.customer.phone = '+22891111111'; self.customer.save()  # Donner un téléphone unique au client.
        for identifier in [self.customer.email,self.customer.phone]:  # Essayer les deux identifiants publics.
            result = self.client.post('/api/v1/auth/login/',{'identifier':identifier,'password':'ClientTest2026!'},format='json')  # Vérifier un mot de passe réellement haché.
            self.assertEqual(result.status_code,200)  # Confirmer la connexion.
            self.client.logout()  # Isoler le mode suivant.
    def test_login_invalid_password(self):  # Refuser une preuve incorrecte.
        self.assertEqual(self.client.post('/api/v1/auth/login/',{'identifier':'client','password':'incorrect'},format='json').status_code,400)  # Ne pas ouvrir de session.
    def test_login_csrf_required(self):  # Vérifier spécifiquement le login CSRF anonyme.
        client = APIClient(enforce_csrf_checks=True)  # Activer le contrôle que l'outil de test neutralise habituellement.
        result = client.post('/api/v1/auth/login/',{'identifier':'client','password':'ClientTest2026!'},format='json')  # Envoyer sans cookie ni jeton.
        self.assertEqual(result.status_code,403)  # Empêcher une connexion forcée depuis un site tiers.
    def test_session_login_with_csrf(self):  # Vérifier un navigateur réel avec cookie initial.
        client = APIClient(enforce_csrf_checks=True); client.get('/')  # Recevoir le jeton par la page d'accueil.
        result = client.post('/api/v1/auth/login/',{'identifier':'client','password':'ClientTest2026!'},format='json',HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)  # Transmettre le jeton courant.
        self.assertEqual(result.status_code,200); self.assertEqual(client.get('/api/v1/me/').status_code,200)  # Ouvrir une session consultable.
    def test_me_anonymous_forbidden(self):  # Protéger les données personnelles.
        self.assertEqual(self.client.get('/api/v1/me/').status_code,401)  # Refuser l'accès sans identité.
    def test_profile_cannot_escalate(self):  # Protéger rôles et statut staff d'une modification du profil.
        self.auth(self.customer)  # Agir comme client connecté.
        self.client.patch('/api/v1/me/',{'role':'admin','is_staff':True},format='json')  # Tenter une auto-promotion.
        self.customer.refresh_from_db(); self.assertEqual(self.customer.role,'client'); self.assertFalse(self.customer.is_staff)  # Garder les champs protégés inchangés.
    def test_jwt_suspension(self):  # Vérifier la suspension malgré un jeton signé non expiré.
        token = RefreshToken.for_user(self.customer)  # Émettre un vrai jeton avant suspension.
        self.customer.is_active = False; self.customer.save()  # Retirer les droits du compte.
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(token.access_token))  # Rejouer son jeton d'accès.
        self.assertEqual(self.client.get('/api/v1/me/').status_code,401)  # Refuser immédiatement ce jeton.
    def test_refresh_suspension(self):  # Refuser de renouveler un compte suspendu.
        token = RefreshToken.for_user(self.customer); self.customer.is_active = False; self.customer.save()  # Préparer un refresh antérieur à la suspension.
        self.assertEqual(self.client.post('/api/v1/auth/refresh/',{'refresh':str(token)},format='json').status_code,401)  # Respecter la suspension à la rotation.
    def test_vendor_mine_before_validation(self):  # Permettre de préparer un catalogue non publié.
        self.vendor.moderation = 'pending'; self.vendor.save(); self.auth(self.owner)  # Connecter un vendeur en attente.
        self.assertEqual(self.client.get('/api/v1/vendors/mine/').status_code,200)  # Garder son espace de travail accessible.
    def test_vendor_creation_starts_single_trial(self):  # Vérifier le cycle d'enrôlement gratuit.
        self.auth(self.other)  # Utiliser un compte vendeur sans commerce.
        body = {'name':'Nouveau commerce','phone':'+22890000000','latitude':6.13,'longitude':1.22}  # Donner un profil minimal valide.
        first = self.client.post('/api/v1/vendors/',body,format='json'); second = self.client.post('/api/v1/vendors/',body,format='json')  # Essayer deux enrôlements.
        self.assertEqual(first.status_code,201); self.assertEqual(second.status_code,400)  # Autoriser un seul commerce.
        vendor = Vendor.objects.get(owner=self.other); self.assertEqual(vendor.moderation,'pending'); self.assertEqual(vendor.subscriptions.count(),1)  # Garantir modération et trial uniques.
    def test_client_cannot_create_vendor(self):  # Respecter les rôles métier.
        self.auth(self.customer)  # Utiliser un compte client.
        self.assertEqual(self.client.post('/api/v1/vendors/',{'name':'Illégal','phone':'1','latitude':0,'longitude':0},format='json').status_code,400)  # Ne pas enrôler un commerce avec le mauvais type de compte.
    def test_other_vendor_cannot_change_status(self):  # Empêcher l'accès horizontal par identifiant connu.
        self.auth(self.other)  # Utiliser un concurrent.
        self.assertEqual(self.client.patch(f'/api/v1/vendors/{self.vendor.pk}/status/',{'status':'closed'},format='json').status_code,404)  # Ne pas confirmer l'existence d'un commerce privé éditable.
    def test_status_override_expires(self):  # Éviter un statut manuel éternel.
        self.auth(self.owner)  # Utiliser le responsable légitime.
        result = self.client.patch(f'/api/v1/vendors/{self.vendor.pk}/status/',{'status':'open'},format='json')  # Demander une ouverture temporaire.
        self.assertEqual(result.status_code,200); self.vendor.refresh_from_db(); self.assertTrue(is_open(self.vendor))  # Appliquer la dérogation.
        self.assertFalse(is_open(self.vendor,now=timezone.now() + timedelta(hours=13)))  # Revenir aux horaires après douze heures.
    def test_profile_change_requires_revalidation(self):  # Empêcher de remplacer un commerce validé par une autre identité.
        self.auth(self.owner); self.client.patch(f'/api/v1/vendors/{self.vendor.pk}/',{'name':'Commerce modifié'},format='json')  # Modifier le profil publié.
        self.vendor.refresh_from_db(); self.assertEqual(self.vendor.moderation,'pending')  # Retirer la publication jusqu'au nouveau contrôle.
    def test_invalid_timezone_rejected(self):  # Éviter une erreur de calcul des horaires.
        self.auth(self.owner)  # Connecter le propriétaire.
        self.assertEqual(self.client.patch(f'/api/v1/vendors/{self.vendor.pk}/',{'timezone':'Lome/Inexistant'},format='json').status_code,400)  # Refuser un identifiant IANA inconnu.
    def test_product_ownership(self):  # Protéger un catalogue contre un vendeur tiers.
        self.auth(self.other)  # Connecter un concurrent.
        self.assertEqual(self.client.patch(f'/api/v1/products/{self.product.pk}/',{'price':1},format='json').status_code,404)  # Refuser la modification.
        self.assertEqual(self.client.delete(f'/api/v1/products/{self.product.pk}/').status_code,404)  # Refuser la suppression.
    def test_product_crud(self):  # Vérifier le parcours complet de catalogue.
        self.auth(self.owner)  # Utiliser le propriétaire.
        result = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/products/',{'name':'Khom','price':500,'category':self.category.pk},format='json')  # Ajouter un produit.
        self.assertEqual(result.status_code,201); identifier = result.json()['id']  # Récupérer le produit créé.
        self.assertEqual(self.client.patch(f'/api/v1/products/{identifier}/',{'price':600},format='json').status_code,200)  # Modifier son prix.
        self.assertEqual(self.client.delete(f'/api/v1/products/{identifier}/').status_code,204)  # Supprimer le produit ajouté.
    def test_product_quota(self):  # Faire respecter le quota gratuit à l'écriture.
        for index in range(9): Product.objects.create(vendor=self.vendor,category=self.category,name=str(index),price=100)  # Atteindre dix produits.
        self.auth(self.owner)  # Tenter un onzième ajout légitime mais hors droits.
        self.assertEqual(self.client.post(f'/api/v1/vendors/{self.vendor.pk}/products/',{'name':'Trop','price':100,'category':self.category.pk},format='json').status_code,400)  # Refuser sans supprimer les données existantes.
    def test_product_negative_price(self):  # Refuser un montant incohérent.
        self.auth(self.owner)  # Utiliser le propriétaire.
        self.assertEqual(self.client.patch(f'/api/v1/products/{self.product.pk}/',{'price':-10},format='json').status_code,400)  # Appliquer la borne positive.
    def test_hours_atomic_validation(self):  # Conserver les horaires si une nouvelle saisie est invalide.
        OpeningHour.objects.create(vendor=self.vendor,weekday=0,start='08:00',end='18:00'); self.auth(self.owner)  # Préparer un planning valide.
        result = self.client.put(f'/api/v1/vendors/{self.vendor.pk}/hours/',[{'weekday':0,'start':'08:00','end':'08:00'}],format='json')  # Soumettre une plage nulle.
        self.assertEqual(result.status_code,400); self.assertEqual(self.vendor.hours.count(),1)  # Vérifier l'absence de perte de planning.
    def test_hours_replacement(self):  # Vérifier PUT et le remplacement complet des plages.
        self.auth(self.owner)  # Utiliser le responsable.
        result = self.client.put(f'/api/v1/vendors/{self.vendor.pk}/hours/',[{'weekday':1,'start':'08:00','end':'18:00'}],format='json')  # Définir une plage hebdomadaire.
        self.assertEqual(result.status_code,200); self.assertEqual(self.vendor.hours.get().weekday,1)  # Persister le jour demandé.
    def test_overnight_hours(self):  # Vérifier une plage lundi soir traversant minuit.
        OpeningHour.objects.create(vendor=self.vendor,weekday=0,start='22:00',end='02:00')  # Ouvrir de lundi 22 h à mardi 2 h.
        self.assertTrue(is_open(self.vendor,datetime(2026,10,13,1,0,tzinfo=ZoneInfo('Africa/Lome'))))  # Rester ouvert mardi à 1 h.
        self.assertFalse(is_open(self.vendor,datetime(2026,10,13,2,0,tzinfo=ZoneInfo('Africa/Lome'))))  # Fermer exactement à 2 h.
    def test_opening_exception_overrides_week(self):  # Donner priorité à une fermeture exceptionnelle.
        OpeningHour.objects.create(vendor=self.vendor,weekday=0,start='06:00',end='22:00')  # Préparer une plage normale.
        OpeningException.objects.create(vendor=self.vendor,date='2026-10-12',closed=True)  # Fermer exceptionnellement lundi.
        self.assertFalse(is_open(self.vendor,datetime(2026,10,12,12,0,tzinfo=ZoneInfo('Africa/Lome'))))  # Ne pas publier une disponibilité trompeuse.
    def test_duplicate_exceptions_rejected(self):  # Éviter deux décisions pour la même date.
        self.auth(self.owner)  # Utiliser le propriétaire.
        result = self.client.put(f'/api/v1/vendors/{self.vendor.pk}/exceptions/',[{'date':'2026-12-25','closed':True},{'date':'2026-12-25','closed':False,'start':'08:00','end':'12:00'}],format='json')  # Soumettre un calendrier contradictoire.
        self.assertEqual(result.status_code,400); self.assertEqual(self.vendor.exceptions.count(),0)  # Ne créer aucune exception partielle.
    def test_review_creation_and_duplicate(self):  # Vérifier un seul avis par client et commerce.
        self.auth(self.customer); body = {'vendor':self.vendor.pk,'rating':5,'text':'Bon repas'}  # Préparer une expérience cliente.
        self.assertEqual(self.client.post('/api/v1/reviews/',body,format='json').status_code,201)  # Publier le premier avis.
        self.assertEqual(self.client.post('/api/v1/reviews/',body,format='json').status_code,400)  # Refuser un doublon.
        self.assertEqual(Notification.objects.filter(user=self.owner).count(),1)  # Notifier le commerçant une seule fois.
    def test_vendor_cannot_review(self):  # Interdire les auto-évaluations et avis de comptes commerçants.
        self.auth(self.owner)  # Utiliser un compte vendeur.
        self.assertEqual(self.client.post('/api/v1/reviews/',{'vendor':self.vendor.pk,'rating':5,'text':'Mon commerce'},format='json').status_code,400)  # Refuser l'évaluation.
    def test_review_invalid_rating(self):  # Encadrer la note avant insertion SQL.
        self.auth(self.customer)  # Utiliser un client.
        for note in [0,6,-1]:  # Couvrir toutes les bornes invalides.
            self.assertEqual(self.client.post('/api/v1/reviews/',{'vendor':self.vendor.pk,'rating':note,'text':'Test'},format='json').status_code,400)  # Ne jamais enregistrer une note hors 1–5.
    def test_review_reply_ownership(self):  # Réserver la réponse au propriétaire du commerce évalué.
        review = Review.objects.create(author=self.customer,vendor=self.vendor,rating=4,text='Bien'); self.auth(self.other)  # Préparer un avis et un concurrent.
        self.assertEqual(self.client.post(f'/api/v1/reviews/{review.pk}/reply/',{'reply':'Usurpation'},format='json').status_code,404)  # Refuser une réponse usurpée.
        self.auth(self.owner); self.assertEqual(self.client.post(f'/api/v1/reviews/{review.pk}/reply/',{'reply':'Merci'},format='json').status_code,200)  # Autoriser le commerçant.
        self.assertEqual(Notification.objects.get(user=self.customer).message,'Merci')  # Transmettre la réponse au client.
    def test_favorites_idempotent_and_private(self):  # Vérifier un favori unique et personnel.
        self.auth(self.customer)  # Utiliser le propriétaire de la liste.
        for _ in range(2): self.client.post('/api/v1/favorites/',{'vendor':self.vendor.pk},format='json')  # Répéter l'ajout.
        self.assertEqual(Favorite.objects.count(),1)  # Éviter les doublons.
        self.auth(self.owner); self.assertEqual(self.client.get('/api/v1/favorites/').json(),[])  # Ne pas exposer la liste à un autre compte.
    def test_notifications_private(self):  # Protéger chaque message par son destinataire.
        item = Notification.objects.create(user=self.customer,title='Privé',message='Confidentiel'); self.auth(self.owner)  # Créer un message pour un tiers.
        self.assertEqual(self.client.post(f'/api/v1/notifications/{item.pk}/read/',{},format='json').status_code,404)  # Refuser son marquage par un autre compte.
        self.assertEqual(self.client.get('/api/v1/notifications/').json()['count'],0)  # Ne pas dévoiler sa présence.
    def test_report_requires_one_target(self):  # Vérifier l'invariant des signalements.
        self.auth(self.customer)  # Utiliser un déclarant connecté.
        self.assertEqual(self.client.post('/api/v1/reports/',{'reason':'Sans cible'},format='json').status_code,400)  # Refuser un dossier inexploitable.
        self.assertEqual(self.client.post('/api/v1/reports/',{'vendor':self.vendor.pk,'reason':'Profil trompeur'},format='json').status_code,201)  # Accepter un commerce précisément ciblé.
    def test_admin_routes_forbidden_to_client(self):  # Vérifier les barrières administratives essentielles.
        self.auth(self.customer)  # Utiliser un compte ordinaire.
        for path in ['dashboard/','users/','export/']:  # Tester métriques, comptes et extraction de données.
            self.assertEqual(self.client.get('/api/v1/admin/' + path).status_code,403)  # Refuser chaque lecture sensible.
    def test_staff_requires_actual_permission(self):  # Ne pas confondre statut staff et permission métier.
        self.customer.is_staff = True; self.customer.role = 'admin'; self.customer.save(); self.auth(self.customer)  # Donner un rôle sans autorisation fine.
        self.assertEqual(self.client.get('/api/v1/admin/dashboard/').status_code,403)  # Bloquer le tableau de bord.
        self.customer.user_permissions.add(Permission.objects.get(codename='view_user',content_type__app_label='core')); self.customer = User.objects.get(pk=self.customer.pk); self.auth(self.customer)  # Accorder seulement un droit de lecture.
        self.assertEqual(self.client.get('/api/v1/admin/dashboard/').status_code,200)  # Autoriser l'aperçu minimal.
        self.assertEqual(self.client.post(f'/api/v1/admin/vendors/{self.vendor.pk}/decision/',{'decision':'approved','reason':'Test'},format='json').status_code,403)  # Garder la décision commerciale interdite.
    def test_admin_vendor_decision_audited(self):  # Vérifier la traçabilité d'une validation.
        self.auth(self.admin)  # Utiliser un opérateur habilité.
        result = self.client.post(f'/api/v1/admin/vendors/{self.vendor.pk}/decision/',{'decision':'rejected','reason':'Adresse incorrecte'},format='json')  # Rejeter avec justification.
        self.assertEqual(result.status_code,200); self.assertTrue(Audit.objects.filter(action='vendor.moderate').exists())  # Conserver une trace de la décision.
        self.assertEqual(self.search().json()['count'],0)  # Retirer la publication immédiatement.
    def test_admin_report_hides_rating(self):  # Exclure un avis masqué de la moyenne publique.
        review = Review.objects.create(author=self.customer,vendor=self.vendor,rating=1,text='Abus'); report = Report.objects.create(author=self.owner,review=review,reason='Inapproprié'); self.auth(self.admin)  # Préparer un dossier précis.
        result = self.client.post(f'/api/v1/admin/reports/{report.pk}/resolve/',{'hide':True,'resolution':'Avis masqué après examen'},format='json')  # Traiter avec masquage.
        self.assertEqual(result.status_code,200); review.refresh_from_db(); self.assertFalse(review.visible)  # Retirer l'avis.
        self.assertEqual(self.client.get(f'/api/v1/vendors/{self.vendor.pk}/').json()['rating'],0)  # Recalculer la note sans contenu abusif.
    def test_admin_suspend_hides_vendor(self):  # Vérifier le lien suspension-publication.
        self.auth(self.admin)  # Utiliser le gestionnaire de comptes.
        self.assertEqual(self.client.post(f'/api/v1/admin/users/{self.owner.pk}/status/',{'active':False},format='json').status_code,200)  # Suspendre le responsable.
        self.assertEqual(self.search().json()['count'],0)  # Retirer son commerce des résultats.
    def test_admin_cannot_suspend_staff_in_simple_tool(self):  # Éviter un verrouillage du back-office simplifié.
        self.auth(self.admin)  # Utiliser l'administrateur lui-même.
        self.assertEqual(self.client.post(f'/api/v1/admin/users/{self.admin.pk}/status/',{'active':False},format='json').status_code,400)  # Refuser son auto-suspension.
    def test_admin_broadcast_targets_role(self):  # Respecter le ciblage clients/vendeurs.
        self.auth(self.admin)  # Utiliser un opérateur de communication.
        result = self.client.post('/api/v1/admin/broadcast/',{'title':'Information','message':'Bonjour','role':'client'},format='json')  # Cibler seulement les clients.
        self.assertEqual(result.status_code,200); self.assertEqual(Notification.objects.filter(user=self.customer).count(),1); self.assertEqual(Notification.objects.filter(user=self.owner).count(),0)  # Ne pas diffuser aux autres rôles.
    def test_csv_formula_neutralized(self):  # Empêcher l'exécution de formules dans un tableur.
        self.customer.first_name = '=HYPERLINK("evil")'; self.customer.save(); self.auth(self.admin)  # Préparer une donnée ressemblant à une formule.
        result = self.client.get('/api/v1/admin/export/')  # Exporter via le parcours protégé.
        self.assertEqual(result.status_code,200); self.assertIn("'=HYPERLINK",result.content.decode())  # Préfixer le contenu dangereux d'une apostrophe.
    def test_discovery_quote_forbidden(self):  # Empêcher le renouvellement gratuit répétitif du trial.
        with self.assertRaises(ValidationError): quote(self.vendor,'discovery')  # Refuser une souscription gratuite par le service métier.
    def test_request_does_not_activate_plan(self):  # Ne pas confondre demande de règlement et encaissement.
        self.auth(self.owner)  # Demander une formule depuis l'espace vendeur.
        result = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/subscriptions/',{'plan':'essential'},format='json')  # Créer un devis financier.
        self.assertEqual(result.status_code,201); self.assertEqual(plan_key(self.vendor),'discovery'); self.assertEqual(Payment.objects.get().status,'pending')  # Garder les anciens droits jusqu'à confirmation.
    def test_duplicate_pending_payment_blocked(self):  # Éviter deux devis simultanés contradictoires.
        self.auth(self.owner)  # Utiliser le vendeur légitime.
        for expected in [201,400]: self.assertEqual(self.client.post(f'/api/v1/vendors/{self.vendor.pk}/subscriptions/',{'plan':'essential'},format='json').status_code,expected)  # Bloquer la seconde demande.
    def test_confirm_payment_idempotent(self):  # Résister à une répétition de webhook ou clic d'opérateur.
        payment = self.payment(); first = confirm_payment(payment.pk,self.admin,'REC-1'); second = confirm_payment(payment.pk,self.admin,'REC-1')  # Confirmer deux fois le même reçu.
        self.assertEqual(first.pk,second.pk); self.assertEqual(self.vendor.subscriptions.count(),2); self.assertEqual(plan_key(self.vendor),'essential')  # Accorder une seule nouvelle période.
        self.assertEqual(Audit.objects.filter(action='payment.confirm').count(),1)  # Tracer une seule activation.
    def test_confirm_requires_receipt(self):  # Ne jamais activer sans preuve externe référencée.
        with self.assertRaises(ValidationError): confirm_payment(self.payment().pk,self.admin,'')  # Refuser une référence vide.
        self.assertEqual(plan_key(self.vendor),'discovery')  # Garder les droits initiaux.
    def test_stale_quote_rejected(self):  # Limiter la validité d'un devis financier.
        payment = self.payment(); Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(hours=25))  # Vieillir la demande.
        with self.assertRaises(ValidationError): confirm_payment(payment.pk,self.admin,'REC-2')  # Refuser une activation à un montant périmé.
    def test_upgrade_credit(self):  # Vérifier le calcul au prorata d'une période payée.
        self.sub.end = timezone.now(); self.sub.save()  # Terminer l'essai pour éviter un chevauchement.
        now = timezone.now(); Subscription.objects.create(vendor=self.vendor,plan='essential',start=now - timedelta(days=45),end=now + timedelta(days=45),amount=1500)  # Placer le vendeur au milieu de sa période.
        result = quote(self.vendor,'growth'); self.assertEqual(result['credit'],750); self.assertEqual(result['amount'],2250)  # Retirer seulement le solde non consommé.
    def test_downgrade_blocked_during_active_period(self):  # Éviter une perte de droits avant l'échéance.
        self.sub.end = timezone.now(); self.sub.save(); Subscription.objects.create(vendor=self.vendor,plan='performance',end=add_months(timezone.now(),12),amount=5000)  # Activer une formule annuelle.
        with self.assertRaises(ValidationError): quote(self.vendor,'essential')  # Refuser une baisse de formule immédiate.
    def test_expiry_preserves_catalog(self):  # Garantir le repli sans suppression de données.
        self.sub.end = timezone.now(); self.sub.save(); Subscription.objects.create(vendor=self.vendor,plan='growth',start=timezone.now()-timedelta(days=200),end=timezone.now()-timedelta(days=1),amount=3000)  # Préparer une formule expirée.
        for index in range(14): Product.objects.create(vendor=self.vendor,category=self.category,name=f'Produit {index}',price=100)  # Stocker quinze produits au total.
        self.assertEqual(plan_key(self.vendor),'discovery'); self.assertEqual(len(visible_products(self.vendor)),10); self.assertEqual(self.vendor.products.count(),15)  # Masquer l'excédent et préserver le catalogue.
    def test_calendar_month_end(self):  # Respecter les fins de mois contractuelles.
        value = datetime(2026,1,31,12,0,tzinfo=ZoneInfo('UTC')); self.assertEqual(add_months(value,1).day,28)  # Éviter une date de février inexistante.
    def test_haversine_antimeridian(self):  # Vérifier une frontière géographique souvent oubliée.
        self.assertLess(distance_m(0,179.99,0,-179.99),3000)  # Calculer la proximité réelle malgré le changement de signe.
    def test_tick_idempotent(self):  # Ne pas répéter les rappels d'abonnement.
        self.sub.end = timezone.now() + timedelta(days=6); self.sub.save()  # Positionner le trial dans la fenêtre J-7.
        for _ in range(2): call_command('subscriptions_tick',stdout=StringIO())  # Simuler deux passages quotidiens.
        self.assertEqual(Notification.objects.filter(dedupe_key=f'sub:{self.sub.pk}:reminder7').count(),1)  # Créer un seul rappel.
    def test_tick_expiration(self):  # Informer du repli sans supprimer les produits.
        self.sub.end = timezone.now() - timedelta(days=1); self.sub.save()  # Faire expirer l'essai.
        call_command('subscriptions_tick',stdout=StringIO())  # Exécuter le cron.
        self.assertEqual(Notification.objects.filter(dedupe_key=f'sub:{self.sub.pk}:expired_notified').count(),1); self.assertEqual(self.vendor.products.count(),1)  # Préserver le catalogue.
    @override_settings(PAYMENT_WEBHOOK_SECRET='webhook-test-secret')  # Configurer un secret propre aux tests financiers.
    def test_signed_webhook_and_replay(self):  # Vérifier signature, montant et idempotence d'un véritable événement.
        payment = self.payment(); payload = json.dumps({'reference':payment.reference,'status':'paid','amount':payment.amount,'currency':'XOF','external_reference':'MM-123'}).encode(); timestamp = str(int(time.time()))  # Figer les octets signés.
        signature = hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(),timestamp.encode()+b'.'+payload,hashlib.sha256).hexdigest()  # Calculer le contrat d'authenticité.
        for _ in range(2): self.assertEqual(self.client.post('/api/v1/payments/webhook/',payload,content_type='application/json',HTTP_X_MIAGBO_TIMESTAMP=timestamp,HTTP_X_MIAGBO_SIGNATURE=signature).status_code,200)  # Accepter un rejeu légitime sans double activation.
        self.assertEqual(self.vendor.subscriptions.count(),2)  # Créer un seul abonnement payé.
    @override_settings(PAYMENT_WEBHOOK_SECRET='webhook-test-secret')  # Activer la validation de signature.
    def test_invalid_webhook_rejected(self):  # Refuser des événements non authentifiés.
        self.assertEqual(self.client.post('/api/v1/payments/webhook/',{},format='json').status_code,401)  # Ne pas accepter un simple corps JSON.
    def test_unconfigured_webhook_disabled(self):  # Refuser tout paiement externe sans secret.
        self.assertEqual(self.client.post('/api/v1/payments/webhook/',{},format='json').status_code,503)  # Expliquer le blocage de configuration.
    def test_admin_payment_activation(self):  # Vérifier le parcours réel d'un opérateur financier.
        payment = self.payment(); self.auth(self.admin)  # Préparer un règlement et l'opérateur.
        result = self.client.post(f'/api/v1/admin/payments/{payment.pk}/decision/',{'decision':'paid','external_reference':'MobileMoney-456'},format='json')  # Confirmer après vérification du reçu.
        self.assertEqual(result.status_code,200); self.assertEqual(plan_key(self.vendor),'essential')  # Accorder les droits payés.
    def test_admin_payment_rejection(self):  # Rejeter une demande sans accorder de droits.
        payment = self.payment(); self.auth(self.admin)  # Préparer un règlement en attente.
        result = self.client.post(f'/api/v1/admin/payments/{payment.pk}/decision/',{'decision':'rejected','external_reference':'Reçu non valide'},format='json')  # Refuser explicitement.
        self.assertEqual(result.status_code,200); self.assertEqual(plan_key(self.vendor),'discovery')  # Conserver le trial.
    def test_reset_response_non_enumerating(self):  # Ne pas divulguer les emails de comptes enregistrés.
        a = self.client.post('/api/v1/auth/password-reset/',{'email':self.customer.email},format='json'); b = self.client.post('/api/v1/auth/password-reset/',{'email':'absent@test.local'},format='json')  # Comparer un compte présent et absent.
        self.assertEqual(a.json(),b.json())  # Retourner la même réponse publique.
    def test_reset_token_single_use(self):  # Vérifier le changement de mot de passe et le refus de rejeu.
        token = default_token_generator.make_token(self.customer); uid = urlsafe_base64_encode(force_bytes(self.customer.pk)); data = {'uid':uid,'token':token,'password':'ChangedSecure2026!'}  # Construire un vrai lien de récupération.
        self.assertEqual(self.client.post('/api/v1/auth/password-confirm/',data,format='json').status_code,200)  # Consommer le jeton.
        self.assertEqual(self.client.post('/api/v1/auth/password-confirm/',data,format='json').status_code,400)  # Refuser son deuxième usage.
    def test_reset_invalid_uid(self):  # Traiter un identifiant malformé sans erreur serveur.
        self.assertEqual(self.client.post('/api/v1/auth/password-confirm/',{'uid':'***','token':'invalid','password':'ChangedSecure2026!'},format='json').status_code,400)  # Répondre uniformément.
    def test_image_reencoded(self):  # Vérifier un média réellement décodé et transformé.
        buffer = BytesIO(); Image.new('RGB',(1800,100),(200,100,50)).save(buffer,'PNG'); file = SimpleUploadedFile('untrusted.png',buffer.getvalue(),content_type='image/png')  # Créer une image plus large que la limite de sortie.
        output = safe_image(file); picture = Image.open(output)  # Lire le fichier sûr produit par le service.
        self.assertEqual(picture.format,'JPEG'); self.assertLessEqual(picture.width,1400); self.assertNotIn('untrusted',output.name)  # Réencoder, redimensionner et renommer.
    def test_fake_image_rejected(self):  # Refuser un script déguisé en photographie.
        with self.assertRaises(ValidationError): safe_image(SimpleUploadedFile('evil.jpg',b'<script>alert(1)</script>',content_type='image/jpeg'))  # Vérifier le contenu au lieu de l'extension.
    def test_account_export_private(self):  # Exporter uniquement les données du propriétaire connecté.
        self.auth(self.customer)  # Utiliser un client.
        result = self.client.get('/api/v1/account/'); self.assertEqual(result.status_code,200); self.assertEqual(result.json()['profile']['id'],self.customer.pk); self.assertNotIn('password',result.json()['profile'])  # Ne pas inclure les secrets ni le profil d'un tiers.
    def test_account_close_requires_password(self):  # Protéger la désactivation d'une preuve supplémentaire.
        self.auth(self.customer)  # Utiliser le propriétaire.
        self.assertEqual(self.client.delete('/api/v1/account/',{'password':'wrong'},format='json').status_code,400)  # Refuser une preuve incorrecte.
        self.assertEqual(self.client.delete('/api/v1/account/',{'password':'ClientTest2026!'},format='json').status_code,200)  # Accepter la fermeture confirmée.
        self.customer.refresh_from_db(); self.assertFalse(self.customer.is_active)  # Retirer l'accès immédiatement.
    def test_device_registration_idempotent(self):  # Réassocier un terminal sans violer son unicité.
        self.auth(self.customer); body = {'token':'ExpoPushToken[abcdefgh]','platform':'android'}  # Utiliser un token de test conforme au format Expo.
        for _ in range(2): self.assertEqual(self.client.post('/api/v1/devices/',body,format='json').status_code,200)  # Accepter une inscription répétée.
        self.assertEqual(Device.objects.count(),1)  # Garder une seule destination.
    def test_device_invalid_format(self):  # Ne pas envoyer vers un token arbitraire.
        self.auth(self.customer)  # Utiliser une identité valide.
        self.assertEqual(self.client.post('/api/v1/devices/',{'token':'invalid','platform':'android'},format='json').status_code,400)  # Exiger un token Expo structuré.
    def test_logout_removes_push_devices(self):  # Ne pas continuer les envois après une déconnexion de compte.
        Device.objects.create(user=self.customer,token='ExpoPushToken[abcdefgh]',platform='android'); self.auth(self.customer)  # Associer un terminal au compte.
        self.assertEqual(self.client.post('/api/v1/auth/logout/',{},format='json').status_code,204); self.assertFalse(Device.objects.exists())  # Retirer les destinations de ce compte.
    def test_purge_searches(self):  # Respecter les quatre-vingt-dix jours de rétention.
        event = SearchEvent.objects.create(keyword='ancien'); SearchEvent.objects.filter(pk=event.pk).update(created_at=timezone.now()-timedelta(days=91)); SearchEvent.objects.create(keyword='récent')  # Préparer ancien et récent.
        call_command('purge_searches',stdout=StringIO()); self.assertEqual(list(SearchEvent.objects.values_list('keyword',flat=True)),['récent'])  # Effacer seulement les données hors rétention.
    def test_oauth_unconfigured(self):  # Ne pas afficher une fausse connexion sociale.
        self.assertEqual(self.client.post('/auth/google/start/',{'consent':'on'}).status_code,503)  # Refuser l'absence de credentials.
    def test_oauth_bad_state(self):  # Bloquer un callback sans parcours de session.
        self.assertEqual(self.client.get('/auth/google/callback/',{'code':'fake','state':'fake'}).status_code,400)  # Refuser le login CSRF avant tout appel externe.
    @override_settings(GOOGLE_CLIENT_ID='test-client',GOOGLE_CLIENT_SECRET='test-secret')  # Configurer un fournisseur fictif isolé.
    def test_oauth_pkce_start(self):  # Vérifier les trois protections du parcours OIDC.
        result = self.client.post('/auth/google/start/',{'consent':'on'})  # Démarrer avec un accord explicite.
        self.assertEqual(result.status_code,302); self.assertIn('code_challenge_method=S256',result.url); self.assertIn('nonce=',result.url); self.assertIn('state=',result.url)  # Produire les paramètres standards de sécurité.
    @override_settings(PUSH_ENABLED=True)  # Activer seulement le transport simulé du test.
    @patch('core.management.commands.send_push.expo_call')  # Empêcher tout envoi distant réel.
    def test_push_ticket_then_receipt(self, provider):  # Distinguer prise en charge, réception transport et lecture.
        Device.objects.create(user=self.customer,token='ExpoPushToken[abcdefgh]',platform='android'); Notification.objects.create(user=self.customer,title='Test',message='Message'); provider.return_value = {'data':{'status':'ok','id':'ticket-123'}}  # Simuler un ticket accepté.
        call_command('send_push',stdout=StringIO()); delivery = PushDelivery.objects.get(); self.assertEqual(delivery.status,'accepted')  # Ne pas qualifier le message de reçu trop tôt.
        PushDelivery.objects.filter(pk=delivery.pk).update(next_attempt=timezone.now()-timedelta(minutes=1)); provider.return_value = {'data':{'ticket-123':{'status':'ok'}}}  # Simuler le reçu fournisseur quinze minutes plus tard.
        call_command('send_push',stdout=StringIO()); delivery.refresh_from_db(); self.assertEqual(delivery.status,'received')  # Mettre à jour l'acheminement sans marquer le message lu.
    def test_schema_available(self):  # Vérifier que la documentation de l'API est effectivement servie.
        self.auth(self.customer)  # Utiliser un compte connecté selon les permissions DRF par défaut.
        self.assertEqual(self.client.get('/api/v1/schema/').status_code,200)  # Obtenir le contrat OpenAPI.
    def test_case_insensitive_username_collision(self):  # Refuser deux comptes dont seul le nom change de casse.
        result = self.client.post('/api/v1/auth/register/',{'username':'CLIENT','email':'other@test.local','password':'SecureTrial2026!','role':'client','consent':True},format='json')  # Réutiliser un identifiant déjà enregistré.
        self.assertEqual(result.status_code,400)  # Garder la connexion non ambiguë.
    def test_profile_phone_normalization(self):  # Valider la normalisation après inscription aussi.
        self.auth(self.customer); result = self.client.patch('/api/v1/me/',{'phone':'+228 91 22 33 44'},format='json')  # Saisir un format de présentation.
        self.assertEqual(result.status_code,200); self.customer.refresh_from_db(); self.assertEqual(self.customer.phone,'+22891223344')  # Conserver la version internationale canonique.
    def test_profile_email_case_collision(self):  # Préserver l'unicité de l'email lors d'une modification du profil.
        self.auth(self.customer)  # Utiliser un client ordinaire.
        self.assertEqual(self.client.patch('/api/v1/me/',{'email':'VENDEUR@test.local'},format='json').status_code,400)  # Refuser l'email d'un autre compte malgré sa casse.
    def test_alert_zone_requires_specific_consent(self):  # Ne pas enregistrer une position avec le seul consentement au compte.
        self.auth(self.customer); result = self.client.post('/api/v1/alerts/',{'latitude':6.13,'longitude':1.22,'radius':2000,'consent':False},format='json')  # Refuser explicitement les alertes.
        self.assertEqual(result.status_code,400)  # Respecter la préférence.
        from .models import AlertZone  # Vérifier la donnée réellement conservée.
        self.assertFalse(AlertZone.objects.exists())  # Ne pas enregistrer la zone sans consentement.
    def test_alert_zone_private_and_removable(self):  # Vérifier création, isolation et retrait du consentement.
        self.auth(self.customer); result = self.client.post('/api/v1/alerts/',{'latitude':6.13,'longitude':1.22,'radius':2000,'consent':True},format='json')  # Activer la zone volontairement.
        self.assertEqual(result.status_code,200); self.auth(self.owner); self.assertEqual(self.client.get('/api/v1/alerts/').status_code,403)  # Ne pas exposer une zone cliente à un vendeur.
        self.auth(self.customer); self.assertEqual(self.client.delete('/api/v1/alerts/').status_code,204); self.assertIsNone(self.client.get('/api/v1/alerts/').json())  # Effacer les coordonnées à la désactivation.
    def test_nearby_alerts_idempotent(self):  # Éviter des notifications répétées à chaque passage du worker.
        from .models import AlertZone  # Préparer un consentement géographique explicite.
        AlertZone.objects.create(user=self.customer,latitude=6.13,longitude=1.22,radius=1000)  # Choisir une zone contenant notre commerce.
        for _ in range(2): call_command('nearby_alerts',stdout=StringIO())  # Vérifier la reprise du job.
        self.assertEqual(Notification.objects.filter(user=self.customer,dedupe_key=f'nearby:{self.customer.pk}:{self.vendor.pk}').count(),1)  # Informer une seule fois du nouveau commerce.
    def test_growth_promotion_quota_and_targeting(self):  # Respecter la campagne mensuelle et le rayon consenti.
        from .models import AlertZone  # Fournir un destinataire ayant demandé ces alertes.
        AlertZone.objects.create(user=self.customer,latitude=6.13,longitude=1.22,radius=1000); self.sub.end = timezone.now(); self.sub.save(); Subscription.objects.create(vendor=self.vendor,plan='growth',end=add_months(timezone.now(),6),amount=3000); self.auth(self.owner)  # Activer les droits Croissance du commerçant.
        result = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/promote/',{'message':'Découvrez notre commerce'},format='json')  # Envoyer la première mise en avant.
        self.assertEqual(result.status_code,201); self.assertEqual(result.json()['recipients'],1)  # Cibler le client réellement proche.
        self.assertEqual(self.client.post(f'/api/v1/vendors/{self.vendor.pk}/promote/',{'message':'Deuxième essai'},format='json').status_code,400)  # Refuser une seconde campagne ce mois.
    def test_performance_promotions_daily_recipient_limit(self):  # Autoriser les demandes Premium tout en protégeant les clients des répétitions.
        from .models import AlertZone  # Définir une zone cliente consentie.
        AlertZone.objects.create(user=self.customer,latitude=6.13,longitude=1.22,radius=1000); self.sub.end = timezone.now(); self.sub.save(); Subscription.objects.create(vendor=self.vendor,plan='performance',end=add_months(timezone.now(),12),amount=5000); self.auth(self.owner)  # Activer la formule annuelle.
        first = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/promote/',{'message':'Bonjour'},format='json'); second = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/promote/',{'message':'Encore'},format='json')  # Déclencher deux campagnes dans la même journée.
        self.assertEqual(first.status_code,201); self.assertEqual(second.status_code,201); self.assertEqual(second.json()['recipients'],0)  # Garder un seul message par commerce et client ce jour.
    def test_confirmed_receipt_cannot_be_reused(self):  # Empêcher de financer deux commerces avec la même preuve externe.
        first = self.payment(); confirm_payment(first.pk,self.admin,'SHARED-RECEIPT')  # Consommer un reçu valide une fois.
        vendor = Vendor.objects.create(owner=self.other,name='Autre commerce',phone='+22890000001',latitude=6.13,longitude=1.22); payment = Payment.objects.create(vendor=vendor,plan='essential',amount=1500,reference='OTHER-PAYMENT')  # Préparer un second bénéficiaire.
        with self.assertRaises(IntegrityError):  # Exiger une protection atomique en base, pas un simple contrôle préalable.
            with transaction.atomic(): confirm_payment(payment.pk,self.admin,'SHARED-RECEIPT')  # Rejouer le reçu sur une autre transaction.
        payment.refresh_from_db(); self.assertEqual(payment.status,'pending')  # Ne pas laisser une activation partielle.
    @override_settings(GOOGLE_CLIENT_ID='test-client',GOOGLE_CLIENT_SECRET='test-secret')  # Simuler seulement la configuration OIDC locale.
    @patch('core.oauth.jwt.decode')  # Tester nos vérifications de claims sans dépendre d'une clé réelle de fournisseur.
    @patch('core.oauth.jwt.PyJWKClient')  # Ne pas contacter le serveur de clés externe.
    @patch('core.oauth.urllib.request.urlopen')  # Simuler l'échange du code OAuth.
    def test_google_new_account_claims_checked(self, http, keys, decode):  # Vérifier création, session et algorithme imposé sur un retour fournisseur valide.
        self.client.post('/auth/google/start/',{'consent':'on'}); flow = self.client.session['oidc']  # Préparer un vrai state de session et un nonce serveur.
        http.return_value.__enter__.return_value.read.return_value = b'{"id_token":"signed-id-token"}'  # Fournir la réponse JSON attendue de l'endpoint token.
        decode.return_value = {'sub':'google-test-subject','iss':'https://accounts.google.com','nonce':flow['nonce'],'email':'newgoogle@test.local','email_verified':True,'given_name':'Ama'}  # Simuler des claims signés conformes au protocole.
        result = self.client.get('/auth/google/callback/',{'state':flow['state'],'code':'one-time-code'})  # Revenir dans la session qui a demandé le fournisseur.
        self.assertEqual(result.status_code,302); self.assertTrue(User.objects.filter(email='newgoogle@test.local',role='client').exists())  # Créer seulement un client sans privilège.
        self.assertEqual(decode.call_args.kwargs['algorithms'],['RS256']); self.assertEqual(decode.call_args.kwargs['audience'],'test-client')  # Imposer les vérifications cryptographiques au SDK JWT.
    @override_settings(GOOGLE_CLIENT_ID='test-client',GOOGLE_CLIENT_SECRET='test-secret')  # Préparer une configuration sociale isolée.
    @patch('core.oauth.jwt.decode')  # Contrôler le nonce renvoyé pour le scénario d'attaque.
    @patch('core.oauth.jwt.PyJWKClient')  # Éviter le réseau de récupération des clés.
    @patch('core.oauth.urllib.request.urlopen')  # Éviter un vrai échange de code OAuth.
    def test_google_bad_nonce_rejected(self, http, keys, decode):  # Refuser une identité qui ne correspond pas à la demande de session.
        self.client.post('/auth/google/start/',{'consent':'on'}); flow = self.client.session['oidc']; http.return_value.__enter__.return_value.read.return_value = b'{"id_token":"token"}'  # Démarrer un parcours valide.
        decode.return_value = {'sub':'wrong-nonce-sub','iss':'https://accounts.google.com','nonce':'wrong-nonce','email':'evil@test.local','email_verified':True}  # Injecter un jeton d'une autre demande.
        result = self.client.get('/auth/google/callback/',{'state':flow['state'],'code':'code'})  # Tenter la connexion avec un state valide mais nonce incohérent.
        self.assertEqual(result.status_code,400); self.assertFalse(User.objects.filter(email='evil@test.local').exists())  # Ne créer aucun compte sur ce retour.
    @override_settings(PUSH_ENABLED=True)  # Activer uniquement le worker simulé.
    @patch('core.management.commands.send_push.expo_call',side_effect=OSError('network down'))  # Reproduire une panne fournisseur réelle sans trafic externe.
    def test_push_transport_failure_retried(self, provider):  # Ne pas perdre un message lors d'une indisponibilité transitoire.
        Device.objects.create(user=self.customer,token='ExpoPushToken[retrytoken]',platform='android'); Notification.objects.create(user=self.customer,title='Essai',message='À reprendre')  # Préparer un message destiné à un terminal valide.
        call_command('send_push',stdout=StringIO()); delivery = PushDelivery.objects.get()  # Exécuter un passage qui échoue au transport.
        self.assertEqual(delivery.status,'pending'); self.assertEqual(delivery.attempts,1); self.assertGreater(delivery.next_attempt,timezone.now())  # Replanifier sans annoncer de livraison réussie.
    def test_vendor_rejects_nonfinite_coordinates(self):  # Refuser les coordonnées qui casseraient l'index PostGIS.
        self.auth(self.owner)  # Utiliser le propriétaire légitime pour tester la validation des données.
        for value in ['NaN','Infinity','-Infinity']:  # Couvrir les valeurs spéciales acceptées par float().
            self.assertEqual(self.client.patch(f'/api/v1/vendors/{self.vendor.pk}/',{'latitude':value},format='json').status_code,400)  # Refuser avant l'écriture ou la requête géographique.
    def test_alert_zone_rejects_nonfinite_coordinates(self):  # Empêcher une zone privée impossible à calculer.
        self.auth(self.customer)  # Utiliser un client ayant le droit de choisir une zone.
        self.assertEqual(self.client.post('/api/v1/alerts/',{'latitude':'NaN','longitude':1.22,'radius':2000,'consent':True},format='json').status_code,400)  # Ne jamais persister une coordonnée non finie malgré un consentement valide.
