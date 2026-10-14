#!/usr/bin/env sh
set -eu # Arrêter le conteneur si la préparation échoue.
python manage.py migrate --noinput # Appliquer les migrations du service avant l'ouverture.
python manage.py collectstatic --noinput # Alimenter le volume de ressources servi par Caddy.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 30 --access-logfile - --access-logformat '%(m)s %(U)s %(s)s %(L)s' # Utiliser un serveur WSGI de production et des logs standard.
