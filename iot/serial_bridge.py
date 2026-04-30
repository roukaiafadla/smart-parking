import serial
import requests
import time

SERIAL_PORT = "COM3"
BAUD_RATE = 9600
FLASK_URL = "http://127.0.0.1:5000/access/api/access"

print("--- Bridge Serial → Flask ---")
print(f"En écoute sur {SERIAL_PORT}...")

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=10)
time.sleep(2)

try:
    while True:
        if ser.in_waiting > 0:
            uid_raw = ser.readline().decode('utf-8').strip()

            if not uid_raw:
                continue

            # Arduino envoie déjà en HEX avec espaces ex: "20 B7 5F 4D"
            # On normalise juste — majuscules + espaces propres
            uid_clean = uid_raw.strip().upper().replace("-", "")
            
            # Si l'Arduino envoie sans espaces ex: "20B75F4D"
            # on ajoute les espaces toutes les 2 caractères
            if " " not in uid_clean:
                uid_formatted = ' '.join(uid_clean[i:i+2] for i in range(0, len(uid_clean), 2))
            else:
                uid_formatted = ' '.join(uid_clean.split())

            print(f"UID brut reçu : '{uid_raw}'")
            print(f"UID formaté   : '{uid_formatted}'")

            try:
                response = requests.post(
                    FLASK_URL,
                    json={"uid": uid_formatted},
                    timeout=5
                )
                resultat = response.json()
                status = resultat.get("status", "error")
                print(f"Réponse Flask : {status} — {resultat.get('message')}")

                # Envoyer la réponse à l'Arduino
                ser.write((status + "\n").encode('utf-8'))

            except requests.exceptions.ConnectionError:
                print("⚠️ Flask inaccessible")
                ser.write(b"error\n")
            except requests.exceptions.Timeout:
                print("⚠️ Timeout Flask")
                ser.write(b"error\n")
            except Exception as e:
                print(f"⚠️ Erreur : {e}")
                ser.write(b"error\n")

except KeyboardInterrupt:
    print("\nArrêt du bridge.")
    ser.close()