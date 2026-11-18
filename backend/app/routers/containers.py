"""API container: thêm - xem (tìm kiếm, lọc, phân trang) - sửa - xóa. Tất cả đều yêu cầu đăng nhập."""
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require_csrf
from ..models import TRANG_THAI, Container, User
from ..schemas import ContainerIn, ContainerOut, ContainerPage, LoaiT, ThongKe, TrangThaiT

router = APIRouter(tags=["Container"])


def _like(text: str) -> str:
    """Thoát ký tự đại diện của LIKE (%, _) để người dùng gõ '%' không thành 'khớp mọi thứ'."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _get_or_404(db: Session, cid: int) -> Container:
    c = db.get(Container, cid)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy container")
    return c


@router.get("", response_model=ContainerPage)
def list_containers(
    q: str | None = Query(None, max_length=50, description="Tìm theo số container, chủ hàng, vị trí"),
    trang_thai: TrangThaiT | None = None,
    loai: LoaiT | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
):
    stmt = select(Container)
    if q and q.strip():
        pat = _like(q.strip())
        stmt = stmt.where(or_(Container.so_container.ilike(pat, escape="\\"),
                              Container.chu_hang.ilike(pat, escape="\\"),
                              Container.vi_tri_bai.ilike(pat, escape="\\")))
    if trang_thai:
        stmt = stmt.where(Container.trang_thai == trang_thai)
    if loai:
        stmt = stmt.where(Container.loai == loai)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Container.updated_at.desc(), Container.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).unique().all()
    return ContainerPage(items=[ContainerOut.model_validate(c) for c in rows], total=total, page=page,
                         page_size=page_size, pages=max(1, math.ceil(total / page_size)))


@router.get("/thong-ke", response_model=ThongKe)
def thong_ke(db: Session = Depends(get_db), _user: User = Depends(current_user)):
    dem = dict(db.execute(select(Container.trang_thai, func.count()).group_by(Container.trang_thai)).all())
    theo = {k: int(dem.get(k, 0)) for k in TRANG_THAI}
    return ThongKe(tong=sum(theo.values()), theo_trang_thai=theo)


@router.get("/{cid}", response_model=ContainerOut)
def get_container(cid: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return ContainerOut.model_validate(_get_or_404(db, cid))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ContainerOut)
def create_container(data: ContainerIn, db: Session = Depends(get_db), user: User = Depends(require_csrf)):
    c = Container(**data.model_dump(), created_by=user.id, updated_by=user.id)
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Số container {data.so_container} đã có trong hệ thống")
    db.refresh(c)
    return ContainerOut.model_validate(c)


@router.put("/{cid}", response_model=ContainerOut)
def update_container(cid: int, data: ContainerIn, db: Session = Depends(get_db),
                     user: User = Depends(require_csrf)):
    c = _get_or_404(db, cid)
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    c.updated_by = user.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Số container {data.so_container} đã có trong hệ thống")
    db.refresh(c)
    return ContainerOut.model_validate(c)


@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_container(cid: int, db: Session = Depends(get_db), _user: User = Depends(require_csrf)):
    db.delete(_get_or_404(db, cid))
    db.commit()
