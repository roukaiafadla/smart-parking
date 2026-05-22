from __future__ import annotations

import time


def normalize_uid(uid: str) -> str:
    uid_clean = uid.strip().upper().replace("-", "").replace(" ", "")
    return " ".join(uid_clean[index : index + 2] for index in range(0, len(uid_clean), 2))


class RFIDReader:
    def __init__(self):
        try:
            import RPi.GPIO as GPIO
            from mfrc522 import MFRC522
        except ImportError as exc:
            raise RuntimeError(
                "mfrc522/RPi.GPIO is not installed. Run this module on Raspberry Pi, "
                "or use rpi_entry_system.py --test-rfid on a development PC."
            ) from exc

        self.GPIO = GPIO
        try:
            self.reader = MFRC522()
        except ValueError as exc:
            raise RuntimeError(
                "RFID initialization failed because mfrc522 changed the GPIO numbering mode. "
                "Use gpio_mode=BOARD in rpi_config.json, which is the default for this project."
            ) from exc
        self.GPIO.setwarnings(False)

    def read(self, timeout_seconds: float = 10.0) -> str | None:
        start = time.time()
        while time.time() - start < timeout_seconds:
            status, _tag_type = self.reader.MFRC522_Request(self.reader.PICC_REQIDL)
            if status == self.reader.MI_OK:
                status, uid_bytes = self.reader.MFRC522_Anticoll()
                if status == self.reader.MI_OK:
                    uid_4bytes = uid_bytes[:4]
                    return " ".join(f"{value:02X}" for value in uid_4bytes)
            time.sleep(0.1)
        return None

    def close(self) -> None:
        pass
