"""Windows DPAPI helpers for installation-bound local secret protection."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .errors import StateError

CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DataBlob(ctypes.Structure):
    """Windows DATA_BLOB structure."""

    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob(data: bytes) -> tuple[DataBlob, ctypes.Array[ctypes.c_char]]:
    """Create a DATA_BLOB while retaining its backing buffer."""
    buffer = ctypes.create_string_buffer(data)
    blob = DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    return blob, buffer


def protect_for_current_user(data: bytes) -> bytes:
    """Encrypt bytes with Windows DPAPI for the current user profile."""
    if os.name != "nt":
        raise StateError("DPAPI is available only on Windows")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, input_buffer = _blob(data)
    output_blob = DataBlob()
    success = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "AnajERP",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not success:
        raise StateError(f"DPAPI protection failed: {ctypes.get_last_error()}")
    del input_buffer
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def unprotect_for_current_user(data: bytes) -> bytes:
    """Decrypt bytes previously protected for the current Windows user."""
    if os.name != "nt":
        raise StateError("DPAPI is available only on Windows")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, input_buffer = _blob(data)
    output_blob = DataBlob()
    success = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not success:
        raise StateError(f"DPAPI unprotection failed: {ctypes.get_last_error()}")
    del input_buffer
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
