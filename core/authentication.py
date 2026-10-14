from django.contrib.auth import get_user_model  # Accéder au modèle de compte personnalisé.
from rest_framework_simplejwt.authentication import JWTAuthentication  # Vérifier les signatures des jetons.
from rest_framework_simplejwt.serializers import TokenRefreshSerializer  # Réutiliser rotation et révocation standard.
from rest_framework.exceptions import AuthenticationFailed  # Produire un refus d'authentification cohérent.
class ActiveJWTAuthentication(JWTAuthentication):  # Refuser les jetons de comptes suspendus.
    def get_user(self, validated_token):  # Résoudre l'identité depuis un jeton validé.
        user = super().get_user(validated_token)  # Charger le compte en base.
        if not user.is_active:  # Respecter une suspension même avec un jeton non expiré.
            raise AuthenticationFailed('Compte suspendu.')  # Interdire l'accès immédiatement.
        return user  # Fournir le compte aux permissions métier.
class ActiveRefreshSerializer(TokenRefreshSerializer):  # Empêcher le renouvellement d'un compte suspendu.
    def validate(self, attrs):  # Ajouter le contrôle aux validations JWT.
        token = self.token_class(attrs['refresh'])  # Vérifier le jeton refresh reçu.
        user = get_user_model().objects.filter(pk=token['user_id'], is_active=True).first()  # Rechercher un compte encore autorisé.
        if not user:  # Refuser un compte supprimé ou suspendu.
            raise AuthenticationFailed('Compte indisponible.')  # Expliquer le refus sans divulgation.
        return super().validate(attrs)  # Effectuer la rotation et la mise sur liste noire.
def exception_handler(exc, context):  # Stabiliser le traitement des erreurs d'API.
    from rest_framework.views import exception_handler as drf_handler  # Importer tardivement pour éviter une dépendance circulaire.
    from django.db import IntegrityError  # Identifier un conflit concurrent de contrainte.
    from rest_framework.response import Response  # Fournir une erreur métier au lieu d'une erreur serveur.
    if isinstance(exc, IntegrityError):  # Traiter proprement les doublons concurrents.
        return Response({'detail': 'Conflit avec une donnée existante ; actualisez puis réessayez.'}, status=409)  # Ne pas exposer la requête SQL.
    return drf_handler(exc, context)  # Garder codes HTTP et messages de validation standards.
