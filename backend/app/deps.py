"""Phụ thuộc dùng chung cho các API: lấy người dùng hiện tại từ cookie phiên, kiểm tra CSRF."""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import User, UserSession
from .security import same, token_digest

COOKIE_NAME = "qlc_sid"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    sess = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_digest(token),
            UserSession.expires_at > datetime.now(timezone.utc),
        )
    )
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phiên đăng nhập đã hết hạn")
    return sess


def current_user(sess: UserSession = Depends(current_session)) -> User:
    return sess.user


def require_csrf(request: Request, sess: UserSession = Depends(current_session)) -> User:
    """Mọi request làm thay đổi dữ liệu (POST/PUT/DELETE) phải gửi header X-CSRF-Token khớp với phiên.

    Trang web lạ có thể khiến trình duyệt gửi kèm cookie, nhưng không đọc được token này
    (Same-Origin Policy) nên không giả mạo được request -> chống CSRF. Cookie còn đặt SameSite=Strict.
    """
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not same(sent, sess.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Thiếu hoặc sai CSRF token")
    return sess.user
