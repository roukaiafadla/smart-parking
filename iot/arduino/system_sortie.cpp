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

// ===== OBJETS =====
MFRC522 rfid(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo servo;
 
 // ===== LCD ACCUEIL =====
void afficherAccueil() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Scanner badge");
  lcd.setCursor(0, 1);
  lcd.print("Smart Parking");
}
// ===== VARIABLES =====
volatile bool smokeEvent = false;
volatile bool smokeState = false;

bool gateOpen    = false;
bool openByRFID  = false;

unsigned long openTime     = 0;
unsigned long lastFireSend = 0;

// ===== VARIABLES FUMÉE =====
#define SEUIL_ANALOGIQUE 200  // plus bas = plus sensible (était 400)
bool smokeDetected = false;
#define OPEN_DURATION 3000
#define FIRE_DELAY    30000

// ===== ISR MQ2 =====
void ISR_SMOKE() {
  smokeState = (digitalRead(MQ2_DIGITAL) == LOW);
  smokeEvent = true;
}

// ===== SETUP =====
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
  attachInterrupt(digitalPinToInterrupt(MQ2_DIGITAL), ISR_SMOKE, CHANGE);

  lcd.setCursor(0, 0);
  lcd.print("Smart Parking");
  lcd.setCursor(0, 1);
  lcd.print("Initialisation");
  delay(2000);

  afficherAccueil();
  Serial.println("ARDUINO_READY");
}

// ===== LOOP =====
void loop() {

// ===== FIRE EVENT — analogique + digital =====
int smokeLevel = analogRead(MQ2_ANALOG);
bool digitalSmoke = (digitalRead(MQ2_DIGITAL) == LOW);

// Détection via analogique OU digital
bool fireNow = (smokeLevel > SEUIL_ANALOGIQUE)  digitalSmoke;

if (fireNow && !smokeDetected) {
    smokeDetected = true;

    if (!gateOpen) {
        servo.write(90);
        gateOpen   = true;
        openByRFID = false;
        Serial.println("BARRIER_EMERGENCY_OPEN");
    }

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("!!! INCENDIE !!!");
    lcd.setCursor(0, 1);
    lcd.print("Niv:");
    lcd.print(smokeLevel);

    if (millis() - lastFireSend > FIRE_DELAY) {
        Serial.print("FIRE_ALERT:");
        Serial.println(smokeLevel);
        lastFireSend = millis();
    }

    tone(BUZZER, 800);
    digitalWrite(LED, HIGH);
}

if (!fireNow && smokeDetected) {
    smokeDetected = false;

    noTone(BUZZER);
    digitalWrite(LED, LOW);

    if (gateOpen && !openByRFID) {
        servo.write(0);
        gateOpen = false;
    }

    Serial.println("FIRE_CLEAR");
    afficherAccueil();
}
  

  // ===== RFID — seulement si pas d'incendie =====
  if (!smokeState) {
    lireRFID();
  }

  // ===== AUTO CLOSE après OPEN_DURATION =====
  if (openByRFID && gateOpen && millis() - openTime > OPEN_DURATION) {
    servo.write(0);
    gateOpen    = false;
    openByRFID  = false;
    Serial.println("BARRIER_CLOSED");
    afficherAccueil();
  }
}

// ===== LECTURE RFID =====
void lireRFID() {
  if (!rfid.PICC_IsNewCardPresent()  !rfid.PICC_ReadCardSerial())
    return;

  // Lire exactement 4 bytes
  String uid = "";
  for (byte i = 0; i < 4; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
    if (i < 3) uid += " ";
  }
  uid.toUpperCase();

  // Envoyer au PC avec préfixe UID:
  Serial.println("UID:" + uid);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Verification...");
  // Attendre réponse du PC max 5 secondes
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

// ===== ACCÈS AUTORISÉ =====
void accesOK() {
  digitalWrite(LED, LOW);   // LED éteinte si autorisé
  noTone(BUZZER);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Acces autorise");
  lcd.setCursor(0, 1);
  lcd.print("Bonne journee !");

  servo.write(90);
  gateOpen   = true;
  openByRFID = true;
  openTime   = millis();

  Serial.println("BARRIER_OPEN");
}

// ===== ACCÈS REFUSÉ =====
void accesKO() {
  // LED allumée + buzzer court en cas de refus
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

  digitalWrite(LED, LOW);  // LED éteinte après 2 secondes
  afficherAccueil();
}