#!/usr/bin/env bash
set -euo pipefail # Interrompre une sauvegarde partielle plutôt que produire un faux succès.
cd "$(dirname "$0")/.." # Trouver Compose depuis n'importe quel dossier.
mkdir -p backups # Créer le dossier ignoré par Git.
chmod 700 backups # Limiter l'accès aux données exportées.
filename="backups/miagbo-$(date -u +%Y%m%dT%H%M%SZ).dump" # Nommer la sauvegarde avec un instant UTC unique.
docker compose exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$filename" # Produire un dump binaire PostgreSQL sans mot de passe dans la commande.
chmod 600 "$filename" # Protéger le fichier contenant les données personnelles.
test -s "$filename" # Refuser un dump vide.
printf 'Sauvegarde créée : %s\n' "$filename" # Donner le chemin concret pour vérifier et transférer l'archive.
