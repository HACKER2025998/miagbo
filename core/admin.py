from django.contrib import admin  # Fournir un back-office robuste avec permissions et historique.
from django.contrib.auth.admin import UserAdmin  # Réutiliser la gestion sécurisée des comptes et groupes.
from django import forms  # Valider les paramètres éditables.
from .models import User, Vendor, Product, Category, OpeningHour, OpeningException, Review, Report, Notification, Subscription, Payment, Audit, SearchEvent, Configuration, Device, PushDelivery, Promotion, SocialIdentity, AlertZone  # Enregistrer les modèles administrés.
from .services import safe_image, audit  # Réutiliser la validation des médias et le journal métier.
admin.site.site_header = 'MIAGBO · Administration'  # Identifier le logiciel dans le back-office.
admin.site.site_title = 'MIAGBO'  # Nommer l'onglet navigateur.
admin.site.index_title = 'Gestion de la plateforme'  # Expliquer le rôle de cet espace.
@admin.register(User)  # Enregistrer les comptes avec l'outil de permissions Django.
class MiagboUserAdmin(UserAdmin):  # Ajouter les propriétés métier sans exposer les mots de passe en clair.
    fieldsets = UserAdmin.fieldsets + (('MIAGBO', {'fields': ('role', 'phone', 'consent_at')}),)  # Afficher rôles et consentements.
    list_display = ['username', 'email', 'role', 'is_active', 'is_staff']  # Faciliter la modération.
    readonly_fields = ['consent_at']  # Ne pas falsifier la date du consentement.
    def get_readonly_fields(self, request, obj=None):  # Empêcher un opérateur de s'attribuer des privilèges supérieurs.
        return self.readonly_fields if request.user.is_superuser else self.readonly_fields + ('is_staff', 'is_superuser', 'groups', 'user_permissions', 'role')  # Réserver les permissions et rôles au superadministrateur.
    def has_add_permission(self, request):  # Réserver la fabrication de comptes administratifs à l'autorité maximale.
        return request.user.is_superuser  # Éviter une création indirecte de privilèges.
    def has_change_permission(self, request, obj=None):  # Protéger les comptes administratifs contre des modérateurs ordinaires.
        return super().has_change_permission(request, obj) and (obj is None or not obj.is_staff or request.user.is_superuser)  # Garder la modération des clients et vendeurs.
    def has_delete_permission(self, request, obj=None):  # Réserver les effacements définitifs à une décision qualifiée.
        return request.user.is_superuser and super().has_delete_permission(request, obj)  # Préserver les historiques financiers face à une erreur de modération.
    def save_model(self, request, obj, form, change):  # Tracer les modifications administratives.
        super().save_model(request, obj, form, change)  # Utiliser les contrôles et hashes standard.
        audit(request.user, 'admin.user.save', obj.pk)  # Ajouter une trace sans secret.
class SafeAdminForm(forms.ModelForm):  # Contrôler les uploads aussi depuis le back-office.
    def clean_photo(self):  # Assainir un fichier nouvellement envoyé.
        photo = self.cleaned_data.get('photo')  # Lire la valeur du formulaire.
        if photo and hasattr(photo, 'content_type'):  # Vérifier uniquement un fichier nouvellement envoyé.
            try:  # Adapter les erreurs du validateur API au formulaire Django.
                return safe_image(photo)  # Réencoder le contenu et éliminer les métadonnées.
            except Exception:  # Présenter une erreur de champ au lieu d'une page serveur.
                raise forms.ValidationError('Photo invalide : JPEG, PNG ou WebP, 5 Mo et 20 mégapixels maximum.')  # Indiquer les limites identiques à l'API.
        return photo  # Réencoder uniquement un nouvel upload.
class TracedAdmin(admin.ModelAdmin):  # Tracer les écritures administratives de manière homogène.
    def save_model(self, request, obj, form, change):  # Intercepter la sauvegarde sans remplacer ses permissions.
        super().save_model(request, obj, form, change)  # Persister la modification validée.
        audit(request.user, 'admin.' + obj._meta.model_name + '.save', obj.pk)  # Garder un audit métier consultable.
    def delete_model(self, request, obj):  # Tracer une suppression unitaire.
        audit(request.user, 'admin.' + obj._meta.model_name + '.delete', obj.pk)  # Enregistrer la cible avant disparition.
        super().delete_model(request, obj)  # Effectuer la suppression autorisée.
    def delete_queryset(self, request, queryset):  # Tracer aussi les suppressions groupées du back-office.
        for obj in queryset:  # Enregistrer chaque cible avant sa suppression.
            audit(request.user, 'admin.' + obj._meta.model_name + '.delete', obj.pk)  # Préserver l'identité des objets retirés.
        super().delete_queryset(request, queryset)  # Exécuter l'action groupée autorisée.
@admin.register(Vendor)  # Administrer les commerces.
class VendorAdmin(TracedAdmin):  # Fournir un registre filtrable.
    form = SafeAdminForm  # Contrôler les médias du commerce.
    list_display = ['name', 'owner', 'moderation', 'status_override', 'views']  # Afficher les principaux états.
    list_filter = ['moderation', 'status_override']  # Faciliter la validation des nouveaux profils.
    search_fields = ['name', 'owner__email']  # Retrouver un dossier par nom ou responsable.
    readonly_fields = ['views', 'created_at']  # Ne pas altérer les métriques.
@admin.register(Product)  # Administrer les contenus de catalogue.
class ProductAdmin(TracedAdmin):  # Fournir un contrôle des produits.
    form = SafeAdminForm  # Réencoder les photos administratives.
    list_display = ['name', 'vendor', 'price', 'available']  # Montrer prix et disponibilité.
    search_fields = ['name', 'vendor__name']  # Faciliter les recherches de contenu.
@admin.register(Payment, Subscription, Audit, SearchEvent, PushDelivery, Promotion, SocialIdentity)  # Exposer les événements financiers et techniques sans édition arbitraire.
class ReadOnlyAdmin(admin.ModelAdmin):  # Imposer les services métier pour les paiements et préserver l'audit.
    def has_add_permission(self, request):  # Interdire la fabrication d'un événement via un formulaire.
        return False  # Exiger le parcours métier.
    def has_change_permission(self, request, obj=None):  # Protéger montants, droits et historique.
        return False  # Autoriser seulement la consultation selon view_permission.
    def has_delete_permission(self, request, obj=None):  # Préserver les traces dans le back-office.
        return False  # Réserver la rétention à une commande d'exploitation documentée.
class ConfigurationForm(forms.ModelForm):  # Encadrer les paramètres qui influencent l'interface.
    def clean(self):  # Vérifier type et limites par clé.
        data = super().clean()  # Appliquer les validations standard.
        key, value = data.get('key'), data.get('value')  # Lire la paire.
        if key == 'radii' and (not isinstance(value, list) or not value or any(type(v) is not int or not 100 <= v <= 20000 for v in value)):  # Refuser un rayon invalide.
            raise forms.ValidationError('radii : liste non vide d’entiers entre 100 et 20 000.')  # Expliquer le format.
        if key == 'default_radius' and (type(value) is not int or not 100 <= value <= 20000):  # Contrôler le rayon initial.
            raise forms.ValidationError('default_radius : entier entre 100 et 20 000.')  # Refuser une valeur dangereuse.
        if key in ['minimum_android', 'minimum_ios'] and not isinstance(value, str):  # Vérifier les versions publiques.
            raise forms.ValidationError('La version minimale doit être une chaîne.')  # Expliquer le type.
        return data  # Accepter les paramètres corrects.
@admin.register(Configuration)  # Centraliser les réglages administratifs.
class ConfigurationAdmin(TracedAdmin):  # Fournir une édition avec validation métier.
    form = ConfigurationForm  # Appliquer les contraintes de configuration.
    list_display = ['key', 'value']  # Afficher les valeurs courantes.
for model in [Category, OpeningHour, OpeningException, Review, Report, Notification, Device, AlertZone]:  # Compléter le back-office pour les ressources métier.
    admin.site.register(model, TracedAdmin)  # Appliquer permissions Django et audit aux écritures.
