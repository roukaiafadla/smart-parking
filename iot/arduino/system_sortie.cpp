/*
============================================================
 SMART PARKING — ARDUINO UNO (SORTIE)
 RFID + MQ2 + LCD + SERVO + BUZZER
============================================================
*/


#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <Servo.h>


// ===== PINS =====
#define SS_PIN      10
#define RST_PIN     9
#define SERVO_PIN   5
#define MQ2_ANALOG  A0
#define MQ2_DIGITAL 2
#define BUZZER      3
#define LED         4


// ===== SEUIL FUMÉE =====
#define SEUIL_ANALOGIQUE 200


// ===== OBJETS =====
MFRC522 rfid(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo servo;


// ===== VARIABLES =====
bool gateOpen      = false;
bool openByRFID    = false;
bool smokeDetected = false;


unsigned long openTime     = 0;
unsigned long lastFireSend = 0;


#define OPEN_DURATION 3000
#define FIRE_DELAY    30000


// ============================================================
// SETUP
// ============================================================
void setup() {


  Serial.begin(9600);


  SPI.begin();
  rfid.PCD_Init();


  lcd.init();
  lcd.backlight();


  servo.attach(SERVO_PIN);
  servo.write(0);


  pinMode(BUZZER, OUTPUT);
  pinMode(LED, OUTPUT);


  digitalWrite(BUZZER, LOW);
  digitalWrite(LED, LOW);


  pinMode(MQ2_DIGITAL, INPUT);


  lcd.setCursor(0, 0);
  lcd.print("Smart Parking");
  lcd.setCursor(0, 1);
  lcd.print("Initialisation");


  delay(2000);


  afficherAccueil();


  Serial.println("ARDUINO_READY");
}


// ============================================================
// LOOP
// ============================================================
void loop() {
  // ==========================================================
// COMMANDE ADMIN VIA SERIAL
// ==========================================================
if (Serial.available()) {                    // ← plus de !smokeDetected
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();


  if (cmd == "OPEN_BARRIER") {
    servo.write(90);
    gateOpen   = true;
    openByRFID = true;
    openTime   = millis();


    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Ouverture admin");
    lcd.setCursor(0, 1);
    lcd.print("Barriere ouverte");


    Serial.println("BARRIER_OPEN");
  }
}


  // ===== LECTURE MQ2 =====
  int smokeLevel = analogRead(MQ2_ANALOG);


  // ===== AFFICHAGE CONSOLE =====
  Serial.print("MQ2=");
  Serial.print(smokeLevel);
  Serial.print(" | Seuil=");
  Serial.println(SEUIL_ANALOGIQUE);


  bool digitalSmoke = (digitalRead(MQ2_DIGITAL) == LOW);


  bool fireNow =
    (smokeLevel > SEUIL_ANALOGIQUE) ||
    digitalSmoke;


  // ==========================================================
  // INCENDIE DÉTECTÉ
  // ==========================================================
  if (fireNow && !smokeDetected) {


    smokeDetected = true;


    Serial.println("!!! FIRE DETECTED !!!");


    // ===== OUVERTURE BARRIÈRE =====
    if (!gateOpen) {


      servo.write(90);


      gateOpen   = true;
      openByRFID = false;


      Serial.println("BARRIER_EMERGENCY_OPEN");
    }


    // ===== LCD =====
    lcd.clear();


    lcd.setCursor(0, 0);
    lcd.print("!!! INCENDIE !!!");


    lcd.setCursor(0, 1);
    lcd.print("Niv:");
    lcd.print(smokeLevel);


    // ===== ENVOI ALERTE PC =====
    if (millis() - lastFireSend > FIRE_DELAY) {


      Serial.print("FIRE_ALERT:");
      Serial.println(smokeLevel);


      lastFireSend = millis();
    }


    // ===== BUZZER + LED =====
    tone(BUZZER, 800);


    digitalWrite(LED, HIGH);
  }


  // ==========================================================
  // FIN INCENDIE
  // ==========================================================
  if (!fireNow && smokeDetected) {


    smokeDetected = false;


    Serial.println("FIRE_CLEAR");


    // ===== STOP ALARME =====
    noTone(BUZZER);


    digitalWrite(LED, LOW);


    // ===== FERMER SI OUVERT PAR INCENDIE =====
    if (gateOpen && !openByRFID) {


      servo.write(0);


      gateOpen = false;
    }


    afficherAccueil();
  }


  // ==========================================================
  // RFID (SEULEMENT SI PAS INCENDIE)
  // ==========================================================
  if (!smokeDetected) {


    lireRFID();
  }


  // ==========================================================
  // AUTO CLOSE
  // ==========================================================
  if (
    openByRFID &&
    gateOpen &&
    millis() - openTime > OPEN_DURATION
  ) {


    servo.write(0);


    gateOpen   = false;
    openByRFID = false;


    Serial.println("BARRIER_CLOSED");


    afficherAccueil();
  }


  delay(500);
}


// ============================================================
// LECTURE RFID
// ============================================================
void lireRFID() {


  if (
    !rfid.PICC_IsNewCardPresent() ||
    !rfid.PICC_ReadCardSerial()
  ) {
    return;
  }


  // ===== LIRE UID =====
  String uid = "";


  for (byte i = 0; i < 4; i++) {


    if (rfid.uid.uidByte[i] < 0x10)
      uid += "0";


    uid += String(rfid.uid.uidByte[i], HEX);


    if (i < 3)
      uid += " ";
  }


  uid.toUpperCase();


  // ===== ENVOI UID =====
  Serial.println("UID:" + uid);


  lcd.clear();


  lcd.setCursor(0, 0);
  lcd.print("Verification...");


  // ===== ATTENTE REPONSE PC =====
  unsigned long start = millis();


  while (!Serial.available()) {


    if (millis() - start > 5000) {


      lcd.clear();


      lcd.setCursor(0, 0);
      lcd.print("Erreur serveur");


      delay(2000);


      afficherAccueil();


      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();


      return;
    }
  }


  String rep = Serial.readStringUntil('\n');


  rep.trim();


  if (rep == "valid") {


    accesOK();


  } else {


    accesKO();
  }


  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}


// ============================================================
// ACCÈS AUTORISÉ
// ============================================================
void accesOK() {


  digitalWrite(LED, LOW);


  noTone(BUZZER);


  lcd.clear();


  lcd.setCursor(0, 0);
  lcd.print("Acces autorise");


  lcd.setCursor(0, 1);
  lcd.print("Bonne journee !");


  servo.write(90);


  gateOpen   = true;
  openByRFID = true;


  openTime = millis();


  Serial.println("BARRIER_OPEN");
}


// ============================================================
// ACCÈS REFUSÉ
// ============================================================
void accesKO() {


  digitalWrite(LED, HIGH);


  tone(BUZZER, 1000);


  delay(500);


  noTone(BUZZER);


  lcd.clear();


  lcd.setCursor(0, 0);
  lcd.print("Acces refuse");


  lcd.setCursor(0, 1);
  lcd.print("Tag non autorise");


  delay(2000);


  digitalWrite(LED, LOW);


  afficherAccueil();
}


// ============================================================
// LCD ACCUEIL
// ============================================================
void afficherAccueil() {


  lcd.clear();


  lcd.setCursor(0, 0);
  lcd.print("Scanner badge");


  lcd.setCursor(0, 1);
  lcd.print("Smart Parking");
}

