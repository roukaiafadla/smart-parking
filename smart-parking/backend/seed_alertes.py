from pymongo import MongoClient
from datetime import datetime, timedelta
import random

client = MongoClient("mongodb://localhost:27017/")
db = client["smart_parking"]

alertes = []
niveaux = ['critique', 'critique', 'warning']
statuts = ['active', 'résolue', 'résolue']

for i in range(8):
    alertes.append({
        'niveau': random.choice(niveaux),
        'message': random.choice([
            'Détection de fumée — Zone A',
            'Détection de fumée — Zone B',
            'Capteur déclenché — Entrée parking',
            'Alerte incendie — Niveau 1',
        ]),
        'statut': random.choice(statuts),
        'timestamp': datetime.now() - timedelta(hours=random.randint(0, 120)),
    })

db.alertes.insert_many(alertes)
print("Done —", len(alertes), "alertes insérées")