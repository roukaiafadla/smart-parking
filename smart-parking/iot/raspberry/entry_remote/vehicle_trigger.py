from __future__ import annotations

import time

from gpio_utils import ensure_gpio_mode, pin_label, resolve_pin


class UltrasonicVehicleTrigger:
    def __init__(
        self,
        trig_pin: int,
        echo_pin: int,
        distance_max_cm: float,
        poll_seconds: float = 0.5,
        echo_timeout_seconds: float = 0.08,
        gpio_mode: str = "BOARD",
        pin_numbering: str = "BCM",
    ):
        try:
            import RPi.GPIO as GPIO
        except ImportError as exc:
            raise RuntimeError(
                "RPi.GPIO is not installed. Run this module on Raspberry Pi, "
                "or use rpi_entry_system.py --test-image on a development PC."
            ) from exc

        self.GPIO = GPIO
        self.gpio_mode = gpio_mode.strip().upper()
        self.pin_numbering = pin_numbering.strip().upper()
        self.configured_trig_pin = trig_pin
        self.configured_echo_pin = echo_pin
        self.trig_pin = resolve_pin(
            trig_pin,
            configured_numbering=self.pin_numbering,
            runtime_mode=self.gpio_mode,
        )
        self.echo_pin = resolve_pin(
            echo_pin,
            configured_numbering=self.pin_numbering,
            runtime_mode=self.gpio_mode,
        )
        self.distance_max_cm = distance_max_cm
        self.poll_seconds = poll_seconds
        self.echo_timeout_seconds = echo_timeout_seconds
        self.last_error = ""

        self.GPIO.setwarnings(False)
        ensure_gpio_mode(self.GPIO, self.gpio_mode)
        self.GPIO.setup(self.trig_pin, self.GPIO.OUT)
        self.GPIO.setup(self.echo_pin, self.GPIO.IN, pull_up_down=self.GPIO.PUD_DOWN)
        self.GPIO.output(self.trig_pin, False)
        time.sleep(0.05)

    def pin_levels(self) -> tuple[int, int]:
        return self.GPIO.input(self.trig_pin), self.GPIO.input(self.echo_pin)

    def measure_distance_cm(self) -> float | None:
        self.last_error = ""
        self.GPIO.output(self.trig_pin, True)
        time.sleep(0.00001)
        self.GPIO.output(self.trig_pin, False)

        wait_start = time.time()
        while self.GPIO.input(self.echo_pin) == 0:
            if time.time() - wait_start > self.echo_timeout_seconds:
                self.last_error = "echo did not go HIGH"
                return None
        pulse_start = time.time()

        while self.GPIO.input(self.echo_pin) == 1:
            if time.time() - pulse_start > self.echo_timeout_seconds:
                self.last_error = "echo stayed HIGH too long"
                return None
        pulse_end = time.time()

        elapsed = pulse_end - pulse_start
        return round((elapsed * 34300) / 2, 1)

    def wait_for_vehicle(self) -> float:
        while True:
            distance = self.measure_distance_cm()
            if distance is not None:
                print(f"[ULTRASONIC] Distance: {distance} cm")
                if distance <= self.distance_max_cm:
                    return distance
            else:
                trig_level, echo_level = self.pin_levels()
                print(
                    "[ULTRASONIC] Distance read timeout "
                    f"({self.last_error}; TRIG {pin_label(self.trig_pin, self.gpio_mode)}={trig_level}, "
                    f"ECHO {pin_label(self.echo_pin, self.gpio_mode)}={echo_level})"
                )
            time.sleep(self.poll_seconds)

    def close(self) -> None:
        pass
