import {registerRootComponent} from 'expo'; // Initialiser le point d'entrée natif compatible Expo.
import App from './App'; // Charger la coque mobile MIAGBO.
registerRootComponent(App); // Enregistrer le composant principal Android et iOS.
