from __future__ import annotations

import time

from gpio_utils import ensure_gpio_mode, pin_label, resolve_pin


class GateController:
    def __init__(
        self,
        servo_pin: int,
        open_duration_seconds: float = 3.0,
        open_duty_cycle: float = 7.5,
        closed_duty_cycle: float = 2.5,
        gpio_mode: str = "BOARD",
        pin_numbering: str = "BCM",
    ):
        try:
            import RPi.GPIO as GPIO
        except ImportError as exc:
            raise RuntimeError(
                "RPi.GPIO is not installed. Run gate control on Raspberry Pi hardware."
            ) from exc

        self.GPIO = GPIO
        self.gpio_mode = gpio_mode.strip().upper()
        self.pin_numbering = pin_numbering.strip().upper()
        self.configured_servo_pin = servo_pin
        self.servo_pin = resolve_pin(
            servo_pin,
            configured_numbering=self.pin_numbering,
            runtime_mode=self.gpio_mode,
        )
        self.open_duration_seconds = open_duration_seconds
        self.open_duty_cycle = open_duty_cycle
        self.closed_duty_cycle = closed_duty_cycle

        self.GPIO.setwarnings(False)
        ensure_gpio_mode(self.GPIO, self.gpio_mode)
        self.GPIO.setup(self.servo_pin, self.GPIO.OUT)
        self.servo = self.GPIO.PWM(self.servo_pin, 50)
        self.servo.start(0)

    def open(self) -> None:
        self.servo.ChangeDutyCycle(self.open_duty_cycle)
        time.sleep(self.open_duration_seconds)
        self.servo.ChangeDutyCycle(self.closed_duty_cycle)
        time.sleep(0.5)
        self.servo.ChangeDutyCycle(0)

    def close(self) -> None:
        self.servo.stop()

    def __repr__(self) -> str:
        return (
            "GateController("
            f"servo={pin_label(self.configured_servo_pin, self.pin_numbering)}"
            f" -> {pin_label(self.servo_pin, self.gpio_mode)})"
        )
