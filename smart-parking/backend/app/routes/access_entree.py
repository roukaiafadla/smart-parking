from datetime import datetime
import sys
import time
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from app import db
from app.normalization import normalize_matricule, normalize_uid


access_entree_bp = Blueprint("access_entree", __name__, url_prefix="/access")
_plate_reader = None


@access_entree_bp.route("/")
@login_required
def index():
    logs = list(db.access_logs.find().sort("timestamp", -1).limit(50))
    return render_template("access.html", logs=logs)


def user_display_name(user: dict | None) -> str:
    if not user:
        return "Inconnu"
    return f"{user.get('prenom', '')} {user.get('nom', '')}".strip() or "Inconnu"


def log_entry_ocr(message: str, *args) -> None:
    if args:
        message = message % args
    current_app.logger.info(message)
    print(message, flush=True)


def get_plate_reader():
    global _plate_reader
    if _plate_reader is not None:
        log_entry_ocr("[ENTRY OCR] Using cached PlateReader")
        return _plate_reader

    ocr_project_dir = Path(current_app.config["OCR_PROJECT_DIR"]).resolve()
    if str(ocr_project_dir) not in sys.path:
        sys.path.insert(0, str(ocr_project_dir))

    from plate_reader import PlateReader

    log_entry_ocr("[ENTRY OCR] Loading PlateReader from %s", ocr_project_dir)
    _plate_reader = PlateReader(
        model_path=current_app.config.get("OCR_MODEL_PATH", "model.onnx"),
        gpu=bool(current_app.config.get("OCR_GPU", False)),
        confidence=float(current_app.config.get("OCR_DETECTOR_CONFIDENCE", 0.5)),
        search_roots=[ocr_project_dir.parent],
    )
    log_entry_ocr("[ENTRY OCR] PlateReader ready")
    return _plate_reader


def save_entry_image(uploaded_file) -> Path:
    upload_dir = Path(current_app.config["OCR_UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_name = secure_filename(uploaded_file.filename or "entry_capture.jpg")
    suffix = Path(original_name).suffix.lower() or ".jpg"
    image_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{suffix}"
    image_path = upload_dir / image_name
    uploaded_file.save(image_path)
    return image_path


def save_annotated_entry_image(source_image: Path, annotated_image, plates: list[dict]) -> Path:
    import cv2
    from plate_reader import default_output_path, draw_annotations

    output_dir = Path(current_app.config["OCR_OUTPUT_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = default_output_path(source_image, output_dir)
    draw_annotations(annotated_image, plates)
    cv2.imwrite(str(output_path), annotated_image)
    return output_path


def find_vehicle_for_user(user_id, matricule: str) -> dict | None:
    vehicle = db.vehicules.find_one({"user_id": user_id, "matricule": matricule})
    if vehicle:
        return vehicle

    for candidate in db.vehicules.find({"user_id": user_id}):
        if normalize_matricule(candidate.get("matricule", "")) == matricule:
            return candidate
    return None


@access_entree_bp.route("/api/entree/image/warmup", methods=["GET"])
def warmup_entry_ocr():
    start_time = time.monotonic()
    try:
        get_plate_reader()
    except Exception as exc:
        current_app.logger.exception("[ENTRY OCR] Warmup failed")
        return jsonify({"status": "error", "message": "OCR warmup failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "ok",
            "message": "OCR model is loaded",
            "elapsed_seconds": round(time.monotonic() - start_time, 1),
        }
    )


def insert_access_log(
    *,
    uid: str,
    matricule: str,
    user: dict | None,
    status: str,
    data: dict,
    rfid_valid: bool,
    plate_valid: bool,
) -> None:
    db.access_logs.insert_one(
        {
            "id_tag": uid,
            "user_id": user.get("_id") if user else None,
            "nom": user_display_name(user),
            "matricule": matricule,
            "ocr_confidence": data.get("ocr_confidence"),
            "detection_confidence": data.get("detection_confidence"),
            "image_path": data.get("image_path"),
            "annotated_image_path": data.get("annotated_image_path"),
            "device_id": data.get("device_id"),
            "distance_cm": data.get("distance_cm"),
            "timestamp": datetime.now(),
            "statut": status,
            "type": data.get("type", "entree"),
            "rfid_valid": rfid_valid,
            "plate_valid": plate_valid,
        }
    )


@access_entree_bp.route("/api/entree", methods=["POST"])
def check_entree():
    data = request.get_json(silent=True) or {}

    uid = normalize_uid(data.get("uid", ""))
    matricule = normalize_matricule(data.get("matricule", ""))

    if not uid:
        return jsonify({"status": "error", "authorized": False, "message": "UID manquant"}), 400
    if not matricule:
        insert_access_log(
            uid=uid,
            matricule="",
            user=None,
            status="refusé",
            data=data,
            rfid_valid=False,
            plate_valid=False,
        )
        return jsonify({"status": "error", "authorized": False, "message": "Matricule manquant"}), 400

    user = db.users.find_one({"id_tag": uid, "etat": "actif"})
    if not user:
        insert_access_log(
            uid=uid,
            matricule=matricule,
            user=None,
            status="refusé",
            data=data,
            rfid_valid=False,
            plate_valid=False,
        )
        return jsonify(
            {
                "status": "error",
                "authorized": False,
                "rfid_valid": False,
                "plate_valid": False,
                "message": "Tag non reconnu",
            }
        )

    vehicle = find_vehicle_for_user(user.get("_id"), matricule)
    if not vehicle:
        insert_access_log(
            uid=uid,
            matricule=matricule,
            user=user,
            status="refusé",
            data=data,
            rfid_valid=True,
            plate_valid=False,
        )
        return jsonify(
            {
                "status": "error",
                "authorized": False,
                "rfid_valid": True,
                "plate_valid": False,
                "message": "Matricule non reconnu",
            }
        )

    insert_access_log(
        uid=uid,
        matricule=matricule,
        user=user,
        status="autorisé",
        data=data,
        rfid_valid=True,
        plate_valid=True,
    )
    nom = user_display_name(user)
    return jsonify(
        {
            "status": "valid",
            "authorized": True,
            "rfid_valid": True,
            "plate_valid": True,
            "message": nom,
            "user": {
                "id": str(user.get("_id")),
                "name": nom,
            },
            "vehicle": {
                "id": str(vehicle.get("_id")),
                "matricule": normalize_matricule(vehicle.get("matricule", "")),
            },
        }
    )


@access_entree_bp.route("/api/entree/image", methods=["GET", "POST"])
def check_entree_image():
    if request.method == "GET":
        return jsonify(
            {
                "status": "ok",
                "message": "Remote OCR endpoint is ready. Use POST multipart/form-data with uid and image.",
                "endpoint": "/access/api/entree/image",
            }
        )

    start_time = time.monotonic()
    log_entry_ocr(
        "[ENTRY OCR] Upload request started from %s content_length=%s",
        request.remote_addr,
        request.content_length,
    )
    data = request.form.to_dict()
    uid = normalize_uid(data.get("uid", ""))
    log_entry_ocr("[ENTRY OCR] Parsed form uid=%s device=%s", uid or "(missing)", data.get("device_id"))

    if not uid:
        return jsonify({"status": "error", "authorized": False, "message": "UID manquant"}), 400

    uploaded_file = request.files.get("image") or request.files.get("photo") or request.files.get("file")
    if not uploaded_file:
        return jsonify({"status": "error", "authorized": False, "message": "Image manquante"}), 400

    image_path = save_entry_image(uploaded_file)
    image_size = image_path.stat().st_size if image_path.exists() else 0
    log_entry_ocr("[ENTRY OCR] Saved image %s (%s bytes)", image_path, image_size)
    data["image_path"] = str(image_path)
    data["type"] = data.get("type", "entree")

    try:
        reader = get_plate_reader()
        log_entry_ocr("[ENTRY OCR] Running plate recognition")
        plate_payload, annotated_image = reader.read(
            image_path,
            ocr_only=current_app.config.get("OCR_MODE", "auto") == "ocr_only",
            fallback_ocr=bool(current_app.config.get("OCR_FALLBACK", True)),
        )
        output_path = save_annotated_entry_image(image_path, annotated_image, plate_payload["plates"])
        log_entry_ocr(
            "[ENTRY OCR] OCR complete matricule=%s confidence=%s elapsed=%.1fs",
            plate_payload.get("matricule") or "(none)",
            plate_payload.get("ocr_confidence"),
            time.monotonic() - start_time,
        )
    except Exception as exc:
        current_app.logger.exception("PC OCR failed for %s", image_path)
        insert_access_log(
            uid=uid,
            matricule="",
            user=None,
            status="refusé",
            data=data,
            rfid_valid=False,
            plate_valid=False,
        )
        return jsonify(
            {
                "status": "error",
                "authorized": False,
                "message": "Erreur OCR sur le PC",
                "detail": str(exc),
                "image_path": str(image_path),
            }
        ), 500

    matricule = normalize_matricule(plate_payload.get("matricule", ""))
    data.update(
        {
            "matricule": matricule,
            "ocr_confidence": plate_payload.get("ocr_confidence"),
            "detection_confidence": plate_payload.get("detection_confidence"),
            "annotated_image_path": str(output_path),
        }
    )
    user = db.users.find_one({"id_tag": uid, "etat": "actif"})
    rfid_valid = bool(user)
    log_entry_ocr(
        "[ENTRY OCR] DB check uid_valid=%s matricule=%s",
        rfid_valid,
        matricule or "(none)",
    )
    ocr_payload = {
        "matricule": matricule,
        "text": plate_payload.get("text", ""),
        "ocr_confidence": plate_payload.get("ocr_confidence"),
        "detection_confidence": plate_payload.get("detection_confidence"),
        "image_path": str(image_path),
        "annotated_image_path": str(output_path),
    }

    if not matricule:
        log_entry_ocr("[ENTRY OCR] Refused: plate unreadable elapsed=%.1fs", time.monotonic() - start_time)
        insert_access_log(
            uid=uid,
            matricule="",
            user=user,
            status="refusé",
            data=data,
            rfid_valid=rfid_valid,
            plate_valid=False,
        )
        return jsonify(
            {
                "status": "error",
                "authorized": False,
                "rfid_valid": rfid_valid,
                "plate_valid": False,
                "message": "Plaque illisible",
                "matricule": "",
                "ocr": ocr_payload,
            }
        )

    if not user:
        log_entry_ocr("[ENTRY OCR] Refused: unknown tag uid=%s elapsed=%.1fs", uid, time.monotonic() - start_time)
        insert_access_log(
            uid=uid,
            matricule=matricule,
            user=None,
            status="refusé",
            data=data,
            rfid_valid=False,
            plate_valid=True,
        )
        return jsonify(
            {
                "status": "error",
                "authorized": False,
                "rfid_valid": False,
                "plate_valid": True,
                "message": "Tag non reconnu",
                "matricule": matricule,
                "ocr": ocr_payload,
            }
        )

    vehicle = find_vehicle_for_user(user.get("_id"), matricule)
    if not vehicle:
        log_entry_ocr(
            "[ENTRY OCR] Refused: matricule %s not linked to uid=%s elapsed=%.1fs",
            matricule,
            uid,
            time.monotonic() - start_time,
        )
        insert_access_log(
            uid=uid,
            matricule=matricule,
            user=user,
            status="refusé",
            data=data,
            rfid_valid=True,
            plate_valid=False,
        )
        return jsonify(
            {
                "status": "error",
                "authorized": False,
                "rfid_valid": True,
                "plate_valid": False,
                "message": "Matricule non reconnu",
                "matricule": matricule,
                "ocr": ocr_payload,
            }
        )

    insert_access_log(
        uid=uid,
        matricule=matricule,
        user=user,
        status="autorisé",
        data=data,
        rfid_valid=True,
        plate_valid=True,
    )
    nom = user_display_name(user)
    log_entry_ocr(
        "[ENTRY OCR] Authorized uid=%s matricule=%s user=%s elapsed=%.1fs",
        uid,
        matricule,
        nom,
        time.monotonic() - start_time,
    )
    return jsonify(
        {
            "status": "valid",
            "authorized": True,
            "rfid_valid": True,
            "plate_valid": True,
            "message": nom,
            "matricule": matricule,
            "ocr": ocr_payload,
            "user": {
                "id": str(user.get("_id")),
                "name": nom,
            },
            "vehicle": {
                "id": str(vehicle.get("_id")),
                "matricule": normalize_matricule(vehicle.get("matricule", "")),
            },
        }
    )
