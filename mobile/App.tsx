import React, {useEffect, useRef, useState} from 'react'; // Gérer le cycle de vie, la navigation et les erreurs natives.
import {ActivityIndicator, Alert, BackHandler, Linking, Platform, StyleSheet, Text, TouchableOpacity, View} from 'react-native'; // Utiliser les composants et services des deux systèmes mobiles.
import {WebView, WebViewMessageEvent} from 'react-native-webview'; // Réutiliser les trois espaces web dans un conteneur natif.
import {SafeAreaProvider, SafeAreaView} from 'react-native-safe-area-context'; // Éviter les encoches et les barres système.
import * as Notifications from 'expo-notifications'; // Obtenir un token Expo correspondant au projet configuré.
import * as Location from 'expo-location'; // Demander un GPS natif uniquement au premier plan.
import {StatusBar} from 'expo-status-bar'; // Harmoniser la barre système avec le fond clair.
const appURL = process.env.EXPO_PUBLIC_MIAGBO_URL || 'http://10.0.2.2:8000'; // Utiliser l'hôte spécial de l'émulateur Android en développement.
const trustedOrigin = new URL(appURL).origin; // Définir l'unique origine autorisée à exécuter le pont natif.
const productionInvalid = !__DEV__ && !appURL.startsWith('https://'); // Refuser de transmettre une session en HTTP dans un binaire de production.
export default function App() { // Fournir navigation, consentement GPS et reprise réseau autour du site.
  const browser = useRef<WebView>(null); const canGoBack = useRef(false); const [offline,setOffline] = useState(false); // Conserver les références nécessaires sans stocker de credentials.
  useEffect(() => { // Relier le bouton Retour Android à l'historique du contenu.
    const handler = BackHandler.addEventListener('hardwareBackPress',() => {if (canGoBack.current) {browser.current?.goBack(); return true;} return false;}); // Revenir dans la WebView avant de fermer l'application.
    return () => handler.remove(); // Retirer l'écoute lors du démontage.
  },[]); // Installer une seule fois le comportement de retour.
  async function onMessage(event: WebViewMessageEvent) { // Traiter uniquement les messages de notre site et du type autorisé.
    try { // Refuser silencieusement les messages mal formés, puis annoncer les erreurs de permission.
      if (new URL(event.nativeEvent.url).origin !== trustedOrigin) return; // Interdire un pont natif à une page tierce.
      const message = JSON.parse(event.nativeEvent.data); // Lire le contrat JSON minimal du site.
      if (message.type === 'push') { // Traiter une demande explicite de notifications du compte.
        const projectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID; if (!projectId) {Alert.alert('Configuration requise','Le projet Expo et les credentials FCM/APNs doivent être configurés.'); return;} // Ne pas simuler un token fournisseur.
        if (Platform.OS === 'android') await Notifications.setNotificationChannelAsync('default',{name:'MIAGBO',importance:Notifications.AndroidImportance.DEFAULT}); // Créer le canal nécessaire avant la permission Android.
        const permission = await Notifications.requestPermissionsAsync(); if (permission.status !== 'granted') return; // Respecter un refus sans bloquer l'application.
        const token = (await Notifications.getExpoPushTokenAsync({projectId})).data; const detail = JSON.stringify({token,platform:Platform.OS}); // Construire le contrat d'inscription du terminal.
        browser.current?.injectJavaScript(`window.dispatchEvent(new CustomEvent('miagbo-push',{detail:${detail}}));true;`); return; // Enregistrer via la session web, sans stocker un JWT natif.
      } // Terminer l'inscription push.
      if (message.type !== 'location' || !['search','vendor'].includes(message.target)) return; // Limiter les capacités accessibles au contenu web.
      const permission = await Location.requestForegroundPermissionsAsync(); // Présenter la permission système seulement après le clic web.
      if (permission.status !== 'granted') {Alert.alert('Position non autorisée','Vous pouvez saisir un point de départ manuellement dans Miagbo.'); return;} // Préserver l'utilisation sans GPS.
      const position = await Location.getCurrentPositionAsync({accuracy:Location.Accuracy.High}); // Capturer un point précis, sans suivi en arrière-plan.
      const detail = JSON.stringify({lat:position.coords.latitude,lng:position.coords.longitude,target:message.target}); // Sérialiser des nombres et une cible de liste blanche.
      browser.current?.injectJavaScript(`window.dispatchEvent(new CustomEvent('miagbo-location',{detail:${detail}}));true;`); // Livrer la position uniquement au parcours demandé.
    } catch {Alert.alert('Position indisponible','Vérifiez le GPS ou utilisez la saisie manuelle.');} // Garder un message accessible sans trace contenant la position.
  } // Terminer le pont GPS.
  function shouldNavigate(url: string) { // Maintenir une frontière stricte entre notre site et les services externes.
    if (url === 'about:blank') return true; // Autoriser la page initiale interne à la WebView.
    try { // Accepter seulement une URL structurée.
      const parsed = new URL(url); if (parsed.origin === trustedOrigin) return true; // Garder session et JavaScript dans notre origine.
      if (['https:','tel:','mailto:'].includes(parsed.protocol)) {Linking.openURL(url).catch(() => Alert.alert('Lien indisponible','Aucune application ne peut ouvrir ce lien.'));} // Ouvrir cartes et téléphone dans le système, sans exposer le pont.
    } catch {} // Refuser toute URL invalide.
    return false; // Bloquer les protocoles arbitraires et les pages tierces dans le conteneur.
  } // Terminer la politique de navigation.
  return <SafeAreaProvider><SafeAreaView style={styles.screen}><StatusBar style="dark"/>{productionInvalid ? <View style={styles.error}><Text style={styles.title}>Configuration HTTPS requise</Text><Text>Configurez EXPO_PUBLIC_MIAGBO_URL avant de produire le binaire.</Text></View> : offline ? <View style={styles.error}><Text style={styles.title}>Retrouvons votre quartier.</Text><Text style={styles.text}>La connexion est indisponible. Vérifiez le réseau puis réessayez.</Text><TouchableOpacity accessibilityRole="button" style={styles.button} onPress={() => setOffline(false)}><Text style={styles.buttonText}>Réessayer</Text></TouchableOpacity></View> : <WebView ref={browser} source={{uri:appURL}} originWhitelist={[trustedOrigin]} javaScriptEnabled domStorageEnabled sharedCookiesEnabled thirdPartyCookiesEnabled={false} mixedContentMode="never" geolocationEnabled={false} setSupportMultipleWindows={false} allowsBackForwardNavigationGestures onMessage={onMessage} onNavigationStateChange={navigation => {canGoBack.current = navigation.canGoBack;}} onShouldStartLoadWithRequest={request => shouldNavigate(request.url)} onError={() => setOffline(true)} onHttpError={event => {if (event.nativeEvent.statusCode >= 500) setOffline(true);}} startInLoadingState renderLoading={() => <ActivityIndicator accessibilityLabel="Chargement de Miagbo" color="#174b37" style={styles.loading}/>} />}</SafeAreaView></SafeAreaProvider>; // Afficher le site, ses cookies sécurisés ou un écran de reprise, jamais de page tierce avec accès GPS natif.
} // Terminer le composant principal.
const styles = StyleSheet.create({ // Définir les styles natifs de secours indépendamment du serveur.
  screen:{flex:1,backgroundColor:'#f6f7f2'}, error:{flex:1,justifyContent:'center',padding:32,gap:16}, // Préserver une surface lisible et la place des barres système.
  title:{fontSize:25,fontWeight:'700',color:'#174b37'}, text:{fontSize:15,lineHeight:24,color:'#657165'}, // Hiérarchiser les explications d'erreur.
  button:{backgroundColor:'#174b37',padding:16,borderRadius:12,alignItems:'center'}, buttonText:{color:'white',fontWeight:'600'}, // Donner une cible tactile accessible pour reprendre.
  loading:{position:'absolute',left:0,right:0,top:0,bottom:0}, // Centrer l'indicateur pendant le chargement initial.
}); // Terminer les styles de la coque native.
