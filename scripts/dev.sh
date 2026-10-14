#!/usr/bin/env bash
set -euo pipefail # Arrêter le démarrage dès qu'une étape essentielle échoue.
cd "$(dirname "$0")/.." # Exécuter depuis la racine, quel que soit le dossier de lancement.
python scripts/bootstrap.py # Créer une configuration locale si nécessaire.
set -a # Exporter les variables lues dans le fichier de confiance local.
source .env # Charger la configuration choisie par l'exploitant.
set +a # Ne plus exporter les variables internes du script.
export DEBUG=1 # Forcer le mode local sans dépendre du DEBUG de l'environnement hôte.
.venv/bin/python manage.py migrate # Appliquer les évolutions avant de servir des pages.
.venv/bin/python manage.py collectstatic --noinput # Préparer aussi les ressources vendues localement.
exec .venv/bin/python manage.py runserver "${MIAGBO_BIND:-127.0.0.1:8000}" # Démarrer un serveur de développement à l'adresse demandée.
