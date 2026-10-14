import os  # Lire la configuration du processus web.
from django.core.wsgi import get_wsgi_application  # Obtenir le serveur WSGI Django.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # Choisir les paramètres MIAGBO.
application = get_wsgi_application()  # Exposer l'application à Gunicorn.
