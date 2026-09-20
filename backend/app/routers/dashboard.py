"""کارت‌های داشبوردِ کاربر — باکسِ «شروعِ کارِ تازه» را خودِ کاربر می‌چیند.

سطحِ کاربر × کسب‌وکار (روی `Membership`): هرکس چیدمانِ خودش را دارد و همان چیدمان
روی نسخه‌ی ویندوز، مرورگر و هر دستگاهِ دیگری می‌آید — چون روی حساب می‌نشیند نه روی
مرورگر. (کلیدهای میان‌بر عمداً برعکس‌اند: آن‌ها به خودِ *صفحه‌کلیدِ* دستگاه گره خورده‌اند.)

خواندن جداگانه اندپوینت ندارد؛ `GET /api/auth/me` همین فهرست را با خودش می‌آورد، پس
داشبورد در همان رفت‌وبرگشتِ اولِ ورود کارت‌هایش را دارد و منتظرِ درخواستِ دوم نمی‌ماند.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal
from app.schemas.dashboard import MAX_CARD_ID, DashboardCardsIn, DashboardCardsOut

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

#: `page` یا `page/section` — همان شکلی که فرانت می‌سازد. گاردِ شکل است نه معنا:
#: جلوی آشغال و متنِ بلند را می‌گیرد، ولی درباره‌ی *وجودِ* صفحه حرفی نمی‌زند.
CARD_ID = re.compile(r"^[a-z][a-z0-9-]*(/[a-z][a-z0-9-]*)?$")


@router.put("/cards", response_model=DashboardCardsOut)
def set_cards(
    data: DashboardCardsIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """چیدمانِ تازه را ذخیره می‌کند. فهرستِ خالی یعنی «باکس را خالی بگذار».

    تکراری‌ها با حفظِ ترتیبِ اولین‌بار حذف می‌شوند: دو کارتِ یکسان در یک باکس فقط
    جای دیگری را می‌گیرد.
    """
    seen: set[str] = set()
    cards: list[str] = []
    for raw in data.cards:
        card = raw.strip()
        if not card or card in seen:
            continue
        if len(card) > MAX_CARD_ID or not CARD_ID.match(card):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه‌ی کارت معتبر نیست")
        seen.add(card)
        cards.append(card)

    principal.membership.dashboard_cards = cards
    db.flush()
    return DashboardCardsOut(cards=cards)


@router.delete("/cards", response_model=DashboardCardsOut)
def reset_cards(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """بازگشت به پیش‌فرض — ستون دوباره `NULL` می‌شود، نه `[]`.

    بدونِ این، «بازگرداندن به پیش‌فرض» باید فهرستِ پیش‌فرض را از فرانت بفرستد و
    ذخیره کند؛ آن‌وقت کاربر برای همیشه یک *کپیِ منجمد* از پیش‌فرضِ امروز می‌گرفت و
    کارتِ تازه‌ای که فردا به پیش‌فرض‌ها اضافه شود هرگز به او نمی‌رسید.
    """
    principal.membership.dashboard_cards = None
    db.flush()
    return DashboardCardsOut(cards=None)
