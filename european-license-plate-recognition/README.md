---
license: mit
datasets:
- 0xnu/european-licence-plate
tags:
- eu
- european-union
- transport
- transportation
- computer-vision
- object-detection
- license-plate-recognition
- ocr
language:
- en
- de
- fr
- es
- it
- nl
---

## EULPR: European License Plate Recognition

EULPR is a computer-vision model architecture purpose-built for detecting, reading, and recognizing European license plates. It is optimized for speed and accuracy across diverse EU plate formats.

### Model Performance

- **Detection Rate**: 100.0%
- **Text Extraction Rate**: 100.0%
- **Processing Speed**: 7.6 FPS
- **Model Size**: YOLOv12 Nano (~10.5MB)

### Supported Languages

- English (en)
- German (de)
- French (fr)
- Spanish (es)
- Italian (it)
- Dutch (nl)

### Quick Start

#### Installation

```python
pip install ultralytics easyocr opencv-python pillow torch torchvision huggingface_hub
```

#### Usage

```python
import cv2
import numpy as np
from ultralytics import YOLO
import easyocr
from PIL import Image
from huggingface_hub import hf_hub_download
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# Download models from HuggingFace
print("Downloading model from HuggingFace...")
model_path = hf_hub_download(repo_id="0xnu/european-license-plate-recognition", filename="model.onnx")
config_path = hf_hub_download(repo_id="0xnu/european-license-plate-recognition", filename="config.json")

# Load models with explicit task specification
yolo_model = YOLO(model_path, task='detect')
ocr_reader = easyocr.Reader(['en', 'de', 'fr', 'es', 'it', 'nl'], gpu=False, verbose=False)

# Process image
def recognize_license_plate(image_path):
   # Load image
   image = cv2.imread(image_path)
   image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
   
   # Detect license plates
   results = yolo_model(image_rgb, conf=0.5, verbose=False)
   
   plates = []
   for result in results:
       boxes = result.boxes
       if boxes is not None:
           for box in boxes:
               # Get coordinates
               x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
               
               # Crop plate
               plate_crop = image_rgb[int(y1):int(y2), int(x1):int(x2)]
               
               # Extract text
               ocr_results = ocr_reader.readtext(plate_crop)
               if ocr_results:
                   text = ocr_results[0][1]
                   confidence = float(ocr_results[0][2])  # Convert to native Python float
                   plates.append({'text': text, 'confidence': confidence})
   
   return plates

# Usage Example
results = recognize_license_plate('sample_car_with_license.jpeg')
print(results)
```

### Model Architecture

#### Detection Model (YOLOv12n)
- **Architecture**: YOLOv12 Nano
- **Parameters**: ~3M
- **Input Size**: 640x640 pixels
- **Output**: Bounding boxes for license plates

#### OCR Model (EasyOCR)
- **Engine**: Deep learning-based OCR
- **Languages**: Multi-European language support
- **Character Set**: Alphanumeric + common symbols

### Training Details

- **Dataset**: European License Plate Dataset ([0xnu/european-licence-plate](https://huggingface.co/datasets/0xnu/european-licence-plate))
- **Training Epochs**: 30
- **Batch Size**: 16
- **Image Size**: 640x640
- **Optimizer**: AdamW
- **Framework**: Ultralytics YOLOv12

### Use Cases

- Traffic monitoring systems
- Automated parking management
- Law enforcement applications
- Toll collection systems
- Vehicle access control

### Limitations

- Optimized for European license plate formats
- Performance may vary with extreme weather conditions
- Requires good image quality for optimal text recognition
- Real-time performance depends on hardware capabilities

### License

This project is licensed under the [Modified MIT License](./LICENSE).

### Citation

If you use this model in your research or product, please cite:

```bibtex
@misc{eulpr2025,
  title={EULPR: European License Plate Recognition},
  author={Finbarrs Oketunji},
  year={2025},
  publisher={Hugging Face},
  howpublished={\url{https://huggingface.co/0xnu/european-license-plate-recognition}}
}
```

### Copyright

Copyright (C) 2025 Finbarrs Oketunji. All Rights Reserved.