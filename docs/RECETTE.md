# Rapport de recette — 14 octobre 2026

## Résultat de la vérification locale

| Vérification | Résultat constaté | Portée |
| --- | --- | --- |
| Suite backend SQLite | **106 tests réussis** | Authentification, permissions, données, horaires, abonnements, modération, alertes, fichiers et fournisseurs simulés |
| Suite backend PostgreSQL/PostGIS | **106 tests réussis** | Même suite sur un moteur réel avec extension et index géographique |
| Couverture applicative Python | **86 %** | Hors code des tests et migrations ; seuil CI de 70 % |
| Parcours navigateur Chromium | **10 scénarios réussis** | Cinq parcours sur desktop et cinq sur format iPhone 13, avec base isolée |
| Contrat OpenAPI | Validation réussie, sans avertissement | Génération avec `--validate --fail-on-warn` |
| Cohérence migrations/modèles | Aucun changement non migré | `makemigrations --check --dry-run` |
| JavaScript web | Syntaxe valide | `node --check static/app.js` |
| Code mobile TypeScript | Vérification stricte réussie | `tsc --noEmit` |
| Bundle Android | Export Metro/Hermes réussi, 730 modules | Bundle JavaScript, pas un APK signé ni un test d’appareil |
| Bundle iOS | Export Metro/Hermes réussi, 730 modules | Bundle JavaScript, pas une archive Xcode signée |
| Configuration Compose et Caddy | Syntaxe Compose et `caddy validate` réussies | Sans lancer un domaine public ni obtenir de certificats réels |
| Image Docker | Construction et contrôle `check --deploy --fail-level WARNING` réussis | Python 3.13, dépendances verrouillées, utilisateur non root |
| Smoke test Gunicorn en conteneur | HTTP 200 sur health, page et JavaScript ; CSP présente sur le frontend | Signal HTTPS du proxy simulé sur localhost ; aucune certification TLS publique |
| Sauvegarde/restauration PostGIS | Restauration réussie dans une base différente de la source | 6 commerces, 6 produits, 3 avis, PostGIS 3.5.2 |

Les logs détaillés des commandes ont été produits dans `/tmp` pendant la réalisation ; ils ne sont pas considérés comme une archive durable de CI. Les nombres ci-dessus correspondent aux sorties observées. Les rapports reproductibles restent les scripts et tests versionnés. Les éventuelles sorties complémentaires de smoke test sont conservées dans les fichiers locaux de documentation associés.

La recette a utilisé Python 3.14.8, Django 5.2.18 et Node 24.16.0 sur l’hôte. L’image de production utilise Python 3.13 ; la CI déclare Python 3.13 et Node 22. La configuration CI est fournie mais un pipeline GitHub distant n’a pas été exécuté ni publié à partir de cet environnement.

## Cas backend couverts

### Identité et isolation

- Hachage et robustesse des mots de passe ; consentement d’inscription.
- Refus de création d’un administrateur public et d’auto-promotion via le profil.
- Connexion par email et téléphone, refus d’un mauvais secret.
- CSRF réellement activé pour le login anonyme, puis connexion valide avec le cookie initial.
- Suspension d’un compte malgré un access token non expiré et refus de son refresh.
- Normalisation du téléphone et refus des doublons email/identifiant sans casse.
- Reset à réponse non énumérante, lien à usage unique et identifiant mal formé.
- OIDC : configuration absente, state manquant, PKCE, création contrôlée avec claims simulés et rejet d’un nonce incohérent.
- Export personnel sans mot de passe, fermeture exigeant la preuve du secret.

### Catalogue et recherche

- Mot-clé de produit, catégorie, résultat vide et exclusion d’un commerce distant.
- NaN, inf, coordonnées hors domaine, rayon et catégorie invalides.
- Retrait immédiat des profils en attente ou appartenant à un compte suspendu.
- Produit indisponible ou masqué au-delà du quota absent de la recherche.
- Statistiques ne stockant pas les coordonnées personnelles de recherche.
- Compteur de vue, favoris idempotents et messages privés inaccessibles à un tiers.
- Enrôlement unique avec trial, vendeur non propriétaire interdit d’écriture.
- CRUD produits, quota gratuit et prix négatif refusé.
- Image réellement décodée/réencodée ; faux fichier JPEG rejeté.

### Horaires et modération

- Remplacement atomique des horaires sans perte en cas de saisie invalide.
- Plage nocturne passant minuit, fermeture exclusive à l’heure de fin.
- Exception fermée prioritaire et dates d’exception dupliquées refusées.
- Dérogation de statut qui expire automatiquement après douze heures.
- Modification de profil remettant le commerce en attente.
- Avis unique 1–5, auto-évaluation vendeur interdite et réponse réservée au propriétaire.
- Signalement avec cible unique, masquage retirant l’avis de la moyenne publique.
- Permissions fines du staff, suspension de compte retirant son commerce et protection du compte administratif.
- Audit d’une décision, diffusion ciblée par rôle et neutralisation des formules CSV.

### Droits et paiement

- Demande de règlement sans activation ; doublon de devis récent bloqué.
- Trial non renouvelable arbitrairement, expiration conservant tout le catalogue.
- Mois calendaires et arrondi du crédit à mi-période.
- Baisse de formule interdite avant échéance.
- Activation idempotente, reçu obligatoire et devis périmé refusé.
- Réutilisation d’un reçu confirmée bloquée par contrainte SQL, sans activation partielle.
- Confirmation/rejet par opérateur habilité.
- Webhook signé valide et rejeu idempotent ; signature absente refusée ; service désactivé sans secret.
- Rappels et notifications d’expiration dédoublonnés.

### Alertes et transport mobile

- Zone d’alerte exigeant un consentement distinct, privée et supprimable.
- Nouveaux commerces notifiés une seule fois dans les zones proches.
- Campagne Croissance limitée au mois et ciblage selon rayon consenti.
- Performance autorisant les campagnes avec au plus un message quotidien par commerce/client.
- Token Expo validé et inscription répétée sans doublon.
- Déconnexion retirant les destinations push du compte.
- Ticket push puis reçu séparés ; panne réseau replanifiée sans faux succès.
- Purge des recherches de plus de quatre-vingt-dix jours.

Ces tests ne constituent pas un audit d’intrusion complet, ni une preuve qu’aucune anomalie n’existe.

## Parcours navigateur exécutés

Chaque ligne a été exécutée en desktop et en format mobile :

| Parcours | Actions observées |
| --- | --- |
| Découverte | Six commerces, recherche « gâteaux », résultat ciblé, mot absent, remise à zéro |
| Carte et fiche | Aucun appel de tuile avant choix ; liste de commerces utilisable ; fiche et lien d’itinéraire correct |
| Client | Connexion réelle avec CSRF, ajout favori, rechargement, lecture depuis la base, retrait |
| Vendeur | Connexion, ajout de produit, modification du prix, suppression confirmée et état relu |
| Administration | Connexion, tableau de bord et back-office ; absence de débordement horizontal |

Les captures sont dans `docs/screenshots/`. Le profil iPhone 13 est une émulation de viewport et d’interactions dans Chromium : il ne prouve ni Safari iOS, ni le comportement GPS/push d’un vrai iPhone. La carte a été vérifiée pour l’absence de requête avant consentement ; le service public de tuiles n’a pas fait l’objet d’un engagement de disponibilité.

## Mesure indicative de recherche

Le fichier [performance.local.json](performance.local.json) conserve une mesure HTTP réelle sur le serveur Django de recette, avec PostgreSQL/PostGIS et six commerces fictifs :

| Paramètre | Mesure |
| --- | --- |
| Requêtes | 40 |
| Concurrence | 4 workers |
| Résultats par recherche | 6 |
| P95 | 99,58 ms |
| Maximum | 114,76 ms |
| Moyenne | 76,32 ms |

La mesure a été faite sur un serveur de développement local, pendant des vérifications concurrentes. Elle permet de contrôler le fonctionnement du script et une petite charge ; elle ne démontre pas un SLA p95 à grande échelle, une disponibilité de 99,5 % ou un chargement 3G/4G inférieur à deux secondes. Rejouez une campagne avec données, latence réseau, géographie, caches et concurrence représentatifs sur Gunicorn/staging.

## Réserves avant réception commerciale

1. Paiement Mobile Money/carte réel : prestataire, credentials, checkout et webhooks natifs à intégrer et tester ; workflow manuel livré.
2. SMTP, Google et push : tests réels avec les comptes du projet et des appareils nécessaires.
3. Mobile : iOS 15.1 minimum, OAuth système natif restant, APK/AAB/IPA signés et validation de stores non réalisés.
4. Interfaces : Safari, Firefox, Edge, clavier/lecteur d’écran exhaustifs et connexions mobiles dégradées à vérifier.
5. Analytique : évolution de note, conversion de recherche, DAU/MAU et taux de renouvellement avancés non complets.
6. Géolocalisation : déplacement de marqueur pour l’édition du commerce non livré ; coordonnées manuelles disponibles.
7. Exploitation : certificats du vrai domaine, S3 réel, sauvegardes distantes, supervision et reprise d’incident à valider sur l’infrastructure choisie.
8. Organisation : responsable légal, coordonnées support, règles comptables et justificatifs d’enrôlement à faire définir.

Les cibles non vérifiées ne sont pas présentées comme des résultats acquis.

## Procès-verbal à remplir avec le client

| Champ | À renseigner par le maître d’ouvrage |
| --- | --- |
| Environnement de recette | URL, version exacte et identifiant d’image |
| Jeu de données | Commerces et comptes autorisés pour la recette |
| Validateur | Nom et fonction |
| Résultat | Accepté / accepté avec réserves / refusé |
| Réserves bloquantes | Références de cette matrice et preuves |
| Actions et échéances | Responsable et date cible par réserve |
| Date de validation | À compléter après les essais réels |

Ce document est un rapport technique de réalisation, pas une signature fictive au nom du client.

## Preuves locales complémentaires

- [Smoke test Docker](docker-smoke.local.json).
- [Mesure de performance](performance.local.json).
- [Restauration de la base fictive](restauration.local.txt).

Les secrets locaux, les cookies et les fichiers de base ne font pas partie de l’archive des sources.

Après le passage complet des 106 tests, deux scénarios ciblés d’inscription ont été rejoués avec succès pour confirmer que le contrat OpenAPI ne propose plus le rôle administrateur à l’inscription publique. Le comportement de refus de ce rôle est conservé.
