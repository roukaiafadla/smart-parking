from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from plate_reader import (
    DEFAULT_LANGUAGES,
    ROOT,
    PlateReader,
    default_output_path,
    draw_annotations,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect license plates with the local YOLO ONNX model and read them with EasyOCR."
    )
    parser.add_argument("image", type=Path, help="Path to a car image.")
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "model.onnx",
        help="Path to the license-plate detector model.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Where to save the annotated image. Defaults to outputs/<image>_plates.jpg.",
    )
    parser.add_argument("--conf", type=float, default=0.5, help="YOLO detection confidence threshold.")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for EasyOCR if CUDA is available.")
    parser.add_argument(
        "--langs",
        nargs="+",
        default=DEFAULT_LANGUAGES,
        help="EasyOCR languages to load.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    parser.add_argument("--no-save", action="store_true", help="Do not save an annotated image.")
    parser.add_argument(
        "--ocr-only",
        action="store_true",
        help="Skip YOLO detection and OCR the whole image. Useful when the image is already a plate crop.",
    )
    parser.add_argument(
        "--fallback-ocr",
        action="store_true",
        help="If no plate is detected, OCR the whole image as a fallback.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output if args.output else default_output_path(args.image)

    reader = PlateReader(
        model_path=args.model,
        languages=args.langs,
        gpu=args.gpu,
        confidence=args.conf,
    )
    payload, annotated_image = reader.read(
        args.image,
        ocr_only=args.ocr_only,
        fallback_ocr=args.fallback_ocr,
        confidence=args.conf,
    )

    if not args.no_save:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        draw_annotations(annotated_image, payload["plates"])
        cv2.imwrite(str(output_path), annotated_image)
        payload["annotated_image"] = str(output_path)
    else:
        payload["annotated_image"] = None

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    if payload["plates"]:
        print("Detected plates:")
        for plate in payload["plates"]:
            text = plate["text"] or "(text not read)"
            det = plate["detection_confidence"]
            det_label = f"{det:.2f}" if det is not None else "n/a"
            print(
                f"- {text} | detector={det_label} | ocr={plate['ocr_confidence']:.2f} | box={plate['box']}"
            )
    else:
        print("No license plate detected.")

    if not args.no_save:
        print(f"Annotated image saved to: {output_path}")


if __name__ == "__main__":
    main()
