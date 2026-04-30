import serial
import requests
import time
import smtplib
import threading
from email.mime.text import MIMEText
from pymongo import MongoClient
from datetime import datetime
from queue import Queue

# ================= CONFIG =================
SERIAL_PORT = "COM3"
BAUD_RATE   = 9600
FLASK_URL   = "http://127.0.0.1:5000/access/api/access"
ALERT_SSE_URL = "http://127.0.0.1:5000/alertes/api/push"   # ← nouvel endpoint

MONGO_URI = "mongodb://localhost:27017"
DB_NAME   = "smart_parking"

EMAIL_EXPEDITEUR = "fadlaroukaia238@gmail.com"
EMAIL_MOT_PASSE  = "wxdt vrtr wyjp omzj"
SMTP_HOST        = "smtp.gmail.com"
SMTP_PORT        = 587

print("--- SMART PARKING BRIDGE ---")
print(f"En écoute sur {SERIAL_PORT}...")

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=10)
time.sleep(2)

# ================= DB =================
def get_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

# ================= EMAIL =================
def envoyer_email_alerte(users, niveau):
    for u in users:
        try:
            msg = MIMEText(
                f"ALERTE INCENDIE\n\n"
                f"Niveau fumée : {niveau}\n"
                f"Heure        : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                f"Evacuez immédiatement !"
            )
            msg["Subject"] = "ALERTE INCENDIE — SMART PARKING"
            msg["From"]    = EMAIL_EXPEDITEUR
            msg["To"]      = u["email"]

            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_EXPEDITEUR, EMAIL_MOT_PASSE)
            server.send_message(msg)
            server.quit()
            print(f"[EMAIL] Envoyé à {u['email']}")
        except Exception as e:
            print(f"[EMAIL ERROR] {e}")

# ================= PUSH DASHBOARD =================
def push_dashboard_event(event_type, payload):
    """Notifie Flask pour diffuser un événement SSE au dashboard."""
    try:
        requests.post(
            ALERT_SSE_URL,
            json={"type": event_type, **payload},
            timeout=2
        )
    except Exception as e:
        print(f"[SSE PUSH ERROR] {e}")

# ================= FIRE =================
def gerer_incendie(niveau):
    db = get_db()
    print(f"[FIRE] Détecté — niveau {niveau}")

    alerte = {
        "niveau":    "critique",
        "message":  f"Détection de fumée — niveau {niveau}",
        "statut":   "active",
        "timestamp": datetime.now(),
    }
    result = db.alertes.insert_one(alerte)

    # Notifier le dashboard en temps réel
    push_dashboard_event("FIRE_ALERT", {
        "niveau": niveau,
        "message": alerte["message"],
        "timestamp": alerte["timestamp"].strftime('%d/%m/%Y %H:%M:%S'),
        "id": str(result.inserted_id)
    })

    # Email dans un thread séparé pour ne pas bloquer le bridge
    users = list(db.users.find({"etat": "actif", "email": {"$exists": True}}))
    threading.Thread(
        target=envoyer_email_alerte,
        args=(users, niveau),
        daemon=True
    ).start()

def fire_clear():
    db = get_db()
    db.alertes.update_many(
        {"statut": "active"},
        {"$set": {"statut": "résolue"}}
    )
    push_dashboard_event("FIRE_CLEAR", {})
    print("[FIRE] Alerte résolue")

# ================= NORMALISATION UID =================
def normaliser_uid(raw):
    uid_clean = raw.strip().upper().replace("-", "")
    if " " not in uid_clean:
        return ' '.join(uid_clean[i:i+2] for i in range(0, len(uid_clean), 2))
    return ' '.join(uid_clean.split())

# ================= LOOP =================
try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode('utf-8').strip()
            if not data:
                continue

            print(f"[Arduino] {data}")

            if data.startswith("FIRE_ALERT:"):
                try:
                    niveau = int(data.split(":")[1])
                    gerer_incendie(niveau)
                except Exception as e:
                    print(f"[FIRE ERROR] {e}")

            elif data == "FIRE_CLEAR":
                fire_clear()

            elif data in ["BARRIER_OPEN", "BARRIER_CLOSED", "BARRIER_EMERGENCY_OPEN"]:
                print(f"[BARRIERE] {data}")

            elif data == "ARDUINO_READY":
                print("[ARDUINO] Connecté et prêt")

            elif data.startswith("UID:"):
                uid_raw       = data[4:]
                uid_formatted = normaliser_uid(uid_raw)
                print(f"[RFID] UID reçu    : '{uid_raw}'")
                print(f"[RFID] UID formaté : '{uid_formatted}'")
                try:
                    response = requests.post(
                        FLASK_URL,
                        json={"uid": uid_formatted},
                        timeout=5
                    )
                    resultat = response.json()
                    status   = resultat.get("status", "error")
                    message  = resultat.get("message", "")
                    print(f"[FLASK] {status} — {message}")
                    ser.write((status + "\n").encode('utf-8'))
                except requests.exceptions.ConnectionError:
                    print("[FLASK] Serveur inaccessible")
                    ser.write(b"error\n")
                except requests.exceptions.Timeout:
                    print("[FLASK] Timeout")
                    ser.write(b"error\n")
                except Exception as e:
                    print(f"[FLASK ERROR] {e}")
                    ser.write(b"error\n")

except KeyboardInterrupt:
    print("\nArrêt du bridge.")
    ser.close()