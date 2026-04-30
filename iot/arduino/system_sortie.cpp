#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <Servo.h>

#define RST_PIN 9
#define SS_PIN 10

MFRC522 rfid(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo servo;

void setup() {
    Serial.begin(9600);
    SPI.begin();
    rfid.PCD_Init();

    lcd.init();
    lcd.backlight();
    lcd.setCursor(0, 0);
    lcd.print("Scannez badge...");

    servo.attach(5);
    servo.write(0);  // barrière fermée
}

void loop() {
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())
        return;

    // Lire UID et formater en hex avec espaces
    String uid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
        if (rfid.uid.uidByte[i] < 0x10) uid += "0";
        uid += String(rfid.uid.uidByte[i], HEX);
        if (i < rfid.uid.size - 1) uid += " ";
    }
    uid.toUpperCase();

    // Envoyer UID au PC via Serial
    Serial.println(uid);

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Verification...");

    // Attendre réponse du PC
    unsigned long start = millis();
    while (!Serial.available()) {
        if (millis() - start > 5000) {
            // Timeout après 5 secondes
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Erreur serveur");
            delay(2000);
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Scannez badge...");
            rfid.PICC_HaltA();
            return;
        }
    }

    String reponse = Serial.readStringUntil('\n');
    reponse.trim();

    if (reponse == "valid") {
        // Accès autorisé
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Acces autorise");
        lcd.setCursor(0, 1);
        lcd.print("Bonne journee !");

        servo.write(90);   // ouvrir barrière
        delay(3000);       // attendre 3 secondes
        servo.write(0);    // fermer barrière

    } else {
        // Accès refusé
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Acces refuse");
        lcd.setCursor(0, 1);
        lcd.print("Tag non autorise");
        delay(2000);
    }

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Scannez badge...");

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    delay(1000);
}