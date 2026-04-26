"""
Cryptography utilities: HMAC signing, optional AES encryption, hash functions.
"""

import logging
import hmac
import hashlib
import os
import base64
from typing import Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


def generate_hmac_signature(
    data: bytes,
    key: bytes,
) -> str:
    """
    Generate HMAC-SHA256 signature for data.

    Args:
        data: Bytes to sign
        key: Secret key bytes

    Returns:
        Hex-encoded signature
    """
    signature = hmac.new(key, data, hashlib.sha256)
    return signature.hexdigest()


def verify_hmac_signature(
    data: bytes,
    signature: str,
    key: bytes,
) -> bool:
    """
    Verify HMAC-SHA256 signature.

    Returns:
        True if signature valid
    """
    expected = generate_hmac_signature(data, key)
    return hmac.compare_digest(expected, signature)


def generate_fernet_key(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = 100000,
) -> Tuple[bytes, bytes]:
    """
    Derive a Fernet encryption key from a password.

    Args:
        password: User-provided password
        salt: Random salt (generate if None)
        iterations: PBKDF2 iterations

    Returns:
        (key, salt) tuple
    """
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


class EncryptedFileStorage:
    """
    Simple AES-256 encryption wrapper for sensitive files (e.g., audit logs).
    Uses Fernet (AES-128 in CBC mode with PKCS7 padding) for simplicity.
    """

    def __init__(self, key: bytes):
        """
        Args:
            key: 32-byte Fernet key (URL-safe base64)
        """
        self.fernet = Fernet(key)

    def encrypt_file(self, input_path: str, output_path: str):
        """Encrypt a file."""
        with open(input_path, "rb") as f:
            data = f.read()
        encrypted = self.fernet.encrypt(data)
        with open(output_path, "wb") as f:
            f.write(encrypted)

    def decrypt_file(self, input_path: str, output_path: str):
        """Decrypt a file."""
        with open(input_path, "rb") as f:
            data = f.read()
        decrypted = self.fernet.decrypt(data)
        with open(output_path, "wb") as f:
            f.write(decrypted)


def sha256_file(file_path: str, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha.update(chunk)
    return sha.hexdigest()


def sha256_string(text: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_secure_token(length: int = 32) -> bytes:
    """Generate cryptographically secure random token."""
    return os.urandom(length)
