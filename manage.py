import os  # Accéder aux variables d'environnement sans inscrire de secret dans le code.
import sys  # Transmettre les arguments de la commande au gestionnaire Django.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # Choisir la configuration commune de MIAGBO.
from django.core.management import execute_from_command_line  # Charger les commandes seulement après la configuration.
execute_from_command_line(sys.argv)  # Exécuter migrate, test, runserver ou une commande métier.
