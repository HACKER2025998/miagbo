from django.contrib.auth import logout  # Révoquer une session devenue interdite.
class ActiveUserMiddleware:  # Vérifier les suspensions pour les navigateurs déjà connectés.
    def __init__(self, get_response):  # Recevoir le middleware suivant.
        self.get_response = get_response  # Conserver la chaîne Django.
    def __call__(self, request):  # Contrôler chaque requête.
        if request.user.is_authenticated and not request.user.is_active:  # Identifier une session suspendue.
            logout(request)  # Effacer les droits de la session.
        response = self.get_response(request)  # Obtenir la réponse après les contrôles de session.
        response['Referrer-Policy'] = 'no-referrer'  # Ne pas transmettre un lien de récupération aux destinations externes.
        if request.path == '/':  # Appliquer une politique stricte au frontend sans casser l'explorateur Swagger séparé.
            response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"  # Bloquer les scripts injectés et permettre les images CDN et styles de carte.
        return response  # Continuer avec des protections explicites du navigateur.
