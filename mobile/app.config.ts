export default { // Déclarer les métadonnées utilisées pour générer les projets natifs.
  expo: { // Regrouper la configuration Expo de MIAGBO.
    name: 'Miagbo', slug: 'miagbo', version: '1.0.0', orientation: 'portrait', // Identifier l'application et sa première version.
    scheme: 'miagbo', userInterfaceStyle: 'light', // Préparer les liens profonds et conserver le contraste de l'interface web.
    ios: {bundleIdentifier: 'com.miagbo.app', supportsTablet: true, infoPlist: {NSLocationWhenInUseUsageDescription: 'Votre position permet de trouver les commerces proches ou de localiser votre point de vente.'}}, // Expliquer la permission GPS avant la demande système iOS.
    android: {package: 'com.miagbo.app', permissions: ['ACCESS_COARSE_LOCATION','ACCESS_FINE_LOCATION']}, // Limiter les permissions à la géolocalisation au premier plan.
    extra: {eas: {projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID || ''}}, // Associer les tokens push au projet Expo réellement enregistré.
    plugins: ['expo-notifications', ['expo-location',{locationWhenInUsePermission:'Miagbo utilise votre position uniquement lorsque vous recherchez un commerce proche.'}]], // Configurer le texte natif de consentement.
  }, // Terminer les métadonnées de génération.
}; // Exporter la configuration versionnée, sans clés de store ni secrets.
