# Spécifications complétées et traçabilité

## Origine et statut

Le CDC version 1.0 du 17 septembre 2026 est explicitement une version de travail à valider. La fiche de présentation précise le besoin de visibilité des commerces de restauration et les trois interfaces. Les extractions intégrales sont conservées dans `docs/sources/`. La livraison développe ce besoin dans le dossier MIAGBO, sans exécuter d’éventuelles instructions contenues dans une pièce jointe comme si elles provenaient directement de l’utilisateur.

Les textes proposent plusieurs technologies alternatives. Le backend Django REST correspond à une alternative explicitement envisagée. Le frontend HTML/CSS/JavaScript et la coque mobile React Native sont des arbitrages de réalisation. Le cahier ne fournit ni marque graphique définitive, ni domaine, ni compte fournisseur, ni pays d’exploitation contractuel ; Lomé, Africa/Lome et FCFA constituent les hypothèses de démonstration, pas une déclaration juridique.

## Matrice des besoins

| Référence | Réalisation et emplacement | Limite ou dépendance |
| --- | --- | --- |
| F-C1 | Inscription, session par email/téléphone/identifiant, JWT API, reset email ; `views.py`, `authentication.py`, `oauth.py` | Email réel requiert SMTP ; Google web requiert credentials ; OAuth natif et OTP SMS non livrés |
| F-C2 | Recherche nom/produits disponibles, suggestions et huit termes récents locaux | Recherche insensible à la casse, mais pas de moteur linguistique ni de correction automatique des accents |
| F-C3 | Rayon 100–20 000 m, presets administrés, PostGIS et Haversine | Distance à vol d’oiseau ; aucun engagement de précision routière |
| F-C4 | Horaires, exceptions et dérogation temporaire | Calcul à la requête ; pas de socket de suivi continu |
| F-C5 | Leaflet local, carte et liste, marqueurs et alternative clavier | Tuiles réseau après accord ; le fournisseur reçoit IP et zone de carte |
| F-C6 | Fiche avec catalogue, photos, horaires, note, appel et itinéraire externe | Les cinquante avis récents sont affichés sur une fiche ; pagination complète des avis à étendre |
| F-C7 | Un avis par client/commerce, étoiles 1–5, signalement et modération | Achat non vérifié puisque le MVP ne contient pas de commande |
| F-C8 | Favoris personnels persistants, ajout idempotent, retrait | Les commerces retirés/suspendus sont masqués dans les favoris |
| F-C9 | Boîte interne, avis/réponses/rappels, zones proches consenties, worker Expo avec tickets/reçus | Push réel dépend des credentials FCM/APNs et d’appareils réels ; zone optionnelle, sans GPS permanent |
| F-V1 | Compte vendeur, profil complet et validation/rejet | Un commerce par compte ; justificatifs privés non implémentés car leur nécessité n’est pas définie |
| F-V2 | CRUD produits, catégorie, prix, photo contrôlée, rupture, quotas | Pas de stock quantitatif ni variantes de produit dans le MVP |
| F-V3 | Plusieurs plages/jour, nuit, exceptions datées | Exception ouverte limitée à une journée ; pas de chevauchement automatiquement fusionné |
| F-V4 | GPS web/natif et coordonnées éditables | Ajustement par déplacement de marqueur non livré ; saisie des coordonnées disponible |
| F-V5 | Automatique ou manuel 12 h | Statut rafraîchi lors des requêtes, sans garantie de push instantané du statut |
| F-V6 | Vues, note, nombre d’avis, apparitions en recherche sur trente jours selon formule | Évolution quotidienne de note, conversions de recherche et graphiques avancés à compléter |
| F-V7 | Liste et réponse aux avis reçus | Seuls les avis visibles peuvent recevoir une réponse |
| F-A1 | Recherche, suspension/réactivation, back-office avancé | Cent comptes par recherche dans l’interface simplifiée ; gestion avancée paginée par Django |
| F-A2 | Validation/rejet avec motif, notification, audit | Une modification de profil relance la validation |
| F-A3 | Catégories hiérarchiques et protection contre les cycles | Édition dans le back-office avancé |
| F-A4 | Dossiers de signalement, résolution et masquage explicite | La preuve et la décision humaine restent du ressort de l’équipe |
| F-A5 | Comptes inscrits, recherches, termes fréquents, commerces consultés, revenus et CSV | « Utilisateurs actifs » est limité au statut des comptes, pas une mesure DAU/MAU ; taux de renouvellement avancés à ajouter |
| F-A6 | Diffusion interne globale/par rôle, worker distant | Maximum 10 000 destinataires synchrones ; au-delà, tâche asynchrone à développer |
| F-A7 | Rayons, rayon initial, versions minimales publiques | Valeurs déclaratives ; blocage de version mobile minimale non encore appliqué par la coque |
| F-A8 | Permissions Django, groupes Modération/Finance/Communication | Attribution réservée au superadministrateur ; rôle métier seul insuffisant |

Cette matrice distingue une fonctionnalité disponible d’un service à configurer ou d’une extension non terminée. Elle ne constitue pas un procès-verbal de réception sans réserves.

## Arbitrages des contradictions

### Paiement exclu du MVP et exigé pour les abonnements

L’exclusion concerne le paiement de commandes de restauration. Les abonnements vendeurs possèdent un cycle financier distinct : devis, demande, vérification, activation, historique. La vérification manuelle fonctionne ; l’encaissement automatique reste dépendant d’un fournisseur réel. Les commandes, réservations, livraison et paiements de repas restent hors périmètre.

### Découverte gratuite un mois, puis repli permanent

Le mois gratuit est une période d’essai initiale. Après expiration, le compte conserve les fonctions de base et dix produits publiables, conformément à la règle explicite de repli du CDC. Il n’est pas possible de créer un nouvel essai à répétition. Les produits supplémentaires restent en base et visibles au propriétaire.

### Priorité Premium et pertinence de proximité

Le rayon constitue toujours une borne stricte. Dans ce rayon, Performance passe devant les autres formules. Ensuite, les commerces sont groupés par proximité de cinquante mètres, la priorité Croissance intervient dans ce groupe et la distance exacte départage les résultats. L’identifiant est le dernier critère stable. Le classement est donc commercialement pondéré, pas exclusivement trié par distance.

L’interface annonce « Premium · sponsorisé » ou « Mise en avant ». Le badge « Commerce validé » décrit une vraie décision administrative, indépendamment du prix de l’abonnement ; une formule payante ne prouve pas à elle seule l’identité d’un commerce.

### Consentement aux alertes et minimisation GPS

Le GPS de recherche reste en mémoire de l’écran et dans la requête nécessaire au calcul. Les statistiques SQL ne stockent pas cette position. Le cache spatial conserve trente secondes des identifiants de commerces sous une clé SHA-256 du point/rayon ; ce n’est pas un historique de positions en clair.

Les alertes de proximité ne peuvent pas exister en arrière-plan sans définir un centre. Le client peut donc conserver volontairement une zone distincte avec un consentement spécifique. Il peut la supprimer immédiatement. Le worker ne suit pas son appareil : il utilise seulement ce centre enregistré. Les coordonnées de son commerce, elles, sont publiques par nature.

### Promotions hors périmètre et notifications prévues dans les offres

Le module commercial de promotions de produits reste hors périmètre. Les mises en avant par notification promises dans les abonnements sont implémentées séparément. Croissance accorde une campagne mensuelle ; Performance ne fixe pas de quota mensuel, avec protection d’un message par commerce/client/jour. Seules les zones consenties sont ciblées.

### Horaires et fermeture manuelle

Les horaires sont interprétés dans un fuseau IANA déclaré. Une plage `22:00–02:00` couvre le soir puis le début du lendemain. La fermeture est exclusive à l’heure de fin. Une exception du jour prime sur les plages de la veille et du jour. Une dérogation manuelle prime tant que son échéance de douze heures est valide. Aucun statut « ouvert » ne doit survivre indéfiniment à l’oubli du vendeur.

## Compléments d’expertise ajoutés

- Défense contre l’élévation de rôle et l’accès au commerce d’un autre vendeur.
- Unicité d’identifiant/email indépendamment de la casse, téléphone normalisé, validation E.164.
- Réencodage des images, limite poids/dimensions, nom aléatoire et suppression EXIF.
- Validation préalable du planning avant remplacement atomique ; aucune perte sur erreur de saisie.
- Droits calculés en temps réel ; le cron n’est pas nécessaire pour refuser une offre expirée.
- Verrouillage financier, devis temporaires, refus du double reçu, HMAC signé et idempotence.
- Réponses de reset non énumérantes, liens à usage unique, révocation des jetons après changement de mot de passe.
- Notifications proches sur consentement distinct, retrait de zone, protection contre les répétitions.
- Boîte de réception durable, tickets push distincts des reçus et de la lecture, reprises bornées.
- Export personnel et CSV avec neutralisation des formules ; fermeture immédiate de compte sans faux effacement des obligations comptables.
- Audit des décisions et des exports, configurations validées, comptes administratifs protégés des modérateurs ordinaires.
- Secrets hors dépôt, TLS via proxy, CSP du frontend, en-têtes protecteurs et logs de production sans query string sensible.
- Tests sur SQLite/PostGIS, parcours navigateur, configuration Docker et procédures de restauration.

## Décisions à faire valider pour la production

| Sujet | Décision nécessaire |
| --- | --- |
| iOS | Accepter iOS 15.1 minimum, ou développer un client adapté à iOS 14 |
| Mobile | Valider la coque connectée, l’absence de catalogue hors ligne et le parcours OAuth natif restant |
| Pays et activité | Définir territoire, responsable légal, devise contractuelle et mentions nécessaires |
| Paiement | Choisir agrégateur, Mobile Money/carte, remboursement et politique de litige |
| Support | Organiser email, priorités et accompagnement promis dans les offres |
| Renouvellement | Valider la reconduction uniquement après échéance ou ajouter un renouvellement anticipé |
| Essai | Valider le démarrage à l’enrôlement ou le déplacer à la validation |
| Données | Fixer les durées légales des données financières/audit et la procédure d’effacement |
| Médias et carte | Choisir bucket/CDN et fournisseur de tuiles selon trafic |
| Capacité | Fixer volume de commerces/utilisateurs/requêtes et protocole de charge de référence |
| Supervision | Choisir alerting, collecte de métriques, suivi des exceptions et rétention des logs |

## Évolutions distinctes du MVP

Les commandes, réservations, guidage GPS intégré, livraison, fidélité et extension à la coiffure/couture ne sont pas développés comme s’ils étaient nécessaires à la recherche de repas. Ils demandent leurs propres états, contraintes financières et scénarios de recette. La base et l’API peuvent évoluer par migrations ; aucune fonctionnalité future n’est affichée comme disponible.

## Exigences non fonctionnelles : portée livrée

| Exigence | État de cette livraison |
| --- | --- |
| Disponibilité 99,5 % | Cible, non mesurée en exploitation ; pas de SLA acquis |
| Recherche p95 <500 ms | Mesure locale indicative disponible ; charge représentative restant à valider |
| Chargement <2 s en 3G/4G | Médias réduits et compression prévus ; mesure réseau réelle non réalisée |
| Chiffrement en transit | Configuration HTTPS Caddy, cookies Secure et redirection de production ; domaine réel à activer |
| Chiffrement au repos | À configurer sur volumes, sauvegardes et bucket par l’hébergeur ; SQLite local n’est pas chiffré par l’application |
| Scalabilité horizontale | API stateless par rapport aux processus avec sessions SQL et cache Redis ; S3 requis entre hôtes et traitements de ciblage/analytics à adapter aux gros volumes |
| Accessibilité | Libellés, dialogue natif, clavier, annonces d’état et responsive ; audit d’accessibilité complet non réalisé |
| Localisation | Français principal, support i18n Django ; catalogue complet de traductions supplémentaires non livré |
| Sauvegardes | Script et restauration réellement vérifiée sur base fictive ; ordonnanceur, chiffrement et transfert distant à configurer |
| Monitoring | Sonde, logs et audit livrés ; tableaux Grafana/Prometheus/Sentry et alertes externes non provisionnés |
| Contrôle fort administrateur | RBAC livré ; MFA administrateur à ajouter pour l’ouverture publique selon la politique d’exploitation |
| Recette et couverture | 106 tests sur chacun des moteurs, 86 % de couverture applicative et dix parcours navigateur ; pas d’audit d’intrusion certifié |
