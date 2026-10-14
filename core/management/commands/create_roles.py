from django.contrib.auth.models import Group, Permission  # Utiliser les permissions Django plutôt qu'un simple libellé de rôle.
from django.core.management.base import BaseCommand  # Exposer un initialiseur reproductible.
from django.db import transaction  # Mettre à jour les groupes de manière cohérente.
class Command(BaseCommand):  # Déclarer les groupes d'exploitation du MVP.
    help = 'Crée les groupes Modération, Finance et Communication sans attribuer de compte automatiquement.'  # Préserver l'attribution explicite par le responsable.
    @transaction.atomic  # Éviter un groupe partiellement configuré en cas d'échec.
    def handle(self, *args, **options):  # Initialiser les autorisations minimales de chaque équipe.
        roles = {'Modération':['view_user','change_user','view_vendor','change_vendor','view_review','change_review','view_report','change_report','view_audit'],'Finance':['view_user','view_payment','change_payment','view_subscription','view_audit'],'Communication':['view_user','view_notification','add_notification']}  # Définir des responsabilités séparées.
        for name, codenames in roles.items():  # Configurer chaque groupe sans y ajouter d'utilisateur.
            group, _ = Group.objects.get_or_create(name=name)  # Réutiliser un groupe existant.
            group.permissions.set(Permission.objects.filter(content_type__app_label='core',codename__in=codenames))  # Appliquer la liste blanche exacte de permissions.
        self.stdout.write(self.style.SUCCESS('Groupes créés. Attribuez-les à des comptes staff depuis un superadministrateur.'))  # Expliquer l'étape d'exploitation volontaire.
