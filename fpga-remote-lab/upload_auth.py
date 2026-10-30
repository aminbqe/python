"""Password verification for temporary bitstream-upload access."""
import hashlib
import hmac
import secrets

ROUNDS = 210_000


def hash_password(password):
    if not password or len(password) > 128:
        raise ValueError('Password must contain 1 to 128 characters')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ROUNDS)
    return f'pbkdf2_sha256${ROUNDS}${salt.hex()}${digest.hex()}'


def verify_password(password, encoded):
    if not password or len(password) > 128:
        return False
    try:
        scheme, rounds, salt, expected = encoded.split('$')
        rounds = int(rounds)
        salt, expected = bytes.fromhex(salt), bytes.fromhex(expected)
        if scheme != 'pbkdf2_sha256' or not 100_000 <= rounds <= 1_000_000:
            return False
        if not 16 <= len(salt) <= 64 or len(expected) != 32:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False
