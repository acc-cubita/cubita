"""فهرستِ اصناف — تنها منبعِ این داده برای همه‌ی کلاینت‌ها.

**چرا endpoint و نه فهرستی در فرانت.** پنج صنفِ درشتِ `INDUSTRY_TEMPLATES` امروز
در `SignupScreen.tsx` دستی تکرار شده‌اند، با یک کامنت که می‌گوید «کلیدها با سرور
یکی‌اند». برای پنج ردیف قابلِ تحمل است؛ برای ~۹۰ ردیف نه — دو فهرست دیر یا زود از
هم دور می‌شوند و کلیدی که فقط یک طرف می‌شناسد، هدف‌گیریِ پخش‌کننده را بی‌صدا
می‌شکند. پس فهرست یک جا می‌ماند و کلاینت می‌گیردش.

**عمداً بدونِ احراز هویت.** صفحه‌ی ثبت‌نام باید صنف را بپرسد و آن‌جا هنوز توکنی
نیست. داده‌ای هم نیست که پنهان بماند: یک فهرستِ ثابت است، نه چیزی از یک کسب‌وکار.
"""
from fastapi import APIRouter

from app.schemas.trades import TradeGroupOut, TradeOut
from app.services.trades import TRADE_GROUPS

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("", response_model=list[TradeGroupOut])
def list_trades():
    """اصناف، گروه‌بندی‌شده و به ترتیبِ نمایش."""
    return [
        TradeGroupOut(
            key=g.key,
            label=g.label,
            trades=[TradeOut(key=t.key, label=t.label) for t in g.trades],
        )
        for g in TRADE_GROUPS
    ]
