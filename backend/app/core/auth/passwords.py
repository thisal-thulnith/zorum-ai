"""Password hashing — argon2id via pwdlib. The plaintext password never leaves this module."""

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()  # argon2id with safe defaults


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    return _hasher.verify(plain, password_hash)
