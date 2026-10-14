from pathlib import Path  # Repérer la racine sans dépendre du dossier courant.
import secrets  # Générer des clés locales cryptographiquement imprévisibles.
root = Path(__file__).resolve().parent.parent  # Construire un chemin absolu stable.
target = root / '.env'  # Garder les secrets dans un fichier ignoré par Git.
if not target.exists():  # Ne jamais écraser une configuration déjà définie.
    content = (root / '.env.example').read_text()  # Partir de l'exemple documenté.
    content = content.replace('GENERER_UNE_CLE_ALEATOIRE_DE_PLUS_DE_50_CARACTERES', secrets.token_urlsafe(64)).replace('GENERER_UN_SECRET_SQL', secrets.token_urlsafe(32))  # Remplacer uniquement les placeholders de secrets.
    target.write_text(content)  # Enregistrer la configuration locale.
    target.chmod(0o600)  # Limiter la lecture au propriétaire du fichier.
    print('Configuration locale créée dans .env, sans afficher les secrets.')  # Confirmer sans divulgation.
else:  # Respecter un fichier de configuration existant.
    print('.env existe déjà : configuration préservée.')  # Expliquer l'idempotence du script.
