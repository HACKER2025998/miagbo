from django.apps import AppConfig  # Définir l'initialisation explicite du module métier.
class CoreConfig(AppConfig):  # Enregistrer les services MIAGBO auprès de Django.
    name = 'core'  # Identifier le module contenant les modèles.
    def ready(self):  # Charger les extensions après l'initialisation des applications.
        from . import schema  # Enregistrer le schéma JWT sans créer de dépendance circulaire.
