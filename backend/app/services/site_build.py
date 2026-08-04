"""ساختِ بسته‌ی سایتِ فروشگاه (ZIP) برای دانلود و آپلود روی هاستِ مستأجر.

قالبِ استاتیک (`storefront/`) را می‌خواند، `assets/config.js` را با apiBase/slug/key
مخصوصِ همین کسب‌وکار جایگزین می‌کند، یک فایلِ آموزشِ اتصال اضافه می‌کند، و ZIP می‌سازد.
هیچ بیلدی لازم نیست — خروجی مستقیماً روی هر هاستی قابلِ آپلود است.
"""
import io
import json
import zipfile
from pathlib import Path

from app.config import get_settings

# فایل‌هایی از قالب که در بسته‌ی مستأجر نمی‌آیند (سندِ داخلیِ توسعه / جایگزین‌شونده).
_SKIP = {"README.md", "assets/config.js"}

_TUTORIAL = """راهنمای راه‌اندازیِ فروشگاه — کوبیتا
=======================================

این بسته سایتِ فروشگاهِ شماست. برای زنده‌کردنِ آن:

۱) فایل‌های داخلِ این بسته را (index.html و پوشه‌ی assets) از حالتِ فشرده خارج کنید.

۲) همه را در پوشه‌ی اصلیِ هاستِ خود آپلود کنید (معمولاً public_html یا www).
   ساختار باید همین‌طور بماند:  index.html  و  assets/…

۳) در برنامه‌ی حسابداری → «اتصال فروشگاه» → «فروشگاهِ کوبیتا»:
   - در کادرِ «دامنه‌ی هاستِ فروشگاه (originِ مجاز)» آدرسِ سایتِ خود را وارد و ذخیره کنید
     (مثلاً https://shop.example.ir). بدونِ این، مرورگر اجازه‌ی اتصال به سرور را نمی‌دهد.
   - دکمه‌ی «انتشار» را بزنید.

۴) درگاهِ پرداختِ خود (زرین‌پال/زیبال/آی‌دی‌پی) را در همان صفحه وارد کنید تا پرداختِ
   خریداران به حسابِ شما بنشیند.

نکته‌ها:
- کالاها، قیمت و موجودی همه از برنامه‌ی حسابداری خوانده می‌شوند؛ تغییرشان همان‌جا کافی است.
- اگر کلیدِ اتصال را در پنل «کلیدِ تازه» زدید، این بسته را دوباره بسازید و آپلود کنید.
- سفارش‌های سایت در برنامه، بخشِ «سفارش‌ها» می‌آیند؛ با «تأیید پرداخت» به فاکتور تبدیل می‌شوند.

شناسه‌ی این فروشگاه: {slug}
"""


def _template_dir() -> Path:
    configured = get_settings().storefront_template_dir
    if configured:
        return Path(configured)
    # backend/app/services/site_build.py → parents: [0]=services [1]=app [2]=backend [3]=ریشه‌ی مخزن
    return Path(__file__).resolve().parents[3] / "storefront"


def _config_js(api_base: str, slug: str, key: str) -> str:
    return (
        "/* تولیدشده توسط کوبیتا — apiBase/slug/key این فروشگاه. */\n"
        "window.SHOP = {\n"
        f"  apiBase: {json.dumps(api_base)},\n"
        f"  slug: {json.dumps(slug)},\n"
        f"  key: {json.dumps(key)},\n"
        "}\n"
    )


def build_site_bundle(*, api_base: str, slug: str, key: str) -> bytes:
    tpl = _template_dir()
    if not tpl.exists():
        raise FileNotFoundError(f"قالبِ فروشگاه یافت نشد: {tpl}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(tpl.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(tpl).as_posix()
            if rel in _SKIP:
                continue
            z.writestr(rel, path.read_bytes())
        z.writestr("assets/config.js", _config_js(api_base, slug, key))
        z.writestr("آموزش-اتصال.txt", _TUTORIAL.format(slug=slug))
    return buf.getvalue()
