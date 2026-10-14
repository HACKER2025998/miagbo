FROM python:3.13-slim AS runtime
# Utiliser une version Python compatible et une image réduite de production.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Éviter les fichiers bytecode et envoyer immédiatement les logs vers le superviseur.
WORKDIR /app
# Placer les commandes et imports dans une racine stable.
COPY requirements.lock.txt ./
# Installer depuis les versions exactes validées pendant la recette locale.
RUN pip install --no-cache-dir -r requirements.lock.txt
# Installer les dépendances Python sans conserver le cache de build.
RUN useradd --create-home --uid 10001 miagbo
# Éviter d'exécuter l'application comme root.
COPY --chown=miagbo:miagbo . .
# Copier le logiciel avec les droits de son utilisateur de service.
RUN mkdir -p media staticfiles && chown miagbo:miagbo media staticfiles && chmod +x scripts/*.sh
# Préparer les points de montage et les scripts de démarrage.
USER miagbo
# Réduire les privilèges du serveur en fonctionnement.
EXPOSE 8000
# Déclarer le port interne, sans l'ouvrir directement dans Compose production.
CMD ["scripts/entrypoint.sh"]
# Démarrer migrations, collecte des ressources et Gunicorn.
