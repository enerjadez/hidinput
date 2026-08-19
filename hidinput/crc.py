"""DualSense Bluetooth CRC32.

Sony prefixes HID output with seed 0xA2 (Bluetooth HID output header) before
the report. Linux hid-playstation and DualSense Explorer both use ITU CRC-32.
"""

from __future__ import annotations

_POLY = 0xEDB88320
_TABLE = []


def _table() -> list[int]:
    if _TABLE:
        return _TABLE
    for n in range(256):
        c = n
        for _ in range(8):
            c = (_POLY ^ (c >> 1)) if (c & 1) else (c >> 1)
        _TABLE.append(c & 0xFFFFFFFF)
    return _TABLE


def crc32(data: bytes | bytearray | memoryview) -> int:
    tbl = _table()
    crc = 0xFFFFFFFF
    for b in data:
        crc = tbl[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


def bt_output_crc(report: bytes | bytearray) -> int:
    """CRC of 0xA2 + report without the last 4 checksum bytes."""
    return crc32(b"\xa2" + bytes(report[:-4]))


def stamp_bt_output(report: bytearray) -> None:
    crc = bt_output_crc(report)
    report[-4] = crc & 0xFF
    report[-3] = (crc >> 8) & 0xFF
    report[-2] = (crc >> 16) & 0xFF
    report[-1] = (crc >> 24) & 0xFF
