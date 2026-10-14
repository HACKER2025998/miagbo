from django.conf import settings  # Détecter l'environnement local.
from django.conf.urls.static import static  # Servir les médias uniquement en développement.
from django.contrib import admin  # Exposer le back-office avancé protégé.
from django.urls import path, include  # Composer les routes de l'application.
from rest_framework.routers import DefaultRouter  # Générer les routes REST des ressources.
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView  # Exposer l'authentification API pour les futurs clients natifs.
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView  # Servir le contrat OpenAPI et son explorateur.
from core.oauth import google_start, google_callback  # Charger les deux étapes de connexion sociale.
from core import views  # Charger les fonctions métier.
from core.authentication import ActiveRefreshSerializer  # Vérifier les comptes actifs lors du renouvellement.
from core.webhooks import payment_webhook  # Réserver une route signée au paiement externe.
class RefreshView(TokenRefreshView):  # Renforcer le renouvellement standard.
    serializer_class = ActiveRefreshSerializer  # Refuser un compte suspendu.
class LoginTokenView(TokenObtainPairView):  # Appliquer une limitation dédiée aux connexions API.
    throttle_classes = [views.AuthThrottle]  # Freiner les attaques par mot de passe.
router = DefaultRouter()  # Définir les ressources sous /api/v1/.
router.register('vendors', views.VendorViewSet, basename='vendor')  # Rechercher et gérer les commerces.
router.register('products', views.ProductViewSet, basename='product')  # Modifier son catalogue.
router.register('reviews', views.ReviewViewSet, basename='review')  # Déposer un avis ou répondre.
router.register('reports', views.ReportViewSet, basename='report')  # Signaler un abus.
router.register('notifications', views.NotificationViewSet, basename='notification')  # Lire sa boîte de réception.
urlpatterns = [path('api/v1/alerts/', views.alerts), path('api/v1/vendors/<int:pk>/promote/', views.promote),path('auth/google/start/', google_start), path('auth/google/callback/', google_callback), path('', views.index), path('backoffice/', admin.site.urls), path('api/v1/auth/register/', views.register), path('api/v1/auth/login/', views.session_login), path('api/v1/auth/logout/', views.session_logout), path('api/v1/auth/token/', LoginTokenView.as_view()), path('api/v1/auth/refresh/', RefreshView.as_view()), path('api/v1/auth/revoke/', TokenBlacklistView.as_view()), path('api/v1/auth/password-reset/', views.password_reset), path('api/v1/auth/password-confirm/', views.password_confirm), path('api/v1/me/', views.me), path('api/v1/account/', views.account), path('api/v1/categories/', views.categories), path('api/v1/subscriptions/plans/', views.plans), path('api/v1/favorites/', views.favorites), path('api/v1/devices/', views.devices), path('api/v1/configuration/', views.configuration), path('api/v1/health/', views.health), path('api/v1/admin/dashboard/', views.admin_dashboard), path('api/v1/admin/users/', views.admin_users), path('api/v1/admin/users/<int:pk>/status/', views.admin_user_status), path('api/v1/admin/vendors/<int:pk>/decision/', views.admin_vendor), path('api/v1/admin/reports/<int:pk>/resolve/', views.admin_report), path('api/v1/admin/payments/<int:pk>/decision/', views.admin_payment), path('api/v1/admin/broadcast/', views.admin_broadcast), path('api/v1/admin/export/', views.admin_export), path('api/v1/payments/webhook/', payment_webhook), path('api/v1/schema/', SpectacularAPIView.as_view()), path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema')), path('api/v1/', include(router.urls))]  # Relier chaque parcours à son contrôle d'accès.
urlpatterns[-3] = path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema')  # Nommer le contrat utilisé par Swagger.
if settings.DEBUG:  # Ne pas utiliser Django pour servir les médias en production.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # Permettre le catalogue photo local.
