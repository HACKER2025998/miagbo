const {defineConfig, devices} = require('@playwright/test'); // Charger la configuration et les profils de navigateur officiels.
module.exports = defineConfig({ // Configurer une recette avec serveur et base indépendants de la démonstration locale.
  testDir:'tests/e2e', fullyParallel:false, workers:1, timeout:30000, // Sérialiser les tests qui modifient le même compte de démonstration.
  use:{baseURL:'http://127.0.0.1:8011',trace:'retain-on-failure'}, // Conserver une trace uniquement pour analyser un échec.
  reporter:[['list'],['json',{outputFile:'test-results/e2e.json'}]], // Produire un résultat lisible et une preuve exploitable dans le rapport de recette.
  webServer:{command:'DEBUG=1 MIAGBO_SQLITE_PATH=/tmp/miagbo-e2e.sqlite3 DEMO_PASSWORD=DemoMiagbo2026! .venv/bin/python scripts/e2e_server.py',url:'http://127.0.0.1:8011/api/v1/health/',reuseExistingServer:false,timeout:30000}, // Ne jamais exécuter les scénarios sur une production ou une base personnelle.
  projects:[{name:'desktop',use:{...devices['Desktop Chrome']}},{name:'mobile',use:{...devices['iPhone 13'],defaultBrowserType:'chromium'}}], // Vérifier desktop et format mobile sans prétendre remplacer un test sur iPhone réel.
}); // Terminer la configuration de recette navigateur.
