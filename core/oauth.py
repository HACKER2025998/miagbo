import base64  # Encoder le challenge PKCE dans l'URL de connexion.
import hashlib  # Calculer le challenge S256 associé au vérificateur secret.
import hmac  # Comparer les paramètres de session sans fuite temporelle.
import json  # Décoder la réponse du fournisseur.
import secrets  # Générer state, nonce et vérificateur imprévisibles.
import time  # Expirer un parcours OAuth abandonné.
import urllib.parse  # Encoder les paramètres du protocole OAuth2.
import urllib.request  # Communiquer uniquement avec les endpoints Google fixes.
import jwt  # Vérifier la signature RS256 du jeton d'identité Google.
from django.conf import settings  # Lire les identifiants OIDC et le domaine de callback.
from django.contrib.auth import login  # Ouvrir la même session protégée que le formulaire classique.
from django.db import transaction  # Associer identité externe et compte atomiquement.
from django.http import JsonResponse  # Fournir des erreurs sans détails fournisseurs ni tokens.
from django.shortcuts import redirect  # Rediriger vers Google puis l'application.
from django.utils import timezone  # Tracer le consentement d'inscription.
from django.views.decorators.csrf import csrf_protect  # Vérifier le consentement avant de commencer le parcours.
from django.views.decorators.http import require_POST, require_GET  # Encadrer les deux étapes OAuth.
from .models import User, SocialIdentity  # Conserver une liaison explicite avec le sub Google.
from .services import audit  # Tracer les liaisons d'identité sans secret.
@require_POST  # Commencer seulement après un formulaire explicite.
@csrf_protect  # Protéger aussi une liaison de compte déjà connecté.
def google_start(request):  # Préparer une connexion OIDC avec PKCE, state et nonce.
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:  # Refuser le parcours avant configuration réelle.
        return JsonResponse({'detail': 'Connexion Google non configurée.'}, status=503)  # Ne pas afficher un faux bouton actif.
    if request.POST.get('consent') != 'on':  # Exiger l'acceptation des conditions de compte.
        return JsonResponse({'detail': 'Consentement requis.'}, status=400)  # Ne pas créer de compte sans accord.
    verifier = secrets.token_urlsafe(64)  # Produire la preuve PKCE qui reste côté serveur.
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)  # Protéger le retour contre injection et rejeu d'identité.
    request.session['oidc'] = {'state':state,'nonce':nonce,'verifier':verifier,'started':time.time(),'user':request.user.pk if request.user.is_authenticated else None}  # Lier le parcours à cette session seulement.
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()  # Construire le challenge S256 du protocole.
    params = {'client_id':settings.GOOGLE_CLIENT_ID,'redirect_uri':settings.PUBLIC_URL + '/auth/google/callback/','response_type':'code','scope':'openid email profile','state':state,'nonce':nonce,'code_challenge':challenge,'code_challenge_method':'S256','prompt':'select_account'}  # Demander uniquement les données de compte nécessaires.
    return redirect('https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params))  # Ouvrir le fournisseur officiel avec paramètres encodés.
@require_GET  # Accepter le retour standard de Google uniquement en GET.
def google_callback(request):  # Vérifier puis relier l'identité sociale sans fusion automatique par email.
    flow = request.session.pop('oidc', None)  # Consommer le state une seule fois.
    if not flow or time.time() - flow['started'] > 600 or not hmac.compare_digest(flow['state'],request.GET.get('state','')):  # Vérifier session, expiration et state.
        return JsonResponse({'detail':'Parcours de connexion invalide ou expiré.'},status=400)  # Bloquer le login CSRF.
    try:  # Traiter les erreurs du fournisseur sans enregistrer son corps sensible.
        data = urllib.parse.urlencode({'code':request.GET['code'],'client_id':settings.GOOGLE_CLIENT_ID,'client_secret':settings.GOOGLE_CLIENT_SECRET,'redirect_uri':settings.PUBLIC_URL + '/auth/google/callback/','grant_type':'authorization_code','code_verifier':flow['verifier']}).encode()  # Réclamer le jeton avec la preuve PKCE.
        with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data),timeout=10) as response:  # Envoyer le code seulement au fournisseur de confiance.
            token = json.load(response)['id_token']  # Ne conserver que le jeton nécessaire à la vérification.
        key = jwt.PyJWKClient('https://www.googleapis.com/oauth2/v3/certs',timeout=10).get_signing_key_from_jwt(token)  # Charger la clé publique correspondant au kid déclaré.
        claims = jwt.decode(token,key.key,algorithms=['RS256'],audience=settings.GOOGLE_CLIENT_ID,options={'require':['exp','iat','sub','iss','nonce','email']})  # Vérifier signature, audience et expiration avec algorithme imposé.
        if claims['iss'] not in ['accounts.google.com','https://accounts.google.com'] or not hmac.compare_digest(claims['nonce'],flow['nonce']) or claims.get('email_verified') is not True:  # Vérifier émetteur, nonce et email confirmé.
            raise ValueError()  # Refuser une identité insuffisamment vérifiée.
        with transaction.atomic():  # Rendre la création ou liaison indivisible.
            identity = SocialIdentity.objects.select_related('user').filter(subject=claims['sub']).first()  # Rechercher par identifiant fournisseur stable.
            if flow['user']:  # Traiter une liaison demandée depuis une session authentifiée.
                if not request.user.is_authenticated or request.user.pk != flow['user'] or identity and identity.user_id != request.user.pk:  # Refuser une identité déjà rattachée à un autre compte.
                    raise ValueError()  # Ne jamais fusionner deux comptes implicitement.
                user = request.user  # Utiliser uniquement le compte ayant démarré la liaison.
                SocialIdentity.objects.get_or_create(subject=claims['sub'],defaults={'user':user})  # Enregistrer la nouvelle liaison de manière unique.
            elif identity:  # Connecter une identité déjà connue.
                user = identity.user  # Retrouver son compte MIAGBO.
            else:  # Créer un nouveau client social sans privilège administratif.
                if User.objects.filter(email__iexact=claims['email']).exists():  # Empêcher la prise de contrôle d'un compte existant par correspondance email.
                    return JsonResponse({'detail':'Cet email possède déjà un compte. Connectez-vous avec votre mot de passe puis liez Google depuis Mon compte.'},status=409)  # Exiger une preuve du compte existant.
                user = User.objects.create_user(username='google-' + secrets.token_hex(8),email=claims['email'].lower(),first_name=str(claims.get('given_name',''))[:80],role='client',consent_at=timezone.now())  # Définir un mot de passe inutilisable par défaut.
                SocialIdentity.objects.create(user=user,subject=claims['sub'])  # Lier le sub au nouveau compte.
            if not user.is_active:  # Respecter les suspensions administratives.
                raise ValueError()  # Refuser la connexion sociale d'un compte suspendu.
            audit(user,'auth.google',user.pk)  # Conserver seulement la trace de connexion.
        login(request,user,backend='django.contrib.auth.backends.ModelBackend')  # Ouvrir la session sécurisée commune.
        return redirect('/')  # Revenir à l'interface sans token dans l'URL.
    except Exception:  # Répondre de façon uniforme à une erreur réseau, JWT ou liaison.
        return JsonResponse({'detail':'Connexion Google refusée ou momentanément indisponible. Utilisez votre compte MIAGBO.'},status=400)  # Ne jamais exposer le code, les secrets ni le jeton fournisseur.
