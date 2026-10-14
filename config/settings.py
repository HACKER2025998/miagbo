from pathlib import Path  # Construire des chemins compatibles Linux, macOS et Windows.
import os  # Lire la configuration fournie par l'exploitant.
from datetime import timedelta  # Définir la durée des jetons mobiles.
BASE_DIR = Path(__file__).resolve().parent.parent  # Identifier la racine du projet.
DEBUG = os.getenv('DEBUG', '1') == '1'  # Activer les diagnostics uniquement en développement.
SECRET_KEY = os.getenv('SECRET_KEY', 'local-only-change-before-production-miagbo-2026')  # Charger la clé de signature.
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith('local-only')):  # Empêcher une production avec une clé prévisible.
    raise RuntimeError('SECRET_KEY doit être aléatoire et contenir au moins 50 caractères.')  # Refuser un démarrage dangereux.
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')  # Refuser les hôtes inattendus.
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'rest_framework', 'rest_framework_simplejwt.token_blacklist', 'corsheaders', 'drf_spectacular', 'core']  # Activer les modules nécessaires.
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'corsheaders.middleware.CorsMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'core.middleware.ActiveUserMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']  # Appliquer sécurité, sessions et contrôle des comptes suspendus.
ROOT_URLCONF = 'config.urls'  # Désigner le registre des routes.
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]  # Rendre les pages et les jetons CSRF.
WSGI_APPLICATION = 'config.wsgi.application'  # Exposer le serveur aux processus Gunicorn.
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.getenv('MIAGBO_SQLITE_PATH', str(BASE_DIR / 'db.sqlite3'))}}  # Permettre un démarrage local sans serveur SQL.
if os.getenv('DB_HOST'):  # Utiliser PostgreSQL lorsque son hôte est configuré.
    DATABASES['default'] = {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.getenv('DB_NAME', 'miagbo'), 'USER': os.getenv('DB_USER', 'miagbo'), 'PASSWORD': os.environ['DB_PASSWORD'], 'HOST': os.environ['DB_HOST'], 'PORT': os.getenv('DB_PORT', '5432'), 'CONN_MAX_AGE': 60}  # Lire les accès hors du dépôt.
AUTH_USER_MODEL = 'core.User'  # Centraliser les rôles et contacts dans notre utilisateur.
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]  # Exiger un mot de passe suffisamment robuste.
LANGUAGE_CODE = 'fr-fr'  # Utiliser les messages de validation français.
TIME_ZONE = 'Africa/Lome'  # Interpréter les horaires commerciaux au Togo par défaut.
USE_I18N = True  # Préparer les traductions futures.
USE_TZ = True  # Stocker les instants en UTC et convertir à l'affichage.
STATIC_URL = '/static/'  # Définir l'URL des ressources publiques.
STATICFILES_DIRS = [BASE_DIR / 'static']  # Localiser les fichiers de l'interface.
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Collecter les ressources pour Gunicorn.
MEDIA_URL = '/media/'  # Exposer les photos contrôlées des catalogues.
MEDIA_ROOT = BASE_DIR / 'media'  # Séparer les médias des sources.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'  # Utiliser des identifiants SQL sur 64 bits.
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['core.authentication.ActiveJWTAuthentication', 'rest_framework.authentication.SessionAuthentication'], 'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'], 'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema', 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination', 'PAGE_SIZE': 30, 'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'], 'DEFAULT_THROTTLE_RATES': {'anon': '100/min', 'user': '300/min', 'auth': '10/min', 'reset': '3/hour'}, 'EXCEPTION_HANDLER': 'core.authentication.exception_handler'}  # Sécuriser l'API par défaut et limiter son usage.
SIMPLE_JWT = {'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15), 'REFRESH_TOKEN_LIFETIME': timedelta(days=7), 'ROTATE_REFRESH_TOKENS': True, 'BLACKLIST_AFTER_ROTATION': True}  # Limiter les jetons et révoquer ceux déjà renouvelés.
SPECTACULAR_SETTINGS = {'TITLE': 'MIAGBO API', 'VERSION': '1.0.0', 'DESCRIPTION': 'Clients, commerces de proximité, modération et abonnements.', 'COMPONENT_SPLIT_REQUEST': True}  # Générer une documentation OpenAPI fidèle aux serializers.
CORS_ALLOWED_ORIGINS = [v for v in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if v]  # Autoriser uniquement les origines explicitement déclarées.
CSRF_TRUSTED_ORIGINS = [v for v in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if v]  # Accepter les formulaires du domaine HTTPS de production.
SESSION_COOKIE_HTTPONLY = True  # Empêcher JavaScript de lire la session.
SESSION_COOKIE_SAMESITE = 'Lax'  # Réduire les envois de cookies depuis un site tiers.
SESSION_COOKIE_SECURE = not DEBUG  # Exiger HTTPS pour les sessions en production.
CSRF_COOKIE_SECURE = not DEBUG  # Protéger également le cookie anti-CSRF.
SECURE_SSL_REDIRECT = not DEBUG  # Rediriger les connexions HTTP en production.
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0  # Demander aux navigateurs de conserver HTTPS.
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG  # Étendre cette règle aux sous-domaines.
SECURE_HSTS_PRELOAD = not DEBUG  # Préparer l'inscription HSTS du domaine.
SECURE_CONTENT_TYPE_NOSNIFF = True  # Empêcher l'interprétation d'un média comme script.
X_FRAME_OPTIONS = 'DENY'  # Bloquer l'intégration de l'application dans un cadre tiers.
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024  # Limiter les corps de requêtes ordinaires.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # Déporter les gros fichiers vers un fichier temporaire.
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')  # Afficher les mails en local sans prétendre les envoyer.
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')  # Lire l'hôte SMTP.
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))  # Choisir le port SMTP.
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')  # Lire le compte SMTP.
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')  # Lire son secret hors du code.
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'  # Chiffrer le transport SMTP.
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'MIAGBO <noreply@localhost>')  # Identifier l'émetteur des alertes.
PUBLIC_URL = os.getenv('PUBLIC_URL', 'http://127.0.0.1:8000')  # Construire les liens de réinitialisation.
PAYMENT_WEBHOOK_SECRET = os.getenv('PAYMENT_WEBHOOK_SECRET', '')  # Vérifier les notifications du futur adaptateur de paiement.
CACHE_REDIS = os.getenv('REDIS_URL', '')  # Activer un cache partagé si Redis est disponible.
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': CACHE_REDIS}} if CACHE_REDIS else {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}  # Partager les limites de débit entre processus en production.
LOGGING = {'version': 1, 'disable_existing_loggers': False, 'handlers': {'console': {'class': 'logging.StreamHandler'}}, 'root': {'handlers': ['console'], 'level': 'INFO'}}  # Envoyer les diagnostics à l'infrastructure sans journaliser de mots de passe.
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')  # Activer Google seulement avec un client OIDC déclaré.
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')  # Conserver le secret du fournisseur côté serveur.
PUSH_ENABLED = os.getenv('PUSH_ENABLED', '0') == '1'  # Ne jamais envoyer de push externes en local par défaut.
EXPO_PUSH_ACCESS_TOKEN = os.getenv('EXPO_PUSH_ACCESS_TOKEN', '')  # Protéger le service Expo si sa sécurité renforcée est activée.
PASSWORD_RESET_TIMEOUT = 3600  # Limiter les liens de récupération à une heure.

if os.getenv('TRUST_PROXY', '0') == '1':  # Activer cette confiance uniquement lorsque l'API n'est pas exposée directement.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Reconnaître HTTPS terminé par Caddy interne.
SIMPLE_JWT['CHECK_REVOKE_TOKEN'] = True  # Invalider les jetons d'accès après un changement de mot de passe.
SPECTACULAR_SETTINGS['ENUM_NAME_OVERRIDES'] = {'UserRoleEnum': [('client', 'Client'), ('vendor', 'Vendeur'), ('admin', 'Administrateur')], 'BroadcastRoleEnum': ['all', 'client', 'vendor']}  # Nommer séparément les rôles de compte et les cibles de diffusion.
if os.getenv('S3_BUCKET'):  # Activer un stockage partagé uniquement lorsqu'un bucket réel est configuré.
    STORAGES = {'default': {'BACKEND':'storages.backends.s3.S3Storage','OPTIONS':{'bucket_name':os.environ['S3_BUCKET'],'endpoint_url':os.getenv('S3_ENDPOINT_URL') or None,'region_name':os.getenv('S3_REGION','us-east-1'),'access_key':os.getenv('S3_ACCESS_KEY') or None,'secret_key':os.getenv('S3_SECRET_KEY') or None,'default_acl':None,'querystring_auth':False,'file_overwrite':False,'custom_domain':os.getenv('S3_CUSTOM_DOMAIN') or None}}, 'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}  # Séparer médias partagés et ressources statiques, sans exposer de clé au navigateur.
SPECTACULAR_SETTINGS['ENUM_NAME_OVERRIDES']['PublicRoleEnum'] = [('client','Client'),('vendor','Vendeur')]  # Distinguer le rôle public d'inscription du rôle administratif et du ciblage de diffusion.
