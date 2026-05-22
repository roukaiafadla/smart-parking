from __future__ import annotations


BCM_TO_BOARD = {
    2: 3,
    3: 5,
    4: 7,
    14: 8,
    15: 10,
    17: 11,
    18: 12,
    27: 13,
    22: 15,
    23: 16,
    24: 18,
    10: 19,
    9: 21,
    25: 22,
    11: 23,
    8: 24,
    7: 26,
    0: 27,
    1: 28,
    5: 29,
    6: 31,
    12: 32,
    13: 33,
    19: 35,
    16: 36,
    26: 37,
    20: 38,
    21: 40,
}
BOARD_TO_BCM = {board: bcm for bcm, board in BCM_TO_BOARD.items()}


def gpio_mode_constant(GPIO, gpio_mode: str):
    mode_name = gpio_mode.strip().upper()
    if mode_name == "BOARD":
        return GPIO.BOARD
    if mode_name == "BCM":
        return GPIO.BCM
    raise ValueError("gpio_mode must be 'BOARD' or 'BCM'")


def ensure_gpio_mode(GPIO, gpio_mode: str):
    target_mode = gpio_mode_constant(GPIO, gpio_mode)
    current_mode = GPIO.getmode()
    if current_mode is None:
        GPIO.setmode(target_mode)
    elif current_mode != target_mode:
        raise RuntimeError(
            "GPIO mode conflict. The RFID library usually uses BOARD mode, "
            "so set gpio_mode to BOARD in rpi_config.json."
        )
    return target_mode


def resolve_pin(pin: int, *, configured_numbering: str, runtime_mode: str) -> int:
    configured = configured_numbering.strip().upper()
    runtime = runtime_mode.strip().upper()

    if configured == runtime:
        return pin
    if configured == "BCM" and runtime == "BOARD":
        try:
            return BCM_TO_BOARD[pin]
        except KeyError as exc:
            raise ValueError(f"GPIO{pin} does not map to a 40-pin Raspberry Pi header pin.") from exc
    if configured == "BOARD" and runtime == "BCM":
        try:
            return BOARD_TO_BCM[pin]
        except KeyError as exc:
            raise ValueError(f"Board pin {pin} is not a GPIO pin.") from exc
    raise ValueError("gpio_pin_numbering and gpio_mode must be 'BOARD' or 'BCM'")


def pin_label(pin: int, numbering: str) -> str:
    return f"{numbering.strip().upper()} {pin}"
