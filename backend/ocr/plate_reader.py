from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import cv2
import easyocr
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
DEFAULT_LANGUAGES = ["en", "de", "fr", "es", "it", "nl"]
MIN_PLATE_ROW_SCORE = 0.35


def normalize_plate_text(text: str) -> str:
    text = text.upper().replace(" ", "")
    return re.sub(r"[^A-Z0-9-]", "", text)


def normalize_matricule(text: str) -> str:
    return "".join(character for character in text.upper() if character.isalnum())


def resolve_image_path(image_path: Path, search_roots: list[Path] | None = None) -> Path:
    search_roots = search_roots or []
    candidates = [
        image_path,
        Path.cwd() / image_path,
        ROOT / image_path,
        ROOT.parent / image_path,
        ROOT / "examples" / image_path,
    ]
    candidates.extend(root / image_path for root in search_roots)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    checked_paths = "\n".join(f"  - {candidate}" for candidate in candidates)
    raise FileNotFoundError(f"Image not found: {image_path}\nChecked:\n{checked_paths}")


def expanded_box(
    box: list[int],
    width: int,
    height: int,
    margin_x_ratio: float = 0.06,
    margin_y_ratio: float = 0.06,
) -> list[int]:
    x1, y1, x2, y2 = box
    margin_x = int((x2 - x1) * margin_x_ratio)
    margin_y = int((y2 - y1) * margin_y_ratio)
    return [
        max(0, x1 - margin_x),
        max(0, y1 - margin_y),
        min(width, x2 + margin_x),
        min(height, y2 + margin_y),
    ]


def row_score(text: str, confidence: float) -> float:
    alnum = re.sub(r"[^A-Z0-9]", "", text)
    letters = sum(character.isalpha() for character in alnum)
    digits = sum(character.isdigit() for character in alnum)
    score = confidence + min(len(alnum), 10) * 0.03

    if letters and not digits:
        score -= 1.0
    elif digits and not letters:
        score += 0.1 if len(alnum) >= 5 else -0.5
    if len(alnum) < 4:
        score -= 0.5
    if len(alnum) > 12:
        score -= (len(alnum) - 12) * 0.12

    return score


def group_words_into_rows(words: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda item: item["center_y"]):
        tolerance = max(14.0, word["height"] * 0.8)
        for row in rows:
            row_center = sum(item["center_y"] for item in row) / len(row)
            if abs(row_center - word["center_y"]) <= tolerance:
                row.append(word)
                break
        else:
            rows.append([word])

    for row in rows:
        row.sort(key=lambda item: item["center_x"])
    return rows


def choose_plate_row(words: list[dict]) -> tuple[str, float, list[int] | None]:
    best_candidate = ("", 0.0, None)
    best_score = float("-inf")

    for row in group_words_into_rows(words):
        text = "".join(word["text"] for word in row)
        confidence = sum(word["confidence"] for word in row) / len(row)
        score = row_score(text, confidence)
        if score > best_score:
            x1 = min(word["box"][0] for word in row)
            y1 = min(word["box"][1] for word in row)
            x2 = max(word["box"][2] for word in row)
            y2 = max(word["box"][3] for word in row)
            best_candidate = (text, confidence, [x1, y1, x2, y2])
            best_score = score

    if best_score < MIN_PLATE_ROW_SCORE:
        return "", 0.0, None

    return best_candidate


def read_plate_text(reader: easyocr.Reader, plate_rgb) -> tuple[str, float, list[dict], list[int] | None]:
    ocr_results = reader.readtext(plate_rgb, detail=1, paragraph=False)
    words = []

    for bbox, raw_text, confidence in ocr_results:
        cleaned_text = normalize_plate_text(raw_text)
        if not cleaned_text or confidence < 0.05:
            continue

        xs = [float(point[0]) for point in bbox]
        ys = [float(point[1]) for point in bbox]
        word_box = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
        words.append(
            {
                "text": cleaned_text,
                "raw_text": raw_text,
                "confidence": float(confidence),
                "center_x": float(sum(xs) / len(xs)),
                "center_y": float(sum(ys) / len(ys)),
                "height": float(max(ys) - min(ys)),
                "box": word_box,
            }
        )

    if not words:
        return "", 0.0, [], None

    plate_text, ocr_confidence, text_box = choose_plate_row(words)
    return plate_text, ocr_confidence, words, text_box


def box_iou(first: list[int], second: list[int]) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def dedupe_plates(plates: list[dict]) -> list[dict]:
    def sort_key(plate: dict) -> float:
        detector_confidence = plate["detection_confidence"] or 0.0
        return detector_confidence * 0.6 + plate["ocr_confidence"] * 0.4

    unique_plates = []
    for plate in sorted(plates, key=sort_key, reverse=True):
        duplicate = False
        for existing in unique_plates:
            same_text = plate["text"] and plate["text"] == existing["text"]
            same_area = box_iou(plate["box"], existing["box"]) > 0.5
            if same_text or same_area:
                duplicate = True
                break
        if not duplicate:
            unique_plates.append(plate)

    return unique_plates


def draw_annotations(image_bgr, plates: list[dict]) -> None:
    for plate in plates:
        x1, y1, x2, y2 = plate["box"]
        label = plate["text"] or "license_plate"
        if plate["detection_confidence"] is not None:
            label = f"{label} {plate['detection_confidence']:.2f}"

        cv2.rectangle(image_bgr, (x1, y1), (x2, y2), (0, 180, 0), 2)
        label_y = max(22, y1 - 8)
        cv2.putText(
            image_bgr,
            label,
            (x1, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 180, 0),
            2,
            cv2.LINE_AA,
        )


def default_output_path(image_path: Path, output_dir: Path | None = None) -> Path:
    output_dir = output_dir or ROOT / "outputs"
    return output_dir / f"{image_path.stem}_plates.jpg"


class PlateReader:
    def __init__(
        self,
        model_path: Path | str = ROOT / "model.onnx",
        languages: list[str] | None = None,
        gpu: bool = False,
        confidence: float = 0.5,
        search_roots: list[Path] | None = None,
    ):
        self.model_path = Path(model_path)
        if not self.model_path.is_absolute():
            self.model_path = ROOT / self.model_path
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        self.languages = languages or DEFAULT_LANGUAGES
        self.gpu = gpu
        self.confidence = confidence
        self.search_roots = search_roots or []
        self.detector = YOLO(str(self.model_path), task="detect")
        self.reader = easyocr.Reader(self.languages, gpu=self.gpu, verbose=False)

    def read(
        self,
        image_path: Path | str,
        ocr_only: bool = False,
        fallback_ocr: bool = False,
        confidence: float | None = None,
    ) -> tuple[dict, Any]:
        resolved_path = resolve_image_path(Path(image_path), self.search_roots)

        if ocr_only:
            plates, annotated_image = self.ocr_whole_image(resolved_path)
        else:
            plates, annotated_image = self.detect_plates(
                resolved_path,
                confidence=self.confidence if confidence is None else confidence,
            )
            if not plates and fallback_ocr:
                plates, annotated_image = self.ocr_whole_image(resolved_path)

        best_plate = plates[0] if plates else None
        payload = {
            "image": str(resolved_path),
            "plates": plates,
            "best_plate": best_plate,
            "text": best_plate["text"] if best_plate else "",
            "matricule": normalize_matricule(best_plate["text"]) if best_plate else "",
            "ocr_confidence": best_plate["ocr_confidence"] if best_plate else 0.0,
            "detection_confidence": best_plate["detection_confidence"] if best_plate else None,
        }
        return payload, annotated_image

    def detect_plates(self, image_path: Path, confidence: float) -> tuple[list[dict], Any]:
        image_bgr = cv2.imread(str(image_path))
        if image_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        height, width = image_rgb.shape[:2]
        results = self.detector(image_rgb, conf=confidence, verbose=False)

        plates = []
        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                x1, y1, x2, y2 = expanded_box(xyxy, width, height)
                plate_crop = image_rgb[y1:y2, x1:x2]
                if plate_crop.size == 0 or (x2 - x1) < 20 or (y2 - y1) < 8:
                    continue

                text, ocr_confidence, ocr_words, text_box = read_plate_text(self.reader, plate_crop)
                detector_area_ratio = ((x2 - x1) * (y2 - y1)) / (width * height)
                if not text and detector_area_ratio > 0.25:
                    continue

                if text_box:
                    crop_width = x2 - x1
                    crop_height = y2 - y1
                    refined_crop_box = expanded_box(
                        text_box,
                        crop_width,
                        crop_height,
                        margin_x_ratio=0.18,
                        margin_y_ratio=0.7,
                    )
                    refined_box = [
                        x1 + refined_crop_box[0],
                        y1 + refined_crop_box[1],
                        x1 + refined_crop_box[2],
                        y1 + refined_crop_box[3],
                    ]
                else:
                    refined_box = [x1, y1, x2, y2]

                plates.append(
                    {
                        "text": text,
                        "matricule": normalize_matricule(text),
                        "detection_confidence": float(box.conf[0].cpu().item())
                        if box.conf is not None
                        else None,
                        "ocr_confidence": ocr_confidence,
                        "box": refined_box,
                        "detector_box": [x1, y1, x2, y2],
                        "ocr_words": ocr_words,
                    }
                )

        return dedupe_plates(plates), image_bgr

    def ocr_whole_image(self, image_path: Path) -> tuple[list[dict], Any]:
        image_bgr = cv2.imread(str(image_path))
        if image_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        height, width = image_rgb.shape[:2]
        text, ocr_confidence, ocr_words, text_box = read_plate_text(self.reader, image_rgb)

        if not text:
            return [], image_bgr

        return [
            {
                "text": text,
                "matricule": normalize_matricule(text),
                "detection_confidence": None,
                "ocr_confidence": ocr_confidence,
                "box": text_box if text_box else [0, 0, width, height],
                "detector_box": None,
                "ocr_words": ocr_words,
            }
        ], image_bgr

