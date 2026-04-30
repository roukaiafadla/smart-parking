import RPi.GPIO as GPIO
from mfrc522 import MFRC522
import requests
import time

SERVER_URL = "http://10.37.152.92:5000/access/api/access"

GPIO.setwarnings(False)
reader = MFRC522()  # pas SimpleMFRC522

print("--- SYSTÈME DE CONTRÔLE D'ACCÈS ---")
print("Scannez votre badge...")

try:
    while True:
        status, TagType = reader.MFRC522_Request(reader.PICC_REQIDL)

        if status == reader.MI_OK:
            status, uid_bytes = reader.MFRC522_Anticoll()

            if status == reader.MI_OK:
                # Lire seulement les 4 premiers bytes comme l'Arduino
                uid_4bytes = uid_bytes[:4]
                uid_formatted = ' '.join(f'{b:02X}' for b in uid_4bytes)

                print(f"\nTag détecté : {uid_formatted}")

                try:
                    response = requests.post(
                        SERVER_URL,
                        json={"uid": uid_formatted},
                        timeout=3
                    )
                    print("Status HTTP:", response.status_code)
                    print("Réponse brute:", response.text)

                    resultat = response.json()

                    if resultat.get("status") == "valid":
                        print("✅ ACCÈS AUTORISÉ —", resultat.get("message"))
                    else:
                        print("❌ ACCÈS REFUSÉ —", resultat.get("message"))

                except requests.exceptions.ConnectionError:
                    print("⚠️ Serveur Flask inaccessible")
                except requests.exceptions.Timeout:
                    print("⚠️ Timeout")
                except requests.exceptions.JSONDecodeError:
                    print("⚠️ Réponse invalide")

                time.sleep(2)

except KeyboardInterrupt:
    print("\nArrêt du système.")
    GPIO.cleanup()