from django.db import migrations  # Définir une évolution reproductible de la base.
def install_postgis(apps, schema_editor):  # Activer le moteur géographique uniquement sur PostgreSQL.
    if schema_editor.connection.vendor == 'postgresql':  # Conserver la compatibilité SQLite pour les tests rapides.
        schema_editor.execute('CREATE EXTENSION IF NOT EXISTS postgis')  # Activer les fonctions ST_DWithin et le type geography.
        schema_editor.execute('CREATE INDEX vendor_geography_gist ON core_vendor USING GIST ((ST_SetSRID(ST_MakePoint(longitude, latitude),4326)::geography))')  # Indexer l'expression exacte utilisée par la recherche.
def uninstall_index(apps, schema_editor):  # Permettre un rollback sans retirer une extension partagée.
    if schema_editor.connection.vendor == 'postgresql':  # Ne pas envoyer du SQL PostGIS à SQLite.
        schema_editor.execute('DROP INDEX IF EXISTS vendor_geography_gist')  # Retirer uniquement notre index.
class Migration(migrations.Migration):  # Enregistrer l'évolution géographique.
    dependencies = [('core', '0001_initial')]  # Exiger la table des commerces avant son index.
    operations = [migrations.RunPython(install_postgis, uninstall_index)]  # Exécuter une migration conditionnelle et réversible.
