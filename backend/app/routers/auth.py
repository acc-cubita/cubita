from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal
from app.models.tenant import Membership
from app.models.user import User
from app.schemas.auth import LoginIn, MeOut, TokenOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if user is None or not user.active or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور نادرست است")

    # توکن به یک مستأجر مشخص گره می‌خورد. کاربری که عضو چند کسب‌وکار است فعلاً به
    # اولین عضویتش وارد می‌شود؛ سوییچر مستأجر جداگانه اضافه می‌شود.
    membership = (
        db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active").first()
    )
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "عضویت فعالی در هیچ کسب‌وکاری ندارید")

    return TokenOut(access_token=create_access_token(user.id, membership.tenant_id))


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal)):
    return MeOut(
        id=principal.user.id,
        name=principal.user.name,
        email=principal.user.email,
        role_key=principal.role.key,
        role_name=principal.role.name,
        permissions=principal.role.permissions,
    )
