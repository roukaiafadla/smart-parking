# License Plate Recognition Model Explanation

This project detects and reads vehicle license plates from images. It uses two main computer vision steps:

1. Detect the license plate location in the image.
2. Read the text inside the detected plate area with OCR.

The project also supports an OCR-only mode for images that are already cropped to the plate.

## Project Files

Important files:

- `model.onnx`: The trained license plate detection model.
- `detect_plate.py`: The script used to run detection and OCR.
- `requirements.txt`: Python libraries needed to run the project.
- `config.json`: Detection model configuration and performance information.
- `ocr_config.json`: OCR configuration and supported languages.
- `examples/`: Example car images.
- `outputs/`: Annotated result images created by the script.

## Model Overview

The detection model is a YOLO-based object detection model exported to ONNX format.

Model details from `config.json`:

- Model type: `YOLOv12n`
- Task: `license_plate_detection`
- Input size: `640 x 640`
- Number of classes: `1`
- Class name: `license_plate`
- Framework: `Ultralytics YOLOv12`
- Model file: `model.onnx`

The model does not directly read the text. It only predicts where the license plate is located by returning a bounding box.

After the plate is detected, the script crops that part of the image and sends it to EasyOCR to read the plate number.

## How The Pipeline Works

### 1. Load The Image

OpenCV reads the image from disk:

```python
image_bgr = cv2.imread(str(image_path))
image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
```

OpenCV loads images in BGR format, but most computer vision models expect RGB, so the script converts the image before detection.

### 2. Detect The Plate

The ONNX model is loaded with Ultralytics:

```python
detector = YOLO(str(model_path), task="detect")
results = detector(image_rgb, conf=confidence, verbose=False)
```

The model returns one or more bounding boxes. Each box contains:

- `x1`: left coordinate
- `y1`: top coordinate
- `x2`: right coordinate
- `y2`: bottom coordinate
- confidence score

### 3. Crop The Plate

For each detected box, the script crops the plate area:

```python
plate_crop = image_rgb[y1:y2, x1:x2]
```

This is important because OCR works better when it only sees the plate, not the whole car or background.

### 4. Read Text With OCR

EasyOCR reads text from the cropped plate image:

```python
ocr_results = reader.readtext(plate_rgb, detail=1, paragraph=False)
```

The script cleans the result by keeping only plate-like characters:

- uppercase letters
- digits
- hyphens

It also scores OCR rows so that plate-like text is preferred over signs, badges, and other background text.

### 5. Save Annotated Output

The script draws a rectangle around the detected plate and writes the result to:

```text
outputs/<image_name>_plates.jpg
```

## Running The Model

Install dependencies:

```powershell
py -3 -m pip install -r requirements.txt
```

Run on a full car image:

```powershell
py -3 detect_plate.py path\to\car.jpg
```

Run on a cropped plate image:

```powershell
py -3 detect_plate.py path\to\plate.jpg --ocr-only
```

Print JSON output:

```powershell
py -3 detect_plate.py path\to\car.jpg --json
```

Try a lower detector confidence if the plate is not found:

```powershell
py -3 detect_plate.py path\to\car.jpg --conf 0.2
```

Use detection first, then OCR the whole image if detection fails:

```powershell
py -3 detect_plate.py path\to\car.jpg --fallback-ocr
```

## Libraries Used

### Ultralytics

Package:

```text
ultralytics
```

Purpose:

- Loads the YOLO object detection model.
- Runs inference on the input image.
- Returns bounding boxes for detected license plates.

In this project, Ultralytics is used to load `model.onnx`:

```python
YOLO(str(model_path), task="detect")
```

### EasyOCR

Package:

```text
easyocr
```

Purpose:

- Reads text from the detected plate crop.
- Supports multiple languages.
- Works on CPU or GPU.

Configured languages:

- English: `en`
- German: `de`
- French: `fr`
- Spanish: `es`
- Italian: `it`
- Dutch: `nl`

In this project, EasyOCR is used after YOLO finds the plate.

### OpenCV

Package:

```text
opencv-python
```

Purpose:

- Reads images from disk.
- Converts image color format.
- Crops detected plate regions.
- Draws rectangles and labels on output images.
- Saves annotated images.

Common functions used:

```python
cv2.imread()
cv2.cvtColor()
cv2.rectangle()
cv2.putText()
cv2.imwrite()
```

### ONNX

Package:

```text
onnx
```

Purpose:

- Provides support for the Open Neural Network Exchange model format.
- Allows the trained YOLO model to be stored in a portable format.

The detection model is saved as:

```text
model.onnx
```

### ONNX Runtime

Package:

```text
onnxruntime
```

Purpose:

- Runs ONNX models efficiently.
- Allows inference without needing the original training framework.

In this project, Ultralytics uses ONNX Runtime internally to run `model.onnx`.

### PyTorch

Packages:

```text
torch
torchvision
```

Purpose:

- Required by EasyOCR and some computer vision components.
- Provides tensor operations and deep learning utilities.
- `torchvision` provides vision-related helpers and model utilities.

The current OCR configuration uses CPU mode:

```text
gpu_enabled: false
device_name: CPU
```

### Pillow

Package:

```text
pillow
```

Purpose:

- Image loading and manipulation support.
- Often used by OCR and computer vision tools.

The current script mainly uses OpenCV, but Pillow is included because it is commonly required by OCR/image libraries.

### NumPy

Package:

```text
numpy
```

Purpose:

- Represents images as arrays.
- Handles bounding box coordinates.
- Supports image crop and model output processing.

OpenCV images are NumPy arrays.

### Matplotlib

Package:

```text
matplotlib
```

Purpose:

- Useful for displaying images and visual debugging.
- Not required for the main `detect_plate.py` flow, but useful during experiments.

### Hugging Face Hub

Package:

```text
huggingface-hub
```

Purpose:

- Can download model files from Hugging Face.
- Useful if the model is not already stored locally.

This project already includes `model.onnx`, so the local script uses the file directly.

## Detection Mode vs OCR-Only Mode

### Detection Mode

Use detection mode when the image contains a full car or a street scene:

```powershell
py -3 detect_plate.py car.jpg
```

This mode:

1. Finds the license plate with YOLO.
2. Crops the plate region.
3. Reads text with EasyOCR.
4. Saves an annotated image.

### OCR-Only Mode

Use OCR-only mode when the image is already cropped to the plate:

```powershell
py -3 detect_plate.py plate.jpg --ocr-only
```

This mode:

1. Skips YOLO detection.
2. Sends the whole image directly to EasyOCR.
3. Reads numeric or alphanumeric plate text.

This is useful for close-up plate images such as `plaque2.jpeg`.

## Output Format

Normal output example:

```text
Detected plates:
- 5678912034 | detector=n/a | ocr=0.89 | box=[9, 122, 495, 209]
Annotated image saved to: outputs\plaque2_plates.jpg
```

JSON output example:

```json
{
  "image": "plaque2.jpeg",
  "plates": [
    {
      "text": "5678912034",
      "detection_confidence": null,
      "ocr_confidence": 0.89,
      "box": [9, 122, 495, 209]
    }
  ],
  "annotated_image": "outputs/plaque2_plates.jpg"
}
```

## Limitations

- The detector was trained mainly for European license plates.
- Non-European plates may work better with `--ocr-only` if the image is already cropped.
- OCR can confuse similar characters, such as:
  - `0` and `O`
  - `1` and `I`
  - `5` and `S`
  - `8` and `B`
- Bad lighting, blur, shadows, reflections, and low resolution reduce accuracy.
- The detector may miss plates if they are too small, rotated, cropped, or from a very different format.

## Tips For Better Results

- Use a clear, high-resolution image.
- Make sure the plate is visible and not blurred.
- For full car images, use normal detection mode.
- For close-up plate images, use `--ocr-only`.
- If detection fails, try a lower confidence:

```powershell
py -3 detect_plate.py car.jpg --conf 0.2
```

- If the image is numeric-only, OCR-only mode may work better:

```powershell
py -3 detect_plate.py plate.jpg --ocr-only
```

