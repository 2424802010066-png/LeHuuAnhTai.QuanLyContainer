"""API tài khoản: đăng ký, đăng nhập, đăng xuất, thông tin phiên."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import COOKIE_NAME, current_session, require_csrf
from ..models import User, UserSession
from ..schemas import LoginIn, RegisterIn, SessionOut, UserOut
from ..security import hash_password, login_limiter, new_token, token_digest, verify_dummy, verify_password

router = APIRouter(tags=["Tài khoản"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Tên đăng nhập đã có người dùng")
    user = User(username=data.username, full_name=data.full_name, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # 2 người đăng ký cùng tên một lúc -> ràng buộc UNIQUE của CSDL chặn
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tên đăng nhập đã có người dùng")
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=SessionOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    key = f"{ip}|{data.username}"
    wait = login_limiter.blocked(key)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Đăng nhập sai quá nhiều lần, thử lại sau {wait} giây",
                            headers={"Retry-After": str(wait)})
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None:
        verify_dummy(data.password)
        ok = False
    else:
        ok = verify_password(data.password, user.password_hash)
    if not ok or user is None:
        login_limiter.fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai tên đăng nhập hoặc mật khẩu")
    login_limiter.reset(key)

    now = datetime.now(timezone.utc)
    db.execute(delete(UserSession).where(UserSession.expires_at < now))  # dọn phiên hết hạn
    token, csrf = new_token(), new_token()
    db.add(UserSession(token_hash=token_digest(token), csrf_token=csrf, user_id=user.id,
                       expires_at=now + timedelta(hours=settings.session_hours)))
    db.commit()
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=settings.session_hours * 3600,
        httponly=True,                   # JavaScript không đọc được cookie -> XSS không lấy cắp được phiên
        secure=settings.cookie_secure,   # true khi chạy HTTPS
        samesite="strict",               # trình duyệt không gửi cookie khi request xuất phát từ trang khác
        path="/",
    )
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, sess: UserSession = Depends(current_session),
           _user: User = Depends(require_csrf), db: Session = Depends(get_db)):
    db.delete(sess)  # xóa phiên phía máy chủ: cookie cũ (nếu bị lộ) cũng vô hiệu ngay
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=settings.cookie_secure, samesite="strict")


@router.get("/me", response_model=SessionOut)
def me(sess: UserSession = Depends(current_session)):
    return SessionOut(user=UserOut.model_validate(sess.user), csrf_token=sess.csrf_token)
