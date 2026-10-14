import os  # Définir une base isolée avant de charger Django.
import sys  # Ajouter explicitement la racine au chemin des imports.
from pathlib import Path  # Construire les chemins absolus.
root = Path(__file__).resolve().parent.parent  # Repérer le projet depuis le script de test.
sys.path.insert(0,str(root))  # Permettre l'import de config et core.
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')  # Initialiser les paramètres MIAGBO.
if os.getenv('MIAGBO_SQLITE_PATH') != '/tmp/miagbo-e2e.sqlite3':  # Empêcher tout nettoyage d'une base non dédiée.
    raise RuntimeError('La recette exige la base isolée /tmp/miagbo-e2e.sqlite3.')  # Refuser une exécution mal configurée.
Path('/tmp/miagbo-e2e.sqlite3').unlink(missing_ok=True)  # Réinitialiser uniquement le fichier explicitement dédié aux tests.
import django  # Charger le framework après configuration de l'isolation.
django.setup()  # Initialiser les modèles et applications.
from django.core.management import call_command  # Réutiliser les commandes de préparation officielles.
call_command('migrate',verbosity=0)  # Construire un schéma neuf pour les tests.
call_command('seed_demo',verbosity=0)  # Alimenter les comptes et commerces fictifs.
call_command('runserver','127.0.0.1:8011',use_reloader=False,verbosity=0)  # Servir uniquement sur loopback pendant la recette.
