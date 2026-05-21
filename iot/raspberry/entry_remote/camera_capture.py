from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path


class CameraCapture:
    def __init__(
        self,
        capture_dir: Path | str,
        warmup_seconds: float = 2.0,
        resolution: list[int] | tuple[int, int] | None = None,
    ):
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise RuntimeError(
                "Picamera2 is not installed. Install it on Raspberry Pi with apt, "
                "or run rpi_entry_system.py with --test-image on a development PC."
            ) from exc

        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.camera = Picamera2()

        if resolution:
            width, height = int(resolution[0]), int(resolution[1])
            config = self.camera.create_still_configuration(main={"size": (width, height)})
        else:
            config = self.camera.create_still_configuration()

        self.camera.configure(config)
        self.camera.start()
        time.sleep(warmup_seconds)

    def capture_image(self, prefix: str = "car") -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image_path = self.capture_dir / f"{prefix}_{timestamp}.jpg"
        self.camera.capture_file(str(image_path))
        return image_path

    def close(self) -> None:
        self.camera.stop()

