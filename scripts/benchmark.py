import argparse  # Lire une cible et un volume explicitement choisis par l'exploitant.
import concurrent.futures  # Simuler plusieurs recherches simultanées sans dépendance tierce.
import json  # Produire une preuve de mesure lisible et réutilisable.
import math  # Calculer le rang du percentile par la méthode du rang supérieur.
import time  # Mesurer une durée monotone sans dépendre de l'horloge civile.
import urllib.request  # Envoyer de vraies requêtes HTTP au serveur de recette.
from pathlib import Path  # Enregistrer le résultat dans le dossier de documentation.
parser = argparse.ArgumentParser(description='Mesure indicative de recherche sur un environnement de recette connu.')  # Expliquer que le résultat dépend du jeu de données.
parser.add_argument('--url',default='http://127.0.0.1:8000')  # Cibler le serveur local sauf choix explicite.
parser.add_argument('--requests',type=int,default=40)  # Rester sous le throttle anonyme de cent appels par minute par défaut.
parser.add_argument('--workers',type=int,default=4)  # Simuler une faible concurrence de recette.
parser.add_argument('--output',default='docs/performance.local.json')  # Conserver la mesure concrète dans un fichier JSON.
args = parser.parse_args()  # Lire les paramètres validables.
if not 1 <= args.requests <= 90 or not 1 <= args.workers <= 16:  # Borner le coût et respecter la limite anonyme standard.
    parser.error('Utilisez 1 à 90 requêtes et 1 à 16 workers ; une charge supérieure exige un plan dédié.')  # Éviter une saturation involontaire.
url = args.url.rstrip('/') + '/api/v1/vendors/search/?lat=6.1319&lng=1.2228&radius=2000'  # Mesurer le même scénario de recherche autour de Lomé.
def sample(index):  # Mesurer un appel complet et son résultat métier.
    start = time.perf_counter()  # Commencer avant la connexion réseau.
    with urllib.request.urlopen(url,timeout=20) as response:  # Borner l'attente d'une requête individuelle.
        data = json.load(response)  # Inclure le décodage de la réponse dans la durée utilisateur.
    return (time.perf_counter() - start) * 1000, data['count']  # Retourner latence en millisecondes et taille du résultat.
with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:  # Utiliser un pool de taille déclarée.
    values = list(executor.map(sample,range(args.requests)))  # Faire échouer la mesure si une requête HTTP échoue.
latencies = sorted(value[0] for value in values)  # Ordonner les durées pour le percentile.
report = {'requests':args.requests,'workers':args.workers,'results_per_search':values[0][1],'p95_ms':round(latencies[math.ceil(len(latencies)*.95)-1],2),'max_ms':round(max(latencies),2),'mean_ms':round(sum(latencies)/len(latencies),2),'scope':'Mesure locale indicative ; aucun SLA de production validé.'}  # Ne pas extrapoler un petit test à la charge réelle.
Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')  # Conserver les nombres réellement mesurés.
print(json.dumps(report,ensure_ascii=False))  # Présenter un bilan sans position personnelle ni secret.
