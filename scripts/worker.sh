#!/usr/bin/env sh
set -u # Refuser une variable non déclarée sans interrompre les retries de worker.
while true; do # Maintenir les tâches de maintenance dans leur conteneur dédié.
  python manage.py nearby_alerts # Calculer les nouveautés dans les zones clientes consenties.
  python manage.py subscriptions_tick # Envoyer les rappels d'abonnements idempotents.
  python manage.py purge_searches # Respecter la rétention des tendances de recherche.
  python manage.py flushexpiredtokens # Purger les anciens tokens JWT expirés.
  if [ "${PUSH_ENABLED:-0}" = "1" ]; then # Contacter Expo uniquement après activation explicite.
    python manage.py send_push # Envoyer et vérifier les notifications distantes configurées.
  fi # Terminer le traitement optionnel du push.
  sleep 60 # Espacer les vérifications et permettre la reprise après une panne externe.
done # Répéter jusqu'à l'arrêt du conteneur par l'exploitant.
