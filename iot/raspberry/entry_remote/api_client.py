from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests


class AccessApiClient:
    def __init__(
        self,
        server_url: str,
        timeout_seconds: float = 5.0,
        image_server_url: str | None = None,
        connect_timeout_seconds: float = 10.0,
    ):
        self.server_url = server_url
        self.timeout_seconds = timeout_seconds
        self.image_server_url = image_server_url or self._default_image_server_url(server_url)
        self.connect_timeout_seconds = connect_timeout_seconds

    @staticmethod
    def _default_image_server_url(server_url: str) -> str:
        trimmed_url = server_url.rstrip("/")
        if trimmed_url.endswith("/api/entree"):
            return f"{trimmed_url}/image"
        return trimmed_url

    def verify_access(
        self,
        uid: str,
        matricule: str,
        ocr_confidence: float | None = None,
        detection_confidence: float | None = None,
        image_path: str | Path | None = None,
        device_id: str | None = None,
        distance_cm: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "uid": uid,
            "matricule": matricule,
            "type": "entree",
        }

        if ocr_confidence is not None:
            payload["ocr_confidence"] = ocr_confidence
        if detection_confidence is not None:
            payload["detection_confidence"] = detection_confidence
        if image_path is not None:
            payload["image_path"] = str(image_path)
        if device_id:
            payload["device_id"] = device_id
        if distance_cm is not None:
            payload["distance_cm"] = distance_cm

        try:
            response = requests.post(
                self.server_url,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Flask server unreachable"}
        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Flask server timeout"}
        except requests.exceptions.JSONDecodeError:
            return {
                "status": "error",
                "message": "Invalid JSON response from Flask server",
                "http_status": response.status_code,
                "raw_response": response.text,
            }
        except requests.exceptions.HTTPError as exc:
            message = str(exc)
            try:
                body = response.json()
                message = body.get("message", message)
            except requests.exceptions.JSONDecodeError:
                body = {"raw_response": response.text}
            return {
                "status": "error",
                "message": message,
                "http_status": response.status_code,
                "response": body,
            }
        except requests.exceptions.RequestException as exc:
            return {"status": "error", "message": str(exc)}

    def verify_access_image(
        self,
        uid: str,
        image_path: str | Path,
        device_id: str | None = None,
        distance_cm: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "uid": uid,
            "type": "entree",
        }
        if device_id:
            payload["device_id"] = device_id
        if distance_cm is not None:
            payload["distance_cm"] = str(distance_cm)

        try:
            image_path = Path(image_path)
            image_size = image_path.stat().st_size
            logging.info(
                "[API] Uploading image %s (%s bytes) to %s",
                image_path,
                image_size,
                self.image_server_url,
            )
            with image_path.open("rb") as image_file:
                files = {
                    "image": (
                        image_path.name,
                        image_file,
                        "image/jpeg",
                    )
                }
                response = requests.post(
                    self.image_server_url,
                    data=payload,
                    files=files,
                    timeout=(self.connect_timeout_seconds, self.timeout_seconds),
                )
            logging.info("[API] PC OCR response HTTP %s", response.status_code)
            response.raise_for_status()
            return response.json()
        except FileNotFoundError:
            return {"status": "error", "message": f"Image not found: {image_path}"}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Flask OCR server unreachable"}
        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Flask OCR server timeout"}
        except requests.exceptions.JSONDecodeError:
            return {
                "status": "error",
                "message": "Invalid JSON response from Flask OCR server",
                "http_status": response.status_code,
                "raw_response": response.text,
            }
        except requests.exceptions.HTTPError as exc:
            message = str(exc)
            try:
                body = response.json()
                message = body.get("message", message)
            except requests.exceptions.JSONDecodeError:
                body = {"raw_response": response.text}
            return {
                "status": "error",
                "message": message,
                "http_status": response.status_code,
                "response": body,
            }
        except requests.exceptions.RequestException as exc:
            return {"status": "error", "message": str(exc)}
