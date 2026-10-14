# MIAGBO — les saveurs, tout près

MIAGBO permet de découvrir des commerces de restauration à proximité d’un point choisi, de consulter leur catalogue et leurs horaires, de conserver des favoris et de partager un avis. Le commerçant dispose de son espace de gestion ; l’équipe MIAGBO dispose de fonctions de validation, de modération et de suivi des abonnements.

Cette livraison contient une application exécutable et des tests, pas uniquement des maquettes. Elle constitue une version de travail pour recette. Une mise en production commerciale et une publication dans les stores demandent les configurations et validations décrites ci-dessous. Aucun paiement réel n’est simulé comme réussi.

## 1. Lire le projet dans le bon ordre

| Votre objectif | Document |
| --- | --- |
| Installer, démarrer et utiliser le logiciel | Ce README |
| Comprendre les documents du client et les arbitrages | [Spécifications et couverture](docs/SPECIFICATIONS.md) |
| Comprendre les données, le code et les protections | [Architecture détaillée](docs/ARCHITECTURE.md) |
| Déployer, sauvegarder, restaurer et traiter un incident | [Guide d’exploitation](docs/EXPLOITATION.md) |
| Rejouer les vérifications et connaître les limites de validation | [Recette](docs/RECETTE.md) |
| Lire le contrat complet des routes | [OpenAPI](docs/openapi.yaml), ou `/api/v1/docs/` après démarrage |
| Retrouver le contenu fourni par le client | [CDC intégral extrait](docs/sources/cahier-des-charges.txt) et [présentation intégrale extraite](docs/sources/presentation.txt) |

Les documents Word ont été lus, tableaux compris. Leurs en-têtes, pieds de page et parties textuelles annexes ont également été extraits. Ils sont traités comme des expressions de besoins, distinctes de votre demande de développement et d’explication du code. Le nom « Asssiooo » à la fin du CDC est une incohérence de référence ; le logiciel livré est nommé MIAGBO.

### Aperçus réels

Les captures proviennent des parcours Playwright exécutés sur l’application :

- [Interface desktop](docs/screenshots/desktop.png).
- [Interface mobile responsive](docs/screenshots/mobile.png).

Les commerces, avis et téléphones de démonstration sont fictifs. Les dessins de plats sont des illustrations vectorielles, pas des photographies de commerces réels.

## 2. Ce que vous pouvez utiliser

### Client

- Explorer sans compte les commerces validés, par mot-clé, catégorie, rayon et disponibilité.
- Utiliser un point manuel ou demander volontairement le GPS. Le centre de Lomé est le point initial annoncé ; l’application ne le présente pas comme votre GPS.
- Afficher une liste ou une carte. Les tuiles externes sont chargées après un choix explicite.
- Consulter produits disponibles, photos, prix en FCFA, horaires, exceptions et avis.
- Ouvrir un itinéraire dans Google Maps, ou appeler le commerce.
- Créer un compte, se connecter par identifiant, email ou téléphone et récupérer le compte par email.
- Enregistrer des favoris, déposer un avis, signaler un commerce ou un avis.
- Consulter les notifications, exporter ses données et désactiver son compte.
- Activer séparément une zone d’alerte privée pour découvrir des commerces récemment inscrits et recevoir les mises en avant proches ; supprimer cette zone à tout moment.

### Commerçant

- Soumettre son commerce à validation, capturer son GPS et modifier ses coordonnées manuellement.
- Ajouter, modifier et supprimer des produits ; uploader des photos vérifiées ; gérer les ruptures de stock.
- Définir plusieurs plages par jour, des horaires passant minuit et des exceptions datées.
- Choisir les horaires automatiques ou une dérogation ouvert/fermé de douze heures.
- Consulter ses vues, sa note, ses avis et les apparitions en recherche selon sa formule.
- Répondre aux avis et choisir une formule avec devis et crédit au prorata.
- Suivre les demandes de règlement et les échéances. Une demande n’active aucun droit payant.
- Avec Croissance ou Performance, diffuser des mises en avant aux zones proches ayant donné leur consentement.

### Administration

- Valider ou rejeter les commerces avec un motif, suspendre et réactiver les comptes ordinaires.
- Traiter les signalements et décider explicitement d’un retrait de contenu.
- Confirmer un reçu vérifié ou rejeter une demande de règlement, avec historique et audit.
- Consulter des statistiques, rechercher les comptes et exporter un CSV protégé contre les formules de tableur.
- Diffuser des messages aux boîtes de réception, globalement ou par rôle.
- Gérer catégories, configurations, utilisateurs, groupes et autorisations dans le back-office avancé Django.

## 3. Choix techniques et limites à connaître

| Élément | Choix livré |
| --- | --- |
| Serveur | Python, Django 5.2 LTS, Django REST Framework |
| Interface web | HTML, CSS et JavaScript locaux, responsive, consommant l’API REST |
| Mobile | React Native / Expo, coque WebView avec GPS natif, reprise réseau et liens externes contrôlés |
| Base locale | SQLite pour démarrer sans infrastructure |
| Base production | PostgreSQL 16 + PostGIS et index GiST |
| Cache | Redis optionnel, activé dans Compose production |
| Authentification web/mobile livré | Session serveur, cookie HttpOnly, CSRF |
| Authentification des futurs clients API | JWT access/refresh, rotation et révocation |
| Connexion sociale | Google OIDC sur le web, activable avec les credentials réels |
| Cartographie | Leaflet local, tuiles OpenStreetMap après choix explicite |
| Médias | Fichiers réencodés sur volume persistant ; stockage S3 compatible optionnel |
| Notifications distantes | Transport Expo vers FCM/APNs, à configurer ; boîte interne toujours disponible |
| Exécution production | Gunicorn, Docker Compose, proxy HTTPS Caddy, worker distinct |

Le frontend n’utilise pas React/Next : ces technologies étaient proposées comme recommandations, pas comme une obligation exclusive. Le JavaScript natif limite l’outillage et permet de partager l’interface avec le conteneur mobile. Les fichiers sont séparés par responsabilité côté serveur ; une séparation future du gros fichier d’interface est possible sans changer l’API.

Le client mobile dépend du site HTTPS déployé. Il n’offre pas de catalogue hors connexion. La version Expo retenue supporte Android 7+ et iOS 15.1+ : elle couvre Android 8, mais **ne couvre pas l’exigence iOS 14** du CDC. Il faut faire valider iOS 15.1 minimum ou financer une implémentation adaptée à iOS 14. Les binaires Android/iOS et les stores n’ont pas été publiés. La connexion Google est masquée dans la coque mobile : un parcours OAuth système avec retour natif reste à développer avant de la proposer sur mobile.

Le checkout Mobile Money/carte dépend du fournisseur et d’un contrat marchand non fournis. Le logiciel propose un processus manuel fonctionnel et un contrat de webhook signé pour un futur adaptateur. Ce contrat n’est pas présenté comme le webhook natif de tous les opérateurs. Aucun fournisseur ne peut être encaissé sans son intégration réelle.

## 4. Installation locale, pas à pas

### Prérequis

- Python 3.13 ou 3.14 ; la recette locale a utilisé Python 3.14 et l’image Docker utilise 3.13.
- `uv` pour créer l’environnement Python, ou un environnement virtuel standard avec `pip`.
- Node.js 22 LTS ou version compatible avec Expo ; la recette locale a utilisé Node 24.
- npm. Docker reste facultatif pour la démonstration SQLite.

Placez-vous dans le dossier du projet. Les commandes suivantes sont prévues pour Bash/Zsh sous Linux/macOS. Sous Windows, utilisez WSL pour reproduire exactement ce guide.

```bash
uv venv .venv # Créer un environnement Python propre au projet.
uv pip install --python .venv/bin/python -r requirements.lock.txt # Installer les versions exactes de la recette.
npm ci # Installer Leaflet et les outils de vérification depuis le lockfile.
npm run vendor # Reconstituer les ressources cartographiques locales si nécessaire.
python scripts/bootstrap.py # Créer .env avec des secrets locaux aléatoires sans écraser un fichier existant.
./scripts/dev.sh # Appliquer les migrations, collecter les ressources et lancer le serveur local.
```

Si vous n’utilisez pas uv, remplacez ses deux premières commandes par :

```bash
python3 -m venv .venv # Créer l’environnement avec l’outil standard Python.
.venv/bin/python -m pip install -r requirements.lock.txt # Installer les dépendances verrouillées.
```

Ouvrez **http://127.0.0.1:8000/**. L’écran fonctionne sans compte, mais il n’affiche aucun commerce tant que la base est vide. C’est normal : les vraies inscriptions doivent être validées.

Ne lancez pas le frontend en double-cliquant sur `templates/index.html` : Django doit le rendre pour fournir la session, les ressources et le jeton anti-CSRF. `.env` n’est pas chargé implicitement par `manage.py` ; `scripts/dev.sh` le charge. Pour une commande de gestion lancée séparément, exportez d’abord ses variables.

### Charger les données fictives

Dans un deuxième terminal, à la racine :

```bash
set -a # Exporter les variables de configuration lues ensuite.
source .env # Charger le fichier local de confiance, jamais un fichier téléchargé non vérifié.
set +a # Rétablir le comportement normal des variables shell.
export DEBUG=1 # Activer explicitement le développement, même si le terminal utilisait DEBUG=0.
export DEMO_PASSWORD='DemoMiagbo2026!' # Choisir le mot de passe des trois nouveaux comptes fictifs.
.venv/bin/python manage.py seed_demo # Créer six commerces fictifs, leurs produits et les comptes de démonstration.
.venv/bin/python manage.py create_roles # Initialiser les groupes d’exploitation sans leur attribuer de compte.
```

| Identifiant | Parcours | Email fictif |
| --- | --- | --- |
| `client` | Client | `client@demo.miagbo.test` |
| `vendeur` | Commerçant du commerce Chez Maman Afi | `vendeur@demo.miagbo.test` |
| `admin` | Superadministrateur de démonstration | `admin@demo.miagbo.test` |

Le mot de passe est la valeur de `DEMO_PASSWORD`. La commande ne l’affiche pas. Elle ne change pas le mot de passe d’un compte existant et ne réinitialise pas vos modifications. Elle refuse de fonctionner si `DEBUG=0`. N’utilisez jamais ces comptes fictifs sur une plateforme publique.

### Créer votre vrai compte administrateur local

```bash
DEBUG=1 .venv/bin/python manage.py createsuperuser # Saisir interactivement un identifiant simple, un email et un mot de passe personnel.
```

Le statut staff et les permissions Django autorisent l’administration ; le simple champ métier `role=admin` n’accorde aucun droit. Un superutilisateur CLI peut avoir le rôle métier par défaut tout en disposant de ses permissions réelles. Le guide d’exploitation explique la séparation des groupes.

## 5. Découvrir l’application en dix minutes

### Scénario client

1. Ouvrez l’accueil. Le bandeau de position indique le centre de Lomé.
2. Recherchez « gâteaux » avec un rayon de 2 km. La démonstration retourne Les Douceurs de Lomé.
3. Activez une catégorie, le filtre ouvert ou un autre rayon. Une recherche vide affiche une explication et permet de réinitialiser les filtres.
4. Cliquez sur le nom du point de départ pour saisir des coordonnées ou demander le GPS. Sur un téléphone, le GPS navigateur exige généralement HTTPS ; localhost est une exception de développement.
5. Ouvrez une fiche : le catalogue, les horaires, les avis et l’itinéraire sont consultables.
6. Connectez-vous comme `client`, puis ajoutez un favori. Rechargez la page pour constater sa persistance côté serveur.
7. Publiez un avis sur un commerce que ce compte n’a pas encore évalué. Les trois premiers commerces possèdent déjà un avis fictif du compte client.
8. Ouvrez Notifications. Une réponse du commerçant apparaît dans votre boîte.
9. Dans Mon compte, exportez vos données ou configurez une zone d’alerte. Cette dernière conserve des coordonnées uniquement après son consentement spécifique.
10. Effacez l’historique local si vous ne souhaitez pas garder les mots-clés sur cet appareil.

Les distances affichées sont arrondies en mètres ou kilomètres et calculées à vol d’oiseau. Elles ne sont ni une durée de déplacement ni une distance routière. Un commerce Premium peut précéder un commerce plus proche dans le même rayon ; le badge signale sa mise en avant.

### Scénario vendeur

1. Connectez-vous comme `vendeur` ou créez un compte commerçant distinct.
2. Pour un nouveau compte, complétez le formulaire d’enrôlement. Le commerce reste invisible au public jusqu’à validation administrative.
3. Dans Catalogue, ajoutez un produit avec catégorie, prix entier en FCFA, description, disponibilité et photo facultative.
4. Le serveur limite le fichier à 5 Mo et 20 mégapixels. Il accepte JPEG/PNG/WebP, le réencode en JPEG, réduit sa taille et retire les métadonnées EXIF.
5. Dans Horaires, ajoutez les plages de la semaine et enregistrez. Plusieurs plages par jour sont acceptées. `22:00 → 02:00` signifie une fermeture le lendemain.
6. Dans Exceptions, définissez une fermeture de jour férié. Une exception ouverte utilise une plage située dans la même journée.
7. Le sélecteur de statut permet une dérogation de douze heures. Ensuite, les horaires reprennent automatiquement.
8. Dans Avis clients, répondez aux commentaires reçus. La réponse génère une notification au client.
9. Dans Abonnement, demandez un devis puis une demande de règlement. La formule ne change pas encore.
10. Après vérification du reçu par un administrateur, le nouvel abonnement devient actif. L’historique conserve la référence et le montant.

Une modification du profil commercial remet le commerce en attente de validation ; la simple gestion du catalogue et des horaires conserve son état de publication. Le catalogue comporte aussi les produits conservés après rétrogradation, même s’ils ne sont plus tous visibles publiquement.

### Scénario administration

1. Connectez-vous comme `admin`. Le tableau de bord affiche les dossiers accessibles.
2. Validez un commerce en indiquant le motif de la décision. Vérifiez son apparition dans la recherche publique.
3. Rejetez un profil trompeur ou suspendez son propriétaire : la publication disparaît immédiatement.
4. Examinez un signalement. La clôture n’implique pas automatiquement un retrait ; cochez explicitement le masquage si votre décision le justifie.
5. Vérifiez un paiement auprès du fournisseur ou sur un reçu probant, puis saisissez sa référence externe. Un même reçu confirmé ne peut pas activer deux transactions.
6. Consultez `/backoffice/` pour gérer catégories, hiérarchie, configurations et groupes. Les objets financiers et le journal d’audit y sont consultables mais non modifiables arbitrairement.
7. Téléchargez un export CSV seulement si vous êtes habilité à traiter les données personnelles.

## 6. Abonnements : règles exactes

| Formule | Durée | Prix total | Catalogue | Priorité |
| --- | --- | --- | --- | --- |
| Découverte | Un mois initial gratuit | 0 FCFA | 10 produits | Standard |
| Essentiel | 3 mois | 1 500 FCFA | 30 produits | Standard |
| Croissance | 6 mois | 3 000 FCFA | Illimité | Priorité à proximité comparable |
| Performance | 12 mois | 5 000 FCFA | Illimité | Priorité dans le rayon, badge Premium |

La durée utilise des mois calendaires. Le 31 janvier + un mois devient le dernier jour de février. L’essai démarre à l’enrôlement, comme indiqué dans le CDC ; une validation tardive consomme donc une partie de l’essai. L’équipe peut faire évoluer ce choix avant commercialisation.

Le changement immédiat est un upgrade. Le crédit correspond à la fraction non consommée du montant réellement payé de la période courante, arrondie au FCFA. Le prix et les droits de référence sont figés lors de la demande pendant 24 heures. Si les droits ont entre-temps été remplacés, la confirmation est refusée. Une seule demande récente peut rester en attente par commerce.

La reconduction de la même formule et le passage à une formule inférieure se font après expiration dans cette version. Il n’y a ni prélèvement automatique, ni remboursement, ni paiement de repas. Le catalogue n’est jamais détruit par une expiration : le repli permet de publier dix produits disponibles, dans l’ordre stable des identifiants. Les produits au-delà restent accessibles au propriétaire.

Croissance permet une campagne de proximité par mois civil UTC. Performance ne limite pas le nombre mensuel de demandes, mais chaque client reçoit au plus un message du même commerce par jour. Le consentement à une zone d’alerte est requis ; un client qui n’a pas choisi de zone ne reçoit pas de ciblage géographique.

Les prestations humaines citées dans le CDC — support prioritaire, accompagnement, accès anticipé — demandent une organisation opérationnelle. Le code ne prétend pas fournir une équipe de support inexistante.

## 7. Application Android/iOS

Le dossier `mobile/` contient le projet natif et son lockfile. L’API et le site doivent être accessibles depuis le téléphone.

```bash
npm ci --prefix mobile # Installer les dépendances mobiles exactes.
cd mobile # Utiliser le dossier du projet Expo pour les commandes natives.
export EXPO_PUBLIC_MIAGBO_URL='http://10.0.2.2:8000' # Pointer le serveur hôte depuis l'émulateur Android uniquement en développement.
npm start # Démarrer Metro et suivre les instructions Expo.
```

Pour un téléphone physique, utilisez l’IP locale du serveur et lancez le backend avec une adresse accessible : `MIAGBO_BIND=0.0.0.0:8000 ./scripts/dev.sh`. Ajoutez cette IP à `ALLOWED_HOSTS` dans `.env` et vérifiez le pare-feu. Cette ouverture est réservée à votre réseau de développement. Pour un iOS Simulator sur le même Mac, utilisez l’adresse locale appropriée. Pour une build distribuée, utilisez exclusivement une URL HTTPS réelle.

Le GPS natif ne suit pas la position en arrière-plan. Le pont n’accepte que les messages de l’origine MIAGBO configurée, avec les types autorisés. Les cartes externes, `tel:` et `mailto:` sont ouverts par le système. Les autres origines ne peuvent pas exécuter le pont GPS. La coque refuse une URL HTTP dans une build de production.

Pour préparer un binaire, après configuration d’un compte Expo/EAS et des identifiants de bundle :

```bash
npx expo run:android # Générer et compiler Android avec un SDK Android installé.
npx expo run:ios # Générer et compiler iOS sur macOS avec Xcode installé.
npx eas-cli build --profile preview --platform android # Produire un APK interne dans votre compte EAS configuré.
npx eas-cli build --profile production --platform all # Construire les binaires signés après configuration des comptes développeur.
```

`eas.json` est fourni, mais aucun compte marchand, compte Apple/Google, certificat de signature ou projet EAS ne peut être inventé. Les identifiants `com.miagbo.app` doivent être vérifiés avant réservation dans les stores. Une coque principalement WebView peut nécessiter des améliorations natives supplémentaires pour satisfaire la revue des stores ; leur acceptation n’est pas garantie.

## 8. Brancher les services externes

### Email

En développement, les messages et liens de reset apparaissent dans le terminal du serveur. Pour envoyer réellement les mails, configurez un SMTP et remplacez `EMAIL_BACKEND` par `django.core.mail.backends.smtp.EmailBackend`. Renseignez hôte, port, utilisateur, secret, TLS et adresse d’expédition. `PUBLIC_URL` doit correspondre au domaine HTTPS public.

Les liens de récupération expirent après une heure et deviennent inutilisables après changement du mot de passe. Le serveur répond avec le même message pour un email présent ou absent. Les anciens refresh tokens sont révoqués après récupération ; les access tokens vérifient aussi l’empreinte du mot de passe.

### Google sur le web

Créez un client OAuth de type application web, configurez `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` et le callback exact `https://votre-domaine/auth/google/callback/`. Le bouton n’apparaît qu’après configuration. Le parcours vérifie state, nonce, PKCE, signature RS256, audience, expiration, émetteur et email vérifié. Un email identique ne fusionne pas automatiquement les comptes : il faut d’abord prouver la possession du compte MIAGBO, puis lier Google depuis Mon compte.

### Notifications mobiles

Configurez les credentials FCM v1/APNs dans votre projet Expo, `EXPO_PUBLIC_EAS_PROJECT_ID` dans le mobile, et `PUSH_ENABLED=1` côté serveur. Ajoutez `EXPO_PUSH_ACCESS_TOKEN` si la sécurité d’accès Expo est activée. Construisez une version de développement ou distribuable adaptée ; ne comptez pas sur Expo Go pour valider ce parcours distant.

Dans le mobile, Mon compte propose alors l’activation des notifications. La permission système est demandée après ce clic. Le terminal est associé à la session connectée. La déconnexion retire les terminaux associés au compte pour éviter des envois après fermeture de session ; réactivez-les ensuite sur les appareils souhaités.

Le worker conserve une tâche par message et terminal, vérifie les tickets puis les reçus, borne les reprises et vérifie que le terminal appartient toujours au destinataire. Un reçu fournisseur ne signifie pas que l’utilisateur a lu le message. La boîte interne reste la référence. Les erreurs et les cas de reprise sont décrits dans le guide d’exploitation.

### Paiement

Le processus manuel est utilisable sans API fournisseur. Pour automatiser l’encaissement, choisissez l’opérateur, implémentez la création réelle du checkout, vérifiez les webhooks natifs de cet opérateur puis traduisez un règlement définitivement confirmé vers notre contrat signé. Le détail des en-têtes, du HMAC et des champs est dans [Architecture](docs/ARCHITECTURE.md). Ne reliez jamais un simple retour navigateur à une activation d’abonnement.

### Stockage S3 et cartographie

Le déploiement par défaut conserve les photos dans un volume persistant. Un backend S3 compatible est prévu via les variables `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` et éventuellement `S3_CUSTOM_DOMAIN` ; voir le guide d’exploitation. Il ne faut pas autoriser l’écriture publique du bucket. Les objets doivent être lisibles par le CDN ou le mécanisme de diffusion retenu.

Les tuiles publiques OpenStreetMap servent la recette et un trafic modéré. Pour une exploitation soutenue, configurez un fournisseur adapté ou votre propre infrastructure de tuiles et respectez sa politique d’usage. Le code Leaflet est livré localement avec sa licence.

## 9. Vérifier le logiciel

```bash
DEBUG=1 .venv/bin/python manage.py check # Vérifier la configuration et les modèles.
DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run # Détecter une évolution de modèle sans migration.
DEBUG=1 .venv/bin/python -m coverage run --source=core,config manage.py test # Exécuter la suite backend sur une base isolée.
.venv/bin/python -m coverage report --fail-under=70 # Mesurer la couverture du code applicatif hors tests et migrations générées.
DEBUG=1 .venv/bin/python manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn # Régénérer et valider le contrat d'API.
npm run check:js # Vérifier la syntaxe de l'interface web.
npx playwright install chromium # Installer le navigateur de recette si nécessaire.
npm run test:e2e # Vérifier les parcours desktop et mobile avec base SQLite dédiée dans /tmp.
npm --prefix mobile run check # Vérifier le typage strict du code natif.
```

Les tests E2E réinitialisent uniquement `/tmp/miagbo-e2e.sqlite3`. Ils ne doivent pas être pointés vers une base personnelle. Le serveur de recette utilise le port 8011. Les traces d’échec et résultats sont ignorés par Git ; les captures de démonstration sont dans `docs/screenshots/`.

Pour vérifier PostGIS, utilisez une base de test isolée avec un compte autorisé à créer la base de test et l’extension PostGIS :

```bash
DEBUG=1 DB_HOST=127.0.0.1 DB_PORT=55432 DB_PASSWORD=miagbo-test-only .venv/bin/python manage.py test # Rejouer la même suite sur PostgreSQL/PostGIS isolé.
```

Cette commande suppose que votre service de recette écoute déjà sur ce port avec les identifiants correspondants. N’utilisez pas les credentials d’une production. La CI fournit elle-même son service éphémère.

## 10. Où modifier quoi ?

| Besoin | Fichier principal |
| --- | --- |
| Tarifs, quotas, prorata, horaires, images | `core/services.py` |
| Tables et contraintes | `core/models.py`, puis nouvelle migration |
| Champs acceptés et validations | `core/serializers.py` |
| Routes métier et contrôle de propriété | `core/views.py`, `config/urls.py` |
| Signature des notifications de paiement | `core/webhooks.py` |
| Connexion Google | `core/oauth.py` |
| Expiration et rappels | `core/management/commands/subscriptions_tick.py` |
| Nouveautés proches et push | `nearby_alerts.py`, `send_push.py` |
| Configuration de l’exécution | `config/settings.py`, `.env.example` |
| Présentation et interactions | `templates/index.html`, `static/style.css`, `static/app.js` |
| Application mobile | `mobile/App.tsx`, `mobile/app.config.ts` |
| Déploiement et sauvegarde | `Dockerfile`, `compose.yaml`, `infra/`, `scripts/` |

Le code rédigé pour le projet porte des commentaires français à chaque ligne significative : intention, méthode et règle métier. Les fichiers JSON ne permettent pas les commentaires en syntaxe standard ; leur rôle et leurs clés sont expliqués dans ce guide et l’architecture. Les lockfiles, le contrat OpenAPI généré et les ressources tierces ne sont pas modifiés pour y injecter des commentaires qui casseraient leur format ou leur provenance. Les lignes vides et shebangs de scripts ne nécessitent pas d’explication redondante.

Après toute modification de modèle, créez une migration, relisez-la, puis exécutez la recette sur les deux moteurs. Après une modification de dépendances, actualisez le lockfile et vérifiez les builds. Conservez les secrets hors Git. La chaîne CI vérifie le code ; elle ne déploie pas automatiquement en production.

## 11. Dépannage rapide

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| « SECRET_KEY doit être aléatoire… » | DEBUG hérité à 0 ou secret de production absent | Utiliser `scripts/dev.sh` en local ; générer un vrai secret en production |
| Aucun commerce à l’accueil | Base vide, rayon différent, profils en attente ou comptes suspendus | Charger la démo en local, vérifier centre/rayon puis modération |
| Erreur 403 CSRF | Jeton absent, mauvais domaine ou session périmée | Recharger depuis le même domaine et vérifier les origines de confiance HTTPS |
| Erreur 429 | Limite de requêtes ou connexions atteinte | Attendre la durée indiquée ; utiliser Redis partagé en production |
| GPS refusé | Permission système, navigateur ou contexte non sécurisé | Utiliser HTTPS et proposer le point manuel |
| Email absent | Backend console ou SMTP incorrect | Lire le terminal en local ; tester la livraison SMTP en staging |
| Formule inchangée après demande | Règlement encore en attente | Faire vérifier le reçu ; ne pas modifier les tables financières directement |
| Paiement non confirmable | Devis >24 h, état rejeté ou droits remplacés | Rejeter l’ancienne demande si nécessaire puis créer un nouveau devis |
| Photo rejetée | Format, poids, dimensions ou fichier invalide | Utiliser JPEG/PNG/WebP dans les limites prévues |
| Application mobile blanche | URL inaccessible depuis l’appareil | Vérifier IP, ALLOWED_HOSTS, HTTPS, réseau et URL Expo |
| Erreur PostGIS à la migration | Extension indisponible ou permission SQL insuffisante | Préparer PostGIS avec le rôle de migration documenté |
| Redirection HTTPS en boucle | Proxy de confiance mal configuré | Garder l’API privée et activer TRUST_PROXY seulement derrière le proxy prévu |

## 12. Avant ouverture commerciale

Le maître d’ouvrage doit encore disposer d’un domaine, d’un hébergement, d’un SMTP, des comptes fournisseurs éventuellement activés, des comptes de stores et des mentions légales réelles. La décision sur iOS 14/15.1 doit être explicite. Les essais de paiement et push réels, les tests sur appareils et les mesures de charge représentatives doivent être réalisés en staging.

Le contenu complet des exigences, les écarts restants et les procédures concrètes figurent dans les documents liés en début de README. Cette transparence permet de faire une recette précise sans confondre une application locale fonctionnelle avec un service commercial déjà publié.
