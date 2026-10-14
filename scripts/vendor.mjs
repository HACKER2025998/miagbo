import {mkdir, copyFile} from 'node:fs/promises'; // Copier uniquement les ressources de carte nécessaires au navigateur.
await mkdir('static/vendor', {recursive: true}); // Créer la destination versionnée si elle n'existe pas.
for (const file of ['leaflet.js', 'leaflet.css', 'leaflet.js.map']) { // Conserver la bibliothèque, sa feuille de style et sa carte de diagnostic.
  await copyFile(`node_modules/leaflet/dist/${file}`, `static/vendor/${file}`); // Rendre la carte indépendante d'un CDN de scripts.
} // Terminer la copie des ressources de carte.
await copyFile('node_modules/leaflet/LICENSE', 'static/vendor/LEAFLET-LICENSE'); // Préserver la licence du composant tiers.
