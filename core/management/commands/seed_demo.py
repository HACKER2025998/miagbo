import os  # Lire le mot de passe de démonstration explicitement fourni.
from django.conf import settings  # Refuser les données fictives en production.
from django.core.management.base import BaseCommand, CommandError  # Fournir un outil local reproductible.
from django.db import transaction  # Garder un jeu de démonstration cohérent.
from django.utils import timezone  # Dater le consentement fictif et les essais.
from core.models import User, Category, Vendor, Product, OpeningHour, Subscription, Review, Notification  # Créer les objets nécessaires aux trois parcours.
from core.services import add_months  # Respecter un mois calendaire d'essai.
class Command(BaseCommand):  # Déclarer le chargement de démonstration.
    help = 'Crée des comptes et commerces fictifs à Lomé ; développement uniquement.'  # Empêcher la confusion avec des clients réels.
    @transaction.atomic  # Ne pas laisser de données partielles si une création échoue.
    def handle(self, *args, **options):  # Charger le jeu de données de manière idempotente.
        password = os.getenv('DEMO_PASSWORD', '')  # Exiger un mot de passe choisi par le développeur.
        if not settings.DEBUG or len(password) < 10:  # Refuser production et mot de passe trop court.
            raise CommandError('DEBUG=1 et DEMO_PASSWORD de 10 caractères minimum sont requis.')  # Donner une consigne concrète.
        users = {}  # Garder les comptes créés pour les relations.
        for name, role, first in [('client', 'client', 'Afi'), ('vendeur', 'vendor', 'Kossi'), ('admin', 'admin', 'Équipe')]:  # Couvrir les trois interfaces du projet.
            user, created = User.objects.get_or_create(username=name, defaults={'email': f'{name}@demo.miagbo.test', 'role': role, 'first_name': first, 'consent_at': timezone.now(), 'is_staff': role == 'admin', 'is_superuser': role == 'admin'})  # Ne pas écraser un compte existant.
            if created:  # Définir le secret seulement pour un nouveau compte.
                user.set_password(password); user.save()  # Hacher le mot de passe choisi.
            users[name] = user  # Conserver la relation pour les fixtures.
        categories = [Category.objects.get_or_create(name=name)[0] for name in ['Repas locaux', 'Douceurs', 'Boissons', 'Grillades']]  # Fournir des filtres cohérents avec la restauration locale.
        shops = [('Chez Maman Afi', 'Ayimolou généreux et saveurs maison, au cœur du quartier.', 'Repas locaux', 6.1331, 1.2242, 'Ayimolou', 700), ('Les Douceurs de Lomé', 'Gâteaux moelleux, beignets et petites douceurs pour votre pause.', 'Douceurs', 6.1293, 1.2208, 'Gâteaux maison', 500), ('Le Coin Frais', 'Bissap, jus de gingembre et boissons fraîches préparés chaque matin.', 'Boissons', 6.1354, 1.2172, 'Bissap frais', 300), ('Maquis Les Voisins', 'Grillades du soir et accueil chaleureux entre voisins.', 'Grillades', 6.1268, 1.2277, 'Poulet grillé', 2500), ('La Marmite du Quartier', 'Khom, sauces locales et recettes familiales à partager.', 'Repas locaux', 6.1404, 1.2318, 'Khom et sauce', 600), ('Pause Gourmande', 'Une petite adresse pour les grandes envies de douceurs.', 'Douceurs', 6.1216, 1.2168, 'Beignets sucrés', 200)]  # Utiliser seulement des commerces explicitement fictifs.
        for index, (name, description, category, lat, lng, product_name, price) in enumerate(shops):  # Créer des résultats à différentes distances autour de Lomé.
            owner = users['vendeur'] if index == 0 else User.objects.get_or_create(username=f'demo-vendeur-{index}', defaults={'email': f'commerce{index}@demo.miagbo.test', 'role': 'vendor', 'first_name': 'Commerce fictif'})[0]  # Associer un propriétaire distinct à chaque commerce.
            if index and not owner.has_usable_password():  # Laisser ces comptes secondaires sans authentification de démonstration.
                owner.set_unusable_password(); owner.save()  # Empêcher leur connexion sans secret défini.
            vendor, created = Vendor.objects.get_or_create(owner=owner, defaults={'name': name, 'description': description, 'address': 'Lomé · adresse fictive de démonstration', 'phone': '+22890000000', 'latitude': lat, 'longitude': lng, 'moderation': 'approved'})  # Préparer une carte exploitable sans vrais contacts.
            if created:  # Ne pas réinitialiser les modifications d'une précédente démonstration.
                Subscription.objects.create(vendor=vendor, plan='discovery', end=add_months(timezone.now(), 1))  # Donner les droits initiaux.
                for day in range(7):  # Ouvrir tous les jours selon un planning simple.
                    OpeningHour.objects.create(vendor=vendor, weekday=day, start='06:00', end='23:00')  # Rendre le filtre ouvert testable en journée.
                Product.objects.create(vendor=vendor, category=next(item for item in categories if item.name == category), name=product_name, description='Produit fictif pour démonstration.', price=price)  # Alimenter la recherche par produit.
                if index < 3:  # Préparer quelques exemples d'évaluation.
                    Review.objects.create(author=users['client'], vendor=vendor, rating=5 - index % 2, text='Exemple d’avis fictif : une bonne adresse dans le quartier.')  # Marquer le contenu comme démonstration.
        Notification.objects.get_or_create(user=users['client'], dedupe_key='demo-welcome', defaults={'title': 'Bienvenue dans votre quartier', 'message': 'Les commerces et avis de cette démonstration sont fictifs.'})  # Ne pas doubler le message lors d'un deuxième chargement.
        self.stdout.write(self.style.SUCCESS('Démonstration prête : client, vendeur, admin. Mot de passe : celui fourni dans DEMO_PASSWORD.'))  # Ne jamais afficher le secret lui-même.
