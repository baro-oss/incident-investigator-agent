"""A2: Secret management at-rest — Fernet symmetric encryption.

Key từ env SECRET_KEY (base64-urlsafe 32 bytes → Fernet key).
Nếu SECRET_KEY không set → pass-through (no encryption, warn once).
Ciphertext được prefix "enc:" để phân biệt với plaintext cũ.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_WARNED_NO_KEY = False
_PREFIX = "enc:"


def _get_fernet():
    """Lấy Fernet instance từ SECRET_KEY env. None nếu không có key."""
    global _WARNED_NO_KEY
    raw_key = os.environ.get("SECRET_KEY", "")
    if not raw_key:
        if not _WARNED_NO_KEY:
            logger.warning(
                "SECRET_KEY không được set — llm_config / auth_config lưu dạng plaintext. "
                "Set SECRET_KEY để mã hóa at-rest."
            )
            _WARNED_NO_KEY = True
        return None

    from cryptography.fernet import Fernet

    # Derive 32-byte Fernet key từ SECRET_KEY (bất kỳ độ dài nào)
    derived = hashlib.sha256(raw_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_secret(plaintext: Optional[str]) -> Optional[str]:
    """Mã hóa chuỗi. Trả None nếu input None. Prefix "enc:" để nhận dạng."""
    if plaintext is None:
        return None
    if is_encrypted(plaintext):
        return plaintext  # đã mã hóa rồi — idempotent
    f = _get_fernet()
    if f is None:
        return plaintext  # pass-through khi không có key
    ciphertext = f.encrypt(plaintext.encode()).decode()
    return _PREFIX + ciphertext


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    """Giải mã chuỗi. Nếu không có prefix "enc:" → trả nguyên (backward compat plaintext)."""
    if value is None:
        return None
    if not is_encrypted(value):
        return value  # plaintext cũ — pass-through
    f = _get_fernet()
    if f is None:
        # Key bị bỏ nhưng giá trị đã mã hóa → trả None, log warning
        logger.error("Không thể giải mã secret: SECRET_KEY không set nhưng giá trị đã mã hóa.")
        return None
    try:
        ciphertext = value[len(_PREFIX):]
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.error("Giải mã thất bại: %s", e)
        return None


def is_encrypted(value: str) -> bool:
    """Kiểm tra chuỗi có prefix "enc:" không."""
    return value.startswith(_PREFIX)
