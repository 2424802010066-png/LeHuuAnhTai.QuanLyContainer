"""Bảo mật: băm mật khẩu bằng bcrypt, sinh token phiên, giới hạn số lần đăng nhập sai."""
import hashlib
import hmac
import secrets
import threading
import time

import bcrypt

from .config import settings

BCRYPT_ROUNDS = 12  # 2^12 vòng lặp ~ 0,2 s/lần băm: đủ chậm để chống dò mật khẩu hàng loạt


def hash_password(password: str) -> str:
    """bcrypt tự sinh salt ngẫu nhiên và nhúng vào chuỗi kết quả: $2b$12$<salt 22 ký tự><hash 31 ký tự>."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    data = password.encode("utf-8")
    if len(data) > 72:
        return False
    try:
        return bcrypt.checkpw(data, password_hash.encode("ascii"))
    except ValueError:
        return False


# Băm sẵn 1 chuỗi giả: khi username không tồn tại vẫn chạy checkpw để thời gian phản hồi như nhau
# (kẻ tấn công không đoán được username nào có thật dựa vào thời gian trả lời).
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def verify_dummy(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bit ngẫu nhiên an toàn mật mã


def token_digest(token: str) -> str:
    """CSDL chỉ lưu HMAC-SHA256(SECRET_KEY, token): lộ bảng sessions cũng không dùng lại được cookie."""
    return hmac.new(settings.secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


class LoginLimiter:
    """Tối đa `limit` lần đăng nhập SAI trong `window` giây cho mỗi (IP, username).

    Đây là lớp phòng thủ thứ 2 trong tiến trình; lớp thứ nhất là limit_req của Nginx.
    """

    def __init__(self, limit: int = 5, window: int = 300):
        self.limit, self.window = limit, window
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        return [t for t in self._fails.get(key, []) if now - t < self.window]

    def blocked(self, key: str) -> int:
        """Trả về số giây còn phải chờ (0 = được thử)."""
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)
            self._fails[key] = recent
            if len(recent) >= self.limit:
                return int(self.window - (now - recent[0])) + 1
        return 0

    def fail(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._fails[key] = self._recent(key, now) + [now]

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


login_limiter = LoginLimiter()
