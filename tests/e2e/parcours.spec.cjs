const {test,expect} = require('@playwright/test'); // Exécuter des parcours réels sur les pages livrées.
async function login(page, identifier) { // Partager uniquement les gestes de connexion, sans contourner l'API.
  await page.getByRole('button',{name:'Se connecter',exact:true}).click(); // Ouvrir le dialogue d'identité depuis la page.
  await page.getByLabel('Email, téléphone ou identifiant').fill(identifier); // Saisir l'acteur du parcours.
  await page.getByLabel('Mot de passe',{exact:true}).fill('DemoMiagbo2026!'); // Utiliser le secret du jeu de test isolé.
  await page.getByRole('dialog').getByRole('button',{name:'Se connecter',exact:true}).click(); // Soumettre un formulaire avec le jeton CSRF réel.
  await expect(page.getByRole('dialog')).not.toBeVisible(); // Attendre que le serveur ait accepté la connexion.
} // Terminer le geste de connexion.
test.beforeEach(async ({page}) => {await page.goto('/'); await expect(page.getByRole('heading',{name:'Autour de vous'})).toBeVisible(); await expect(page.locator('#result-count')).toContainText('commerce');}); // Attendre une interface réellement chargée avant chaque scénario.
test('recherche, état vide et retour aux résultats',async ({page}) => { // Vérifier le parcours principal et une reprise sans rechargement.
  await expect(page.locator('.vendor-card')).toHaveCount(6);
  await page.screenshot({path:`docs/screenshots/${test.info().project.name}.png`,fullPage:true}); // Conserver un aperçu réel de l'interface livrée.
 // Afficher les commerces fictifs proches de Lomé.
  await page.getByLabel('Que cherchez-vous ?').fill('gâteaux'); await page.locator('#search-form').getByRole('button',{name:'Rechercher'}).click(); // Rechercher une offre concrète du cahier des charges.
  await expect(page.locator('.vendor-card')).toHaveCount(1); await expect(page.locator('.vendor-card')).toContainText('Les Douceurs de Lomé'); // Retrouver uniquement l'offre correspondante.
  await page.getByLabel('Que cherchez-vous ?').fill('aucun-produit-test'); await page.locator('#search-form').getByRole('button',{name:'Rechercher'}).click(); // Produire un résultat vide réel.
  await expect(page.getByRole('heading',{name:'Aucune adresse dans ce rayon, pour le moment.'})).toBeVisible(); // Donner une explication à l'utilisateur.
  await page.locator('#results').getByRole('button',{name:'Tout découvrir'}).click(); await expect(page.locator('.vendor-card')).toHaveCount(6); // Reprendre la découverte sans perdre le centre géographique.
}); // Terminer la recette de recherche.
test('carte soumise au choix et fiche avec itinéraire externe',async ({page}) => { // Vérifier confidentialité cartographique et accès au catalogue.
  let tileRequests = 0; page.on('request',request => {if (request.url().includes('tile.openstreetmap.org')) tileRequests++;}); // Observer le réseau sans envoyer une position à un tiers.
  await page.getByRole('button',{name:'Carte',exact:true}).click(); await expect(page.getByRole('button',{name:'Charger la carte'})).toBeVisible(); // Attendre un choix avant le fournisseur de tuiles.
  expect(tileRequests).toBe(0); // Confirmer qu'aucune tuile n'est demandée avant consentement.
  await page.locator('.map-list').getByRole('button',{name:'Chez Maman Afi'}).click(); // Ouvrir aussi la fiche au clavier depuis la liste cartographique.
  await expect(page.getByRole('dialog').getByRole('heading',{name:'Chez Maman Afi'})).toBeVisible(); await expect(page.getByRole('link',{name:'Itinéraire externe'})).toHaveAttribute('href',/destination=6\.1331,1\.2242/); // Vérifier le commerce et sa destination réelle.
}); // Terminer la recette de carte et fiche.
test('connexion client et favoris persistants',async ({page}) => { // Vérifier qu'une mutation privée passe par le serveur et survit au rechargement.
  await login(page,'client'); await page.locator('.favorite-button').first().click(); await expect(page.locator('.favorite-button.selected').first()).toBeVisible(); // Ajouter un commerce après authentification.
  await page.reload(); await expect(page.locator('.favorite-button.selected').first()).toBeVisible(); // Relire le favori depuis la base plutôt que le seul état JavaScript.
  await page.locator('.favorite-button.selected').first().click(); // Rétablir le jeu de test pour le projet responsive suivant.
}); // Terminer le scénario client.
test('vendeur : création, modification et suppression d’un produit',async ({page}) => { // Vérifier le catalogue de bout en bout avec sessions et droits de propriété.
  await login(page,'vendeur'); await expect(page.getByRole('heading',{name:'Chez Maman Afi'})).toBeVisible(); // Atteindre le commerce propriétaire.
  await page.getByRole('button',{name:'Ajouter un produit'}).click(); await page.getByLabel('Nom du produit').fill('Produit recette navigateur'); await page.getByLabel('Prix en FCFA').fill('850'); // Saisir un nouveau produit.
  await page.getByRole('button',{name:'Enregistrer le produit'}).click(); await expect(page.locator('tr').filter({hasText:'Produit recette navigateur'})).toBeVisible(); // Vérifier son apparition après réponse API.
  const row = page.locator('tr').filter({hasText:'Produit recette navigateur'}); await row.getByRole('button',{name:'Modifier'}).click(); await page.getByLabel('Prix en FCFA').fill('900'); await page.getByRole('button',{name:'Enregistrer le produit'}).click(); // Modifier le prix du produit créé.
  await expect(page.locator('tr').filter({hasText:'Produit recette navigateur'})).toContainText('900'); // Relire le montant persistant dans le tableau.
  await page.locator('tr').filter({hasText:'Produit recette navigateur'}).getByRole('button',{name:'Supprimer'}).click(); await page.getByRole('dialog').getByRole('button',{name:'Supprimer le produit'}).click(); // Confirmer explicitement la suppression.
  await expect(page.locator('tr').filter({hasText:'Produit recette navigateur'})).toHaveCount(0); // Ne laisser aucun produit de recette dans le catalogue.
}); // Terminer le scénario commerçant.
test('administration et affichage responsive sans débordement',async ({page}) => { // Vérifier la navigation administrative et l'adaptation réelle de la largeur.
  await login(page,'admin'); await expect(page.getByRole('heading',{name:'Le quartier, en confiance.'})).toBeVisible(); await expect(page.getByRole('link',{name:'Back-office avancé ↗',exact:true})).toBeVisible(); // Atteindre les outils de gestion depuis un compte autorisé.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy(); // Détecter un débordement horizontal de la page, en particulier mobile.
}); // Terminer la recette administrative.
