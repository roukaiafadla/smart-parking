import serial
import requests
import time

SERIAL_PORT = "COM3"
BAUD_RATE   = 9600
SERVER_URL  = "http://10.37.152.92:5000/api/access/entree"

def clean_uid(uid_raw):
    """
    Arduino envoie : '20 B7 5F 4D 85'
    On garde ce format avec espaces — identique à la DB
    """
    return uid_raw.strip().upper()

print("--- Bridge Serial → Flask ---")
print(f"En écoute sur {SERIAL_PORT}...")

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)

    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()

            if not line or line.startswith("DEBUG"):
                print(f"[DEBUG Arduino] {line}")
                continue

            uid = clean_uid(line)
            print(f"\nUID reçu    : '{line}'")
            print(f"UID nettoyé : '{uid}'")

            try:
                response = requests.post(
                    SERVER_URL,
                    json={"id_tag": uid},
                    timeout=5
                )
                data = response.json()
                print(f"Réponse Flask : {data}")

                if data.get("autorise") == True:
                    print("✅ ACCÈS AUTORISÉ —", data.get("message"))
                    ser.write(b"valid\n")
                else:
                    print("❌ ACCÈS REFUSÉ —", data.get("message"))
                    ser.write(b"refuse\n")

            except requests.exceptions.ConnectionError:
                print("❌ Serveur Flask inaccessible")
                ser.write(b"erreur\n")
            except requests.exceptions.Timeout:
                print("❌ Timeout serveur")
                ser.write(b"erreur\n")
            except Exception as e:
                print(f"❌ Erreur inattendue : {e}")
                ser.write(b"erreur\n")

except KeyboardInterrupt:
    print("\nArrêt du bridge.")
    ser.close()
except serial.SerialException as e:
    print(f"❌ Erreur port série : {e}")