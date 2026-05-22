from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from api_client import AccessApiClient
from camera_capture import CameraCapture
from gate_controller import GateController
from rfid_reader import RFIDReader, normalize_uid
from vehicle_trigger import UltrasonicVehicleTrigger


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "rpi_config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi smart parking entry system.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to rpi_config.json.")
    parser.add_argument("--test-image", type=Path, help="Run without Pi hardware using this image.")
    parser.add_argument("--test-rfid", help="Run without Pi hardware using this RFID UID.")
    parser.add_argument("--test-ocr-only", action="store_true", help="OCR the whole test image.")
    parser.add_argument("--no-api", action="store_true", help="Do not call Flask API in test mode.")
    parser.add_argument("--once", action="store_true", help="Process one car and exit in live mode.")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for EasyOCR if available.")
    parser.add_argument("--local-ocr", action="store_true", help="Run YOLO/EasyOCR locally on this machine.")
    parser.add_argument("--remote-ocr", action="store_true", help="Send the image to the PC OCR backend.")
    parser.add_argument(
        "--skip-trigger",
        action="store_true",
        help="Skip ultrasonic waiting and capture immediately. Useful while debugging sensor wiring.",
    )
    parser.add_argument(
        "--manual-capture",
        action="store_true",
        help="When --skip-trigger is used, wait for Enter before each capture.",
    )
    parser.add_argument(
        "--no-lcd",
        action="store_true",
        help="Disable the I2C LCD display and print LCD messages to logs only.",
    )
    parser.add_argument(
        "--ultrasonic-test",
        action="store_true",
        help="Only test the ultrasonic sensor and print distance/debug values.",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def setup_logging(config: dict[str, Any]) -> None:
    log_dir = project_path(config.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "entry_system.log", encoding="utf-8"),
        ],
    )


class Display:
    def __init__(
        self,
        enabled: bool,
        i2c_address: str | int = "0x27",
        i2c_port: int = 1,
        cols: int = 16,
        rows: int = 2,
        expander: str = "PCF8574",
        fail_fast: bool = False,
    ):
        self.lcd = None
        if not enabled:
            logging.info("LCD disabled; messages will be printed only.")
            return

        try:
            from RPLCD.i2c import CharLCD
        except ImportError:
            logging.warning("RPLCD is not installed; LCD messages will be printed only.")
            return

        try:
            address = int(i2c_address, 0) if isinstance(i2c_address, str) else int(i2c_address)
            self.lcd = CharLCD(expander, address, port=i2c_port, cols=cols, rows=rows)
        except (OSError, ValueError) as exc:
            self.lcd = None
            message = (
                "LCD initialization failed at address "
                f"{i2c_address} on I2C bus {i2c_port}: {exc}. "
                "Continuing without LCD. Check wiring, run `i2cdetect -y 1`, "
                "or set lcd_enabled=false / use --no-lcd."
            )
            if fail_fast:
                raise RuntimeError(message) from exc
            logging.warning(message)

    def show(self, line1: str, line2: str = "") -> None:
        logging.info("[LCD] %s | %s", line1, line2)
        if not self.lcd:
            return
        try:
            self.lcd.clear()
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1[:16])
            if line2:
                self.lcd.cursor_pos = (1, 0)
                self.lcd.write_string(line2[:16])
        except OSError as exc:
            logging.warning("LCD write failed: %s. Disabling LCD for this run.", exc)
            self.lcd = None

    def close(self) -> None:
        if self.lcd:
            try:
                self.lcd.clear()
            except OSError as exc:
                logging.warning("LCD cleanup failed: %s", exc)


def processing_mode(args: argparse.Namespace, config: dict[str, Any]) -> str:
    if args.local_ocr and args.remote_ocr:
        raise ValueError("Use only one of --local-ocr or --remote-ocr.")
    if args.local_ocr:
        return "local"
    if args.remote_ocr:
        return "remote"
    return str(config.get("processing_mode", "remote")).strip().lower()


def build_plate_reader(config: dict[str, Any], gpu_override: bool = False):
    from plate_reader import PlateReader

    return PlateReader(
        model_path=project_path(config.get("model_path", "model.onnx")),
        languages=config.get("languages"),
        gpu=bool(gpu_override or config.get("gpu", False)),
        confidence=float(config.get("detector_confidence", 0.5)),
        search_roots=[ROOT.parent],
    )


def save_annotated_image(config: dict[str, Any], source_image: Path, annotated_image, plates: list[dict]) -> Path:
    import cv2
    from plate_reader import default_output_path, draw_annotations

    output_dir = project_path(config.get("output_dir", "outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = default_output_path(source_image, output_dir)
    draw_annotations(annotated_image, plates)
    cv2.imwrite(str(output_path), annotated_image)
    return output_path


def should_use_ocr_only(config: dict[str, Any], force_ocr_only: bool = False) -> bool:
    return force_ocr_only or config.get("ocr_mode", "auto") == "ocr_only"


def verify_with_api(
    config: dict[str, Any],
    uid: str,
    plate_payload: dict[str, Any],
    image_path: Path,
    no_api: bool = False,
) -> dict[str, Any]:
    if no_api:
        return {"status": "skipped", "message": "API call skipped"}

    api = AccessApiClient(
        server_url=config["server_url"],
        timeout_seconds=float(config.get("api_timeout_seconds", 5)),
        image_server_url=config.get("image_server_url"),
    )
    return api.verify_access(
        uid=uid,
        matricule=plate_payload["matricule"],
        ocr_confidence=plate_payload.get("ocr_confidence"),
        detection_confidence=plate_payload.get("detection_confidence"),
        image_path=image_path,
        device_id=config.get("device_id"),
        distance_cm=plate_payload.get("distance_cm"),
    )


def verify_image_with_api(
    config: dict[str, Any],
    uid: str,
    image_path: Path,
    distance_cm: float | None = None,
    no_api: bool = False,
) -> dict[str, Any]:
    if no_api:
        return {
            "status": "skipped",
            "authorized": False,
            "message": "API image upload skipped",
            "image_path": str(image_path),
        }

    api = AccessApiClient(
        server_url=config["server_url"],
        image_server_url=config.get("image_server_url"),
        timeout_seconds=float(config.get("api_timeout_seconds", 120)),
        connect_timeout_seconds=float(config.get("api_connect_timeout_seconds", 10)),
    )
    return api.verify_access_image(
        uid=uid,
        image_path=image_path,
        device_id=config.get("device_id"),
        distance_cm=distance_cm,
    )


def run_test_mode(args: argparse.Namespace, config: dict[str, Any]) -> int:
    if not args.test_image:
        print("--test-image is required for test mode.")
        return 2

    uid = normalize_uid(args.test_rfid or config.get("test_rfid_uid", ""))
    if not uid:
        print("[RFID] Missing --test-rfid.")
        return 2

    mode = processing_mode(args, config)
    if mode == "remote":
        image_path = project_path(args.test_image)
        if not image_path.exists():
            image_path = args.test_image
        print(f"[MODE] Remote OCR on PC backend")
        print(f"[RFID] UID: {uid}")
        print(f"[CAMERA] Image: {image_path}")
        response = verify_image_with_api(
            config=config,
            uid=uid,
            image_path=image_path,
            no_api=args.no_api,
        )
        print(f"[API] {response}")
        return 0 if response.get("status") in {"valid", "skipped"} else 1

    if mode != "local":
        print(f"Unknown processing_mode: {mode}. Use 'remote' or 'local'.")
        return 2

    reader = build_plate_reader(config, gpu_override=args.gpu)
    plate_payload, annotated_image = reader.read(
        args.test_image,
        ocr_only=should_use_ocr_only(config, args.test_ocr_only),
        fallback_ocr=bool(config.get("fallback_ocr", True)),
    )
    resolved_image = Path(plate_payload["image"])
    output_path = save_annotated_image(config, resolved_image, annotated_image, plate_payload["plates"])

    print(f"[OCR] Image: {resolved_image}")
    print(f"[OCR] Annotated output: {output_path}")
    print(f"[OCR] Matricule: {plate_payload['matricule'] or '(not detected)'}")
    print(f"[OCR] Confidence: {plate_payload['ocr_confidence']:.2f}")

    if not plate_payload["matricule"]:
        print("[ACCESS] Refused: plate not readable.")
        return 1

    response = verify_with_api(
        config=config,
        uid=uid,
        plate_payload=plate_payload,
        image_path=output_path,
        no_api=args.no_api,
    )
    print(f"[API] {response}")
    return 0 if response.get("status") in {"valid", "skipped"} else 1


def run_live_mode(args: argparse.Namespace, config: dict[str, Any]) -> int:
    setup_logging(config)
    gpio_mode = config.get("gpio_mode", "BOARD")
    gpio_pin_numbering = config.get("gpio_pin_numbering", "BCM")
    display = Display(
        enabled=bool(config.get("lcd_enabled", True)) and not args.no_lcd,
        i2c_address=config.get("lcd_i2c_address", "0x27"),
        i2c_port=int(config.get("lcd_i2c_port", 1)),
        cols=int(config.get("lcd_cols", 16)),
        rows=int(config.get("lcd_rows", 2)),
        expander=config.get("lcd_expander", "PCF8574"),
        fail_fast=bool(config.get("lcd_fail_fast", False)),
    )
    resources: list[Any] = [display]

    try:
        display.show("Smart Parking", "Initialisation")
        mode = processing_mode(args, config)
        if mode not in {"remote", "local"}:
            raise ValueError("processing_mode must be 'remote' or 'local'.")
        logging.info("Processing mode: %s", mode)
        reader = build_plate_reader(config, gpu_override=args.gpu) if mode == "local" else None
        vehicle_trigger = None
        if not args.skip_trigger:
            vehicle_trigger = UltrasonicVehicleTrigger(
                trig_pin=int(config["trig_pin"]),
                echo_pin=int(config["echo_pin"]),
                distance_max_cm=float(config["distance_max_cm"]),
                poll_seconds=float(config.get("distance_poll_seconds", 0.5)),
                echo_timeout_seconds=float(config.get("echo_timeout_seconds", 0.08)),
                gpio_mode=gpio_mode,
                pin_numbering=gpio_pin_numbering,
            )
        camera = CameraCapture(
            capture_dir=project_path(config.get("capture_dir", "captures")),
            warmup_seconds=float(config.get("camera_warmup_seconds", 2)),
            resolution=config.get("camera_resolution"),
        )
        rfid = RFIDReader()
        gate = GateController(
            servo_pin=int(config["servo_pin"]),
            open_duration_seconds=float(config.get("open_duration_seconds", 3)),
            gpio_mode=gpio_mode,
            pin_numbering=gpio_pin_numbering,
        )
        resources.extend(resource for resource in [vehicle_trigger, camera, rfid, gate] if resource)

        display.show("Pret", "Approchez")

        while True:
            if mode == "remote":
                display.show("Pret", "Scannez badge")
                logging.info("Waiting for RFID card")
                uid = rfid.read(timeout_seconds=float(config.get("rfid_timeout_seconds", 10)))
                if not uid:
                    logging.info("RFID timeout")
                    display.show("Badge absent", "Reessayez")
                    time.sleep(2)
                    if args.once:
                        return 1
                    continue

                logging.info("RFID UID: %s", uid)
                display.show("Badge OK", "Approchez")

                if vehicle_trigger:
                    distance_cm = vehicle_trigger.wait_for_vehicle()
                else:
                    if args.manual_capture:
                        input("Press Enter to capture a car photo...")
                    distance_cm = None

                if distance_cm is None:
                    logging.info("Vehicle trigger skipped by operator")
                else:
                    logging.info("Vehicle detected at %.1f cm", distance_cm)

                display.show("Photo plaque", "")
                image_path = camera.capture_image()
                logging.info("Captured image: %s", image_path)

                display.show("Envoi au PC", "Verification")
                response = verify_image_with_api(
                    config=config,
                    uid=uid,
                    image_path=image_path,
                    distance_cm=distance_cm,
                )
                logging.info("PC OCR/API response: %s", response)

                matricule = response.get("matricule") or response.get("ocr", {}).get("matricule") or ""
                if response.get("status") == "valid" or response.get("authorized") is True:
                    display.show("Acces autorise", str(matricule or response.get("message", ""))[:16])
                    gate.open()
                    result_code = 0
                else:
                    display.show("Acces refuse", str(response.get("message", ""))[:16])
                    time.sleep(2)
                    result_code = 1

                display.show("Pret", "Scannez badge")
                if args.once:
                    return result_code
                continue

            if vehicle_trigger:
                distance_cm = vehicle_trigger.wait_for_vehicle()
            else:
                if args.manual_capture:
                    input("Press Enter to capture a car photo...")
                distance_cm = None
            if distance_cm is None:
                logging.info("Vehicle trigger skipped by operator")
            else:
                logging.info("Vehicle detected at %.1f cm", distance_cm)
            display.show("Vehicule detecte", "Photo...")

            image_path = camera.capture_image()
            logging.info("Captured image: %s", image_path)

            display.show("Lecture plaque", "")
            if reader is None:
                raise RuntimeError("Local OCR mode requires the plate reader.")
            plate_payload, annotated_image = reader.read(
                image_path,
                ocr_only=should_use_ocr_only(config),
                fallback_ocr=bool(config.get("fallback_ocr", True)),
            )
            plate_payload["distance_cm"] = distance_cm
            output_path = save_annotated_image(config, image_path, annotated_image, plate_payload["plates"])

            matricule = plate_payload["matricule"]
            if not matricule:
                logging.info("Plate not readable for image %s", image_path)
                display.show("Plaque illisible", "Acces refuse")
                time.sleep(2)
                display.show("Pret", "Approchez")
                if args.once:
                    return 1
                continue

            logging.info("Matricule detected: %s", matricule)
            display.show("Scannez badge", matricule[:16])
            uid = rfid.read(timeout_seconds=float(config.get("rfid_timeout_seconds", 10)))

            if not uid:
                logging.info("RFID timeout")
                display.show("Badge absent", "Acces refuse")
                time.sleep(2)
                display.show("Pret", "Approchez")
                if args.once:
                    return 1
                continue

            logging.info("RFID UID: %s", uid)
            display.show("Verification", "")
            response = verify_with_api(
                config=config,
                uid=uid,
                plate_payload=plate_payload,
                image_path=output_path,
            )
            logging.info("API response: %s", response)

            if response.get("status") == "valid":
                display.show("Acces autorise", str(response.get("message", ""))[:16])
                gate.open()
            else:
                display.show("Acces refuse", str(response.get("message", ""))[:16])
                time.sleep(2)

            display.show("Pret", "Approchez")
            if args.once:
                return 0

    except KeyboardInterrupt:
        logging.info("System stopped by user.")
        return 0
    finally:
        for resource in reversed(resources):
            close = getattr(resource, "close", None)
            if close:
                try:
                    close()
                except Exception as exc:
                    logging.warning("Cleanup failed for %s: %s", resource.__class__.__name__, exc)
        try:
            import RPi.GPIO as GPIO

            GPIO.cleanup()
        except ImportError:
            pass


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    test_mode = bool(args.test_image or args.test_rfid)

    if args.ultrasonic_test:
        setup_logging(config)
        gpio_mode = config.get("gpio_mode", "BOARD")
        gpio_pin_numbering = config.get("gpio_pin_numbering", "BCM")
        trigger = UltrasonicVehicleTrigger(
            trig_pin=int(config["trig_pin"]),
            echo_pin=int(config["echo_pin"]),
            distance_max_cm=float(config["distance_max_cm"]),
            poll_seconds=float(config.get("distance_poll_seconds", 0.5)),
            echo_timeout_seconds=float(config.get("echo_timeout_seconds", 0.08)),
            gpio_mode=gpio_mode,
            pin_numbering=gpio_pin_numbering,
        )
        try:
            while True:
                distance = trigger.measure_distance_cm()
                trig_level, echo_level = trigger.pin_levels()
                if distance is None:
                    print(
                        "[ULTRASONIC TEST] timeout "
                        f"({trigger.last_error}; TRIG={trig_level}, ECHO={echo_level})"
                    )
                else:
                    print(f"[ULTRASONIC TEST] distance={distance} cm")
                time.sleep(float(config.get("distance_poll_seconds", 0.5)))
        except KeyboardInterrupt:
            return 0

    if test_mode:
        return run_test_mode(args, config)
    return run_live_mode(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
