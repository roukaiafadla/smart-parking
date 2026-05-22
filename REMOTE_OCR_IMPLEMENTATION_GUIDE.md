# Remote OCR Entry System Implementation Guide

This guide describes the new optimized architecture for Raspberry Pi 4.

The Raspberry Pi no longer runs the YOLO/EasyOCR model. It only handles the parking hardware:

1. Read the RFID card.
2. Wait for a car with the ultrasonic sensor.
3. Capture a license plate photo with the Pi camera.
4. Send the RFID UID and image to the PC Flask backend.
5. Wait for the backend decision.
6. Open the gate only when the backend returns authorized access.

The PC now handles the heavier work:

1. Receive the RFID UID and uploaded image.
2. Run `PlateReader` using `model.onnx`, YOLO, and EasyOCR.
3. Normalize the detected matricule.
4. Validate RFID + matricule against MongoDB.
5. Save the access log.
6. Return a JSON decision to the Raspberry Pi.

## Updated Runtime Flow

```text
Raspberry Pi
  -> LCD/log: Ready / scan badge
  -> RFIDReader reads UID
  -> LCD/log: badge OK / approach
  -> Ultrasonic sensor detects car
  -> CameraCapture saves image
  -> AccessApiClient uploads uid + image to PC

PC Flask backend
  -> POST /access/api/entree/image
  -> saves uploaded image
  -> loads PlateReader once
  -> detects and reads plate text
  -> checks users + vehicules in MongoDB
  -> writes access_logs
  -> returns authorized or refused response

Raspberry Pi
  -> opens gate if response.status == valid
  -> otherwise refuses access
```

## Files Changed

### Raspberry Pi side

```text
european-license-plate-recognition/
  rpi_entry_system.py
  api_client.py
  rpi_config.json
  requirements-rpi.txt
```

Important changes:

- `rpi_entry_system.py` defaults to remote OCR mode.
- The Pi script no longer imports `plate_reader`, `cv2`, `easyocr`, or `ultralytics` unless local OCR mode is explicitly selected.
- The interactive live flow is now RFID first, then ultrasonic detection, then camera capture, then PC verification.
- `api_client.py` can upload an image with multipart form data.
- `requirements-rpi.txt` now contains only lightweight Pi dependencies.

### PC/backend side

```text
smart-parking/backend/app/config.py
smart-parking/backend/app/routes/access_entree.py
smart-parking/backend/requirements-ocr-pc.txt
```

Important changes:

- New endpoint:

```text
POST /access/api/entree/image
```

- The endpoint accepts:

```text
uid: RFID UID
image: captured plate/car image
device_id: optional Raspberry Pi identifier
distance_cm: optional ultrasonic distance
```

- The backend loads `PlateReader` once and reuses it for later requests.
- Uploaded images and annotated OCR outputs are saved in:

```text
smart-parking/backend/uploads/entry/
smart-parking/backend/uploads/entry_outputs/
```

## Raspberry Pi Config

File:

```text
european-license-plate-recognition/rpi_config.json
```

Key settings:

```json
{
  "server_url": "http://10.37.152.92:5000/access/api/entree",
  "image_server_url": "http://10.37.152.92:5000/access/api/entree/image",
  "processing_mode": "remote",
  "api_timeout_seconds": 120
}
```

Use your PC IP address in `image_server_url`.

## PC Backend Environment

Install the normal backend dependencies, then install OCR dependencies:

```bash
cd ~/model-ocr/smart-parking/backend
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-ocr-pc.txt
```

If your backend virtual environment is on Windows PowerShell:

```powershell
cd C:\Users\aaden\Desktop\model-ocr\smart-parking\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ocr-pc.txt
```

Start the backend on the PC:

```bash
python run.py
```

The backend must be reachable from the Raspberry Pi:

```text
http://<PC_IP>:5000
```

## Raspberry Pi Environment

Install only the lightweight Pi dependencies:

```bash
cd ~/model-ocr/european-license-plate-recognition
source .venv/bin/activate
pip install -r requirements-rpi.txt
sudo apt install -y python3-picamera2
```

Run the interactive entry system:

```bash
python3 rpi_entry_system.py --no-lcd
```

For one test cycle:

```bash
python3 rpi_entry_system.py --no-lcd --once
```

For camera upload without waiting for the ultrasonic sensor:

```bash
python3 rpi_entry_system.py --skip-trigger --no-lcd --once
```

For manual Enter-to-capture testing:

```bash
python3 rpi_entry_system.py --skip-trigger --manual-capture --no-lcd --once
```

## PC Endpoint Test From Raspberry Pi

After the PC backend is running, test upload from the Pi:

```bash
curl -X POST http://10.37.152.92:5000/access/api/entree/image \
  -F "uid=AA BB CC DD" \
  -F "device_id=raspberry-pi-entry-01" \
  -F "image=@captures/YOUR_CAPTURE.jpg"
```

Expected valid response:

```json
{
  "status": "valid",
  "authorized": true,
  "rfid_valid": true,
  "plate_valid": true,
  "matricule": "5678912034",
  "message": "User Name"
}
```

Expected refused response:

```json
{
  "status": "error",
  "authorized": false,
  "message": "Matricule non reconnu"
}
```

## Local PC Test Without Raspberry Pi

From the OCR project folder on the PC:

```bash
python rpi_entry_system.py --remote-ocr --test-image ../plaque2.jpeg --test-rfid "AA BB CC DD"
```

This sends the test image to the Flask backend just like the Raspberry Pi would.

To test old local OCR mode on the PC:

```bash
python rpi_entry_system.py --local-ocr --test-image ../plaque2.jpeg --test-rfid "AA BB CC DD" --no-api
```

## Troubleshooting

### Pi cannot reach PC backend

Check the PC IP address:

```bash
ipconfig
```

or on Linux:

```bash
ip addr
```

Then update `image_server_url` in `rpi_config.json`.

Also allow Flask through the PC firewall for port `5000`.

### First request is slow

The first image upload can be slow because the backend loads YOLO and EasyOCR. Later requests reuse the same loaded reader.

Check that the endpoint is reachable from the Raspberry Pi:

```bash
curl http://192.168.12.208:5000/access/api/entree/image
```

Warm up the OCR model on the PC before running the Pi flow:

```bash
curl http://192.168.12.208:5000/access/api/entree/image/warmup
```

### OCR reads the wrong text

Try OCR-only mode on the PC backend by setting:

```bash
OCR_MODE=ocr_only
```

or improve camera framing so the plate fills more of the image.

### Raspberry Pi still imports heavy OCR packages

Make sure `rpi_config.json` has:

```json
"processing_mode": "remote"
```

Do not install `european-license-plate-recognition/requirements.txt` on the Pi for remote OCR mode. Use `requirements-rpi.txt`.

## Deployment Copy Commands

From WSL on your PC:

```bash
scp /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/rpi_entry_system.py \
    /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/api_client.py \
    /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/rpi_config.json \
    /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/requirements-rpi.txt \
    pi@192.168.12.230:/home/pi/model-ocr/european-license-plate-recognition/
```

If the Raspberry Pi also needs the GPIO fixes from the previous step:

```bash
scp /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/gpio_utils.py \
    /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/gate_controller.py \
    /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/vehicle_trigger.py \
    /mnt/c/Users/aaden/Desktop/model-ocr/european-license-plate-recognition/rfid_reader.py \
    pi@192.168.12.230:/home/pi/model-ocr/european-license-plate-recognition/
```

Copy backend changes to the PC backend folder if you deploy from another machine:

```bash
smart-parking/backend/app/config.py
smart-parking/backend/app/routes/access_entree.py
smart-parking/backend/requirements-ocr-pc.txt
```
