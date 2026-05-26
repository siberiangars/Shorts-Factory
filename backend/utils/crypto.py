from cryptography.fernet import Fernet, InvalidToken

from config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.fernet_key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string, return base64-urlsafe ciphertext string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string produced by :func:`encrypt`.

    Raises :class:`cryptography.fernet.InvalidToken` if the key or data is wrong.
    """
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt: invalid token or wrong FERNET_KEY")
