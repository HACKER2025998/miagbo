from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme  # Réutiliser le contrat Bearer standard de SimpleJWT.
class ActiveJWTScheme(SimpleJWTScheme):  # Décrire notre contrôle supplémentaire sans modifier le protocole de token.
    target_class = 'core.authentication.ActiveJWTAuthentication'  # Associer l'extension à l'authentificateur utilisé.
    name = 'jwtAuth'  # Exposer un schéma Bearer unique dans OpenAPI.
