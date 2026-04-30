import serial
import requests
import time
import smtplib
from email.mime.text import MIMEText
from pymongo import MongoClient
from datetime import datetime

# ================= CONFIG =================
SERIAL_PORT = "COM3"
BAUD_RATE   = 9600
FLASK_URL   = "http://127.0.0.1:5000/access/api/access"

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

# ================= FIRE =================
def gerer_incendie(niveau):
    db = get_db()
    print(f"[FIRE] Détecté — niveau {niveau}")

    # Enregistrer alerte dans MongoDB
    db.alertes.insert_one({
        "niveau":    "critique",
        "message":  f"Détection de fumée — niveau {niveau}",
        "statut":   "active",
        "timestamp": datetime.now(),
    })

    # Envoyer email à tous les clients actifs
    users = list(db.users.find({"etat": "actif", "email": {"$exists": True}}))
    envoyer_email_alerte(users, niveau)


def fire_clear():
    db = get_db()
    db.alertes.update_many(
        {"statut": "active"},
        {"$set": {"statut": "résolue"}}
    )
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

            # ── FIRE ALERT ──
            if data.startswith("FIRE_ALERT:"):
                try:
                    niveau = int(data.split(":")[1])
                    gerer_incendie(niveau)
                except Exception as e:
                    print(f"[FIRE ERROR] {e}")

            # ── FIRE CLEAR ──
            elif data == "FIRE_CLEAR":
                fire_clear()

            # ── BARRIER STATUS ──
            elif data in ["BARRIER_OPEN", "BARRIER_CLOSED", "BARRIER_EMERGENCY_OPEN"]:
                print(f"[BARRIERE] {data}")

            # ── ARDUINO READY ──
            elif data == "ARDUINO_READY":
                print("[ARDUINO] Connecté et prêt")

            # ── RFID UID ──
            elif data.startswith("UID:"):
                uid_raw = data[4:]  # supprimer le préfixe "UID:"
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

                    # Envoyer réponse à l'Arduino
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