# Smart Parking OCR + RFID Implementation Guide

This guide explains how to modify the current project so it works with the following scenario:

1. A car approaches the Raspberry Pi camera.
2. The Raspberry Pi detects that the car is close.
3. The Raspberry Pi captures a photo of the car.
4. The photo is sent to the AI/OCR model.
5. The model extracts the license plate text.
6. The Raspberry Pi reads the RFID card.
7. The Raspberry Pi sends both the plate number and RFID UID to the Flask API.
8. The API checks MongoDB to verify:
   - the RFID card exists and is active
   - the matricule/license plate exists
   - the RFID card and vehicle belong to the same user
9. If access is valid, the barrier opens.
10. The result is logged.

## Current Folder Analysis

The workspace is:

```text
C:\Users\aaden\Desktop\model-ocr
```

It contains two important projects:

```text
model-ocr/
  european-license-plate-recognition/
  smart-parking/
  pass.py
  plaque2.jpeg
  plaque3.jpeg
  plaque4.jpeg
  last_capture.jpeg
```

## OCR Model Project

Path:

```text
C:\Users\aaden\Desktop\model-ocr\european-license-plate-recognition
```

Important files:

```text
european-license-plate-recognition/
  model.onnx
  detect_plate.py
  config.json
  ocr_config.json
  requirements.txt
  README.md
  MODEL_EXPLANATION.md
  examples/
  outputs/
```

### `model.onnx`

This is the YOLO license plate detection model.

It detects the location of the license plate in an image. It does not read the text by itself.

### `detect_plate.py`

This is the current implementation script.

Current behavior:

```text
input image
-> YOLO detects plate position
-> script crops plate area
-> EasyOCR reads plate text
-> script saves annotated output image
```

It also supports OCR-only mode:

```powershell
py -3 detect_plate.py plaque2.jpeg --ocr-only
```

This is useful when the image is already cropped to the license plate.

### `config.json`

This says the detector is:

```text
model_type: YOLOv12n
task: license_plate_detection
input_size: 640 x 640
num_classes: 1
class_names: license_plate
```

### `ocr_config.json`

This describes the OCR engine:

```text
library: EasyOCR
supported languages: en, de, fr, es, it, nl
gpu_enabled: false
```

## Smart Parking Project

Path:

```text
C:\Users\aaden\Desktop\model-ocr\smart-parking
```

Important structure:

```text
smart-parking/
  backend/
    run.py
    app/
      __init__.py
      config.py
      routes/
        access.py
        access_entree.py
        users.py
        vehicles.py
        tags.py
  iot/
    raspberry/
      system_accessv1.py
    arduino/
      system_sortie.cpp
    serial_handler.py
```

## Existing Backend API

The most important route for this scenario is:

```text
POST /access/api/entree
```

File:

```text
C:\Users\aaden\Desktop\model-ocr\smart-parking\backend\app\routes\access_entree.py
```

Expected request body:

```json
{
  "uid": "AA BB CC DD",
  "matricule": "5678912034"
}
```

Current backend logic:

1. Reads `uid`.
2. Reads `matricule`.
3. Searches for an active user:

```python
db.users.find_one({"id_tag": uid, "etat": "actif"})
```

4. Searches for a vehicle owned by that user:

```python
db.vehicules.find_one({
    "user_id": user.get("_id"),
    "matricule": matricule
})
```

5. Writes a document in:

```text
access_logs
```

6. Returns:

```json
{
  "status": "valid",
  "message": "User Name"
}
```

or:

```json
{
  "status": "error",
  "message": "Reason"
}
```

## Important Existing Problem

There is an existing file:

```text
C:\Users\aaden\Desktop\model-ocr\pass.py
```

It already contains Raspberry Pi logic for:

- ultrasonic sensor
- RFID reader
- Picamera2 camera
- LCD display
- servo barrier
- Flask API call

But it has two problems:

1. It uses `pytesseract` instead of the current YOLO + EasyOCR model.
2. It sends requests to:

```text
/access/api/access
```

That endpoint only validates RFID. It does not validate the matricule.

For the desired scenario, the Raspberry Pi must send to:

```text
/access/api/entree
```

## Target Architecture

The final implementation should be split into small modules instead of one large script.

Proposed structure:

```text
european-license-plate-recognition/
  plate_reader.py
  api_client.py
  camera_capture.py
  vehicle_trigger.py
  rfid_reader.py
  gate_controller.py
  rpi_entry_system.py
  rpi_config.json
```

## Proposed Files To Create

### 1. `plate_reader.py`

Purpose:

Convert the current OCR logic from `detect_plate.py` into reusable functions.

Responsibilities:

- load YOLO model once
- load EasyOCR reader once
- read a full car image
- detect plate region
- crop the plate
- extract the text
- return clean plate result

Example function:

```python
def read_plate(image_path: Path) -> dict:
    return {
        "text": "5678912034",
        "ocr_confidence": 0.89,
        "detection_confidence": 0.74,
        "box": [10, 40, 300, 90],
        "image_path": str(image_path)
    }
```

Why this is needed:

The Raspberry Pi script should call a function, not execute the CLI script directly.

### 2. `camera_capture.py`

Purpose:

Capture images from the Raspberry Pi camera.

Responsibilities:

- initialize `Picamera2`
- capture a photo
- save it to a `captures/` folder
- return the saved image path

Example function:

```python
def capture_image() -> Path:
    return Path("captures/car_2026_05_21_153000.jpg")
```

### 3. `vehicle_trigger.py`

Purpose:

Detect when a car is close to the Raspberry Pi camera.

Current hardware already suggested by `pass.py`:

```text
TRIG_PIN = 23
ECHO_PIN = 24
DISTANCE_MAX = 15 cm
```

Responsibilities:

- read ultrasonic sensor distance
- return `True` when a car is close enough

Example function:

```python
def wait_for_vehicle() -> float:
    return 42.5
```

### 4. `rfid_reader.py`

Purpose:

Read the RFID card UID.

Current code uses:

```python
from mfrc522 import MFRC522
```

Responsibilities:

- read RFID UID
- normalize it to the same format used by the backend
- return `None` on timeout

Expected UID format:

```text
AA BB CC DD
```

Example function:

```python
def read_rfid(timeout_seconds: int = 10) -> str | None:
    return "AA BB CC DD"
```

### 5. `api_client.py`

Purpose:

Send RFID UID and plate matricule to Flask.

Responsibilities:

- send HTTP POST to `/access/api/entree`
- handle connection errors
- handle timeout errors
- parse JSON response

Example request:

```json
{
  "uid": "AA BB CC DD",
  "matricule": "5678912034",
  "type": "entree"
}
```

Example function:

```python
def verify_access(uid: str, matricule: str) -> dict:
    return {
        "status": "valid",
        "message": "Access allowed"
    }
```

### 6. `gate_controller.py`

Purpose:

Open and close the barrier.

Current `pass.py` uses:

```text
SERVO_PIN = 18
OPEN_DURATION = 3 seconds
```

Responsibilities:

- initialize servo
- open barrier
- wait
- close barrier
- cleanup GPIO on exit

Example function:

```python
def open_barrier() -> None:
    ...
```

### 7. `rpi_entry_system.py`

Purpose:

Main Raspberry Pi entrance system.

This file combines:

- car detection
- camera capture
- OCR
- RFID
- API verification
- barrier control
- LCD messages
- logs

Final loop:

```text
start system
load config
initialize camera
initialize RFID
initialize ultrasonic sensor
initialize barrier
initialize OCR model

loop forever:
    wait until car is close
    capture car image
    extract matricule with AI model
    read RFID card
    send matricule + uid to API
    if API response is valid:
        open barrier
    else:
        deny access
    return to waiting state
```

### 8. `rpi_config.json`

Purpose:

Avoid hardcoding IP addresses, pins, thresholds, and folders.

Example:

```json
{
  "server_url": "http://10.37.152.92:5000/access/api/entree",
  "device_id": "raspberry-pi-entry-01",
  "model_path": "model.onnx",
  "capture_dir": "captures",
  "output_dir": "outputs",
  "distance_max_cm": 50,
  "rfid_timeout_seconds": 10,
  "open_duration_seconds": 3,
  "trig_pin": 23,
  "echo_pin": 24,
  "servo_pin": 18,
  "ocr_mode": "auto"
}
```

## Final Runtime Flow

Detailed flow:

```text
1. Raspberry Pi starts.
2. Camera starts.
3. RFID reader starts.
4. Ultrasonic sensor starts.
5. YOLO + EasyOCR model loads once.
6. LCD displays: Ready / Approchez.
7. Ultrasonic sensor measures distance.
8. If distance is greater than threshold, keep waiting.
9. If distance is lower than threshold, car is detected.
10. Raspberry Pi captures image.
11. Image is saved in captures/.
12. `plate_reader.py` extracts the matricule.
13. RFID reader waits for a card.
14. If no RFID is read, access is denied.
15. If no plate is detected, access is denied.
16. API client sends uid + matricule to Flask.
17. Flask checks MongoDB.
18. If response status is `valid`, barrier opens.
19. If response status is `error`, access is denied.
20. System returns to ready state.
```

## API Contract

The Raspberry Pi should call:

```text
POST http://<PC_IP>:5000/access/api/entree
```

Request:

```json
{
  "uid": "AA BB CC DD",
  "matricule": "5678912034",
  "type": "entree"
}
```

Valid response:

```json
{
  "status": "valid",
  "message": "User Name"
}
```

Invalid response:

```json
{
  "status": "error",
  "message": "Tag non reconnu"
}
```

or:

```json
{
  "status": "error",
  "message": "Matricule non reconnu"
}
```

## Backend Changes Needed

The backend already has the required route:

```text
smart-parking/backend/app/routes/access_entree.py
```

Recommended improvements:

1. Normalize matricule before comparison.
2. Save OCR confidence in `access_logs`.
3. Save captured image filename in `access_logs`.
4. Return more structured response fields.

Suggested improved response:

```json
{
  "status": "valid",
  "authorized": true,
  "rfid_valid": true,
  "plate_valid": true,
  "message": "Access allowed",
  "user": {
    "id": "mongodb-user-id",
    "name": "User Name"
  }
}
```

Suggested access log fields:

```json
{
  "id_tag": "AA BB CC DD",
  "matricule": "5678912034",
  "ocr_confidence": 0.89,
  "image_path": "captures/car_2026_05_21_153000.jpg",
  "statut": "autorise",
  "type": "entree",
  "timestamp": "2026-05-21T15:30:00"
}
```

## Raspberry Pi Dependencies

The Raspberry Pi environment will need both OCR dependencies and hardware dependencies.

OCR dependencies:

```text
ultralytics
easyocr
opencv-python
torch
torchvision
pillow
numpy
onnx
onnxruntime
```

Raspberry Pi hardware dependencies:

```text
picamera2
RPi.GPIO
mfrc522
RPLCD
requests
```

Note:

Some packages are installed through `apt`, not only `pip`, especially `picamera2`.

## Development Mode

Because development is currently happening on Windows, the code should support a test mode.

Example:

```powershell
py -3 rpi_entry_system.py --test-image plaque2.jpeg --test-rfid "AA BB CC DD"
```

In test mode:

- do not use GPIO
- do not use Picamera2
- do not use real RFID
- use a test image
- use a fake RFID UID
- still call the Flask API

This allows testing the full backend/OCR flow before deploying to Raspberry Pi.

## Implementation Steps

### Step 1: Keep `detect_plate.py` as CLI

Do not remove it.

It is useful for manual testing:

```powershell
py -3 detect_plate.py plaque2.jpeg --ocr-only
```

### Step 2: Create `plate_reader.py`

Move reusable model logic from `detect_plate.py` into a class:

```python
class PlateReader:
    def __init__(self, model_path: Path, languages: list[str], gpu: bool = False):
        ...

    def read(self, image_path: Path, ocr_only: bool = False) -> dict:
        ...
```

### Step 3: Update `detect_plate.py`

Make `detect_plate.py` use `PlateReader`.

This avoids duplicated OCR logic.

### Step 4: Create Raspberry Pi Modules

Create:

```text
camera_capture.py
vehicle_trigger.py
rfid_reader.py
gate_controller.py
api_client.py
```

Each file should do one job only.

### Step 5: Create `rpi_entry_system.py`

This is the final main program for Raspberry Pi.

It should import all modules and run the main loop.

### Step 6: Add Config File

Create:

```text
rpi_config.json
```

No IP addresses or GPIO pins should be hardcoded in the main logic.

### Step 7: Update Backend API

Improve:

```text
smart-parking/backend/app/routes/access_entree.py
```

Add:

- matricule normalization
- OCR confidence logging
- image path logging
- structured response fields

### Step 8: Test On Windows

Use:

```powershell
py -3 rpi_entry_system.py --test-image plaque2.jpeg --test-rfid "AA BB CC DD"
```

Expected behavior:

```text
read plate from image
use fake RFID
send both to Flask
print API result
do not use GPIO
```

### Step 9: Test On Raspberry Pi

Use real hardware:

```bash
python3 rpi_entry_system.py
```

Check:

- ultrasonic sensor detects car
- camera captures image
- OCR returns matricule
- RFID reads UID
- API receives both values
- barrier opens only when response is valid

## Main Pseudocode

```python
def main():
    config = load_config("rpi_config.json")

    vehicle_sensor = VehicleTrigger(config)
    camera = CameraCapture(config)
    rfid = RFIDReader(config)
    gate = GateController(config)
    api = ApiClient(config["server_url"])
    plate_reader = PlateReader(config["model_path"])

    while True:
        distance = vehicle_sensor.wait_for_vehicle()

        image_path = camera.capture_image()
        plate_result = plate_reader.read(image_path)
        matricule = plate_result["text"]

        if not matricule:
            display("Plaque illisible")
            continue

        uid = rfid.read(timeout_seconds=config["rfid_timeout_seconds"])

        if not uid:
            display("Badge absent")
            continue

        response = api.verify_access(
            uid=uid,
            matricule=matricule,
            ocr_confidence=plate_result["ocr_confidence"],
            image_path=str(image_path)
        )

        if response.get("status") == "valid":
            gate.open()
        else:
            display("Acces refuse")
```

## Risks And Notes

### OCR Accuracy

The YOLO model is trained mainly for European plates.

For Algerian plates or numeric-only plates:

- cropped images may work better with OCR-only mode
- full car images may need more testing
- plate normalization may be needed before API comparison

Example:

```text
OCR: 56789 120 34
Normalized: 5678912034
```

### Raspberry Pi Performance

EasyOCR and YOLO can be slow on Raspberry Pi CPU.

Possible optimizations:

- load model once at startup
- use smaller image resolution
- crop around expected plate region if camera position is fixed
- run OCR-only if the camera is already focused on the plate area
- consider moving OCR inference to the PC/server if Raspberry Pi is too slow

### Backend Matricule Matching

The database must store matricules in the same normalized format as OCR output.

Recommended normalization:

```python
def normalize_matricule(value):
    return "".join(ch for ch in value.upper() if ch.isalnum())
```

Use the same normalization when:

- creating vehicles
- editing vehicles
- checking API access
- reading OCR output

## Open Questions Before Coding

Before implementation, confirm:

1. Will the camera see the full car or mostly the plate?
2. Are the plates always Algerian numeric plates?
3. Should RFID be scanned before or after the camera captures the plate?
4. Should the barrier open only if both RFID and matricule belong to the same user?
5. Is the Raspberry Pi expected to run the AI model locally, or can it send the photo to the PC/server for OCR?

## Recommended Final Decision

Based on the current files, the best implementation is:

```text
Keep Flask/MongoDB backend in smart-parking.
Keep YOLO/EasyOCR model in european-license-plate-recognition.
Add reusable OCR module: plate_reader.py.
Replace Tesseract code in pass.py with PlateReader.
Send uid + matricule to /access/api/entree.
Keep detect_plate.py for manual testing.
```

