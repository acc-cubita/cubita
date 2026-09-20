"""اصناف — تاکسونومیِ ثابتِ «این کسب‌وکار چه می‌فروشد».

**چرا جدا از `industry`.** ستونِ `Tenant.industry` هم «صنف» نامیده می‌شود ولی کارِ
دیگری می‌کند: پنج گزینه‌ی درشت که **قالبِ ماژول‌های پنل** را انتخاب می‌کنند
(`app/services/modules.py`). این‌جا لایه‌ی ریزتری است — «بستنی‌فروشی»، «لوازم یدکی
خودرو» — که با آن دو کسب‌وکار به هم **وصل** می‌شوند: شرکتِ پخش اعلام می‌کند به کدام
اصناف جنس می‌دهد، و فروشگاه در بازار همان‌ها را می‌بیند.

**چرا ثابت در کد و نه جدولِ per-tenant.** این یک برچسبِ محلی نیست، **کلیدِ تطبیق
بینِ دو مستأجر** است. اگر هر کسب‌وکار صنفِ خودش را می‌نوشت، «لوازم یدکی» و «یدکی
فروشی» دو چیزِ متفاوت می‌شدند و هدف‌گیریِ پخش‌کننده بی‌صدا از کار می‌افتاد. همان
دلیلی که `INDUSTRY_TEMPLATES` هم در کد است.

**گروه‌ها رفتار ندارند.** فقط برای سازمان‌دهی‌اند: `<optgroup>` در انتخابگر، و
دکمه‌ی «کلِ این گروه» وقتی پخش‌کننده هدف‌هایش را می‌چیند. به `industry` نگاشت
نمی‌شوند — ثبت‌نام آن را جدا می‌پرسد.

**افزودنِ صنفِ تازه** = یک ردیف این‌جا. کلیدها هرگز عوض نمی‌شوند، چون در
`tenants.trade` و `marketplace_settings.target_trades` ذخیره شده‌اند؛ برچسبِ فارسی
آزاد است.
"""
from typing import NamedTuple


class Trade(NamedTuple):
    """یک صنف. `key` در دیتابیس می‌نشیند، `label` فقط دیده می‌شود."""

    key: str
    label: str


class TradeGroup(NamedTuple):
    key: str
    label: str
    trades: tuple[Trade, ...]


#: حداکثر طولِ کلید — با `String(40)`ِ `tenants.trade` یکی است. تست نگهش می‌دارد.
MAX_TRADE_KEY_LEN = 40


TRADE_GROUPS: tuple[TradeGroup, ...] = (
    TradeGroup(
        "food",
        "خوراکی و آشامیدنی",
        (
            Trade("supermarket", "سوپرمارکت"),
            Trade("hypermarket", "هایپرمارکت"),
            Trade("grocery", "بقالی"),
            Trade("icecream", "بستنی‌فروشی"),
            Trade("confectionery", "قنادی و شیرینی"),
            Trade("bakery", "نانوایی"),
            Trade("dairy", "لبنیاتی"),
            Trade("butcher", "قصابی"),
            Trade("poultry_fish", "مرغ و ماهی"),
            Trade("produce", "میوه و تره‌بار"),
            Trade("nuts", "آجیل و خشکبار"),
            Trade("cafe", "کافه و قهوه"),
            Trade("restaurant", "رستوران"),
            Trade("fastfood", "فست‌فود"),
            Trade("beverages", "نوشیدنی و آبمیوه"),
        ),
    ),
    TradeGroup(
        "apparel",
        "پوشاک و منسوجات",
        (
            Trade("clothing", "پوشاک"),
            Trade("boutique", "بوتیک"),
            Trade("childrens_wear", "پوشاک بچگانه"),
            Trade("underwear", "لباس زیر"),
            Trade("shoes_bags", "کیف و کفش"),
            Trade("fabric", "پارچه‌فروشی"),
            Trade("haberdashery", "خرازی"),
            Trade("workwear", "لباس کار و ایمنی"),
        ),
    ),
    TradeGroup(
        "auto_industrial",
        "فنی، خودرو و صنعتی",
        (
            Trade("autoparts", "لوازم یدکی خودرو"),
            Trade("motorcycle_parts", "لوازم یدکی موتورسیکلت"),
            Trade("tires", "لاستیک و رینگ"),
            Trade("car_accessories", "صوتی و تزئینات خودرو"),
            Trade("oil_filter", "روغن و فیلتر"),
            Trade("tools", "ابزارفروشی"),
            Trade("electrical", "لوازم برقی و الکتریکی"),
            Trade("hardware", "یراق‌آلات"),
            Trade("iron_metal", "آهن‌آلات و فلزات"),
            Trade("paint", "رنگ و رزین"),
            Trade("building_material", "مصالح ساختمانی"),
            Trade("plumbing", "لوازم بهداشتی ساختمان"),
            Trade("hvac", "تأسیسات و تهویه"),
            Trade("industrial_equipment", "تجهیزات صنعتی"),
        ),
    ),
    TradeGroup(
        "digital",
        "دیجیتال و لوازم خانگی",
        (
            Trade("mobile", "موبایل و لوازم جانبی"),
            Trade("computer", "کامپیوتر و قطعات"),
            Trade("home_appliance", "لوازم خانگی"),
            Trade("audio_video", "صوتی و تصویری"),
            Trade("camera", "دوربین و تجهیزات تصویربرداری"),
            Trade("gaming", "بازی و کنسول"),
            Trade("office_equipment", "ماشین‌های اداری"),
        ),
    ),
    TradeGroup(
        "health",
        "بهداشت، سلامت و زیبایی",
        (
            Trade("pharmacy", "داروخانه"),
            Trade("cosmetics", "لوازم آرایشی و بهداشتی"),
            Trade("medical_equipment", "تجهیزات پزشکی"),
            Trade("optician", "عینک‌فروشی"),
            Trade("herbal", "عطاری و گیاهان دارویی"),
            Trade("supplement", "مکمل و تغذیه‌ی ورزشی"),
            Trade("barber", "آرایشگاه و پیرایش"),
            Trade("beauty_salon", "سالن زیبایی"),
        ),
    ),
    TradeGroup(
        "home",
        "خانه و دکوراسیون",
        (
            Trade("furniture", "مبلمان و دکوراسیون"),
            Trade("carpet", "فرش و موکت"),
            Trade("lighting", "لوستر و روشنایی"),
            Trade("curtain", "پرده و تزئینات"),
            Trade("tile", "کاشی و سرامیک"),
            Trade("kitchenware", "ظروف و لوازم آشپزخانه"),
            Trade("bedding", "سرویس خواب"),
            Trade("flowers", "گل و گیاه"),
        ),
    ),
    TradeGroup(
        "culture",
        "فرهنگی، ورزشی و سرگرمی",
        (
            Trade("stationery", "لوازم‌التحریر"),
            Trade("bookstore", "کتاب‌فروشی"),
            Trade("toys", "اسباب‌بازی"),
            Trade("sports", "لوازم ورزشی"),
            Trade("music_instruments", "آلات موسیقی"),
            Trade("handicraft", "صنایع دستی"),
            Trade("pet_shop", "پت‌شاپ و لوازم حیوانات"),
            Trade("gift_shop", "هدایا و کادویی"),
        ),
    ),
    TradeGroup(
        "luxury",
        "طلا، ساعت و لوکس",
        (
            Trade("gold", "طلا و جواهر"),
            Trade("watch", "ساعت"),
            Trade("silver", "نقره‌فروشی"),
            Trade("antique", "آنتیک و کلکسیون"),
        ),
    ),
    TradeGroup(
        "services",
        "خدمات و پیمانکاری",
        (
            Trade("construction", "پیمانکاری ساختمان"),
            Trade("auto_repair", "تعمیرگاه خودرو"),
            Trade("technical_services", "خدمات فنی و تعمیرات"),
            Trade("printing", "چاپ و تبلیغات"),
            Trade("transport", "حمل و نقل"),
            Trade("real_estate", "مشاور املاک"),
            Trade("education", "آموزشگاه"),
            Trade("it_services", "خدمات کامپیوتری و نرم‌افزار"),
            Trade("travel", "آژانس مسافرتی"),
            Trade("laundry", "خشکشویی"),
            Trade("accounting_services", "خدمات حسابداری و مالی"),
            Trade("insurance", "بیمه"),
        ),
    ),
    TradeGroup(
        "agriculture",
        "کشاورزی و دام",
        (
            Trade("farm_inputs", "نهاده‌های کشاورزی"),
            Trade("animal_feed", "خوراک دام و طیور"),
            Trade("greenhouse", "گلخانه و نهال"),
            Trade("veterinary", "دامپزشکی و لوازم"),
        ),
    ),
    TradeGroup(
        "wholesale",
        "پخش و بنکداری",
        (
            Trade("food_distribution", "پخش مواد غذایی"),
            Trade("hygiene_distribution", "پخش بهداشتی و شوینده"),
            Trade("pharma_distribution", "پخش دارو و مکمل"),
            Trade("industrial_distribution", "پخش لوازم صنعتی"),
            Trade("general_wholesale", "بنکداری و عمده‌فروشی"),
        ),
    ),
    #: گروهِ آخر عمدی است: کسی که صنفش در فهرست نیست باید بتواند چیزی انتخاب کند،
    #: وگرنه فیلدِ خالی می‌گذارد و از «هنوز اعلام نکرده» قابلِ تشخیص نمی‌ماند.
    TradeGroup("other", "سایر", (Trade("other", "سایرِ اصناف"),)),
)


#: نگاشتِ کلید → برچسب، یک بار ساخته می‌شود.
TRADE_LABELS: dict[str, str] = {
    t.key: t.label for g in TRADE_GROUPS for t in g.trades
}

#: کلیدِ گروهِ هر صنف — برای «کلِ این گروه» و گزارش.
TRADE_GROUP_OF: dict[str, str] = {
    t.key: g.key for g in TRADE_GROUPS for t in g.trades
}


def is_valid_trade(key: str) -> bool:
    return key in TRADE_LABELS


def trade_label(key: str | None) -> str:
    """برچسبِ فارسی. کلیدِ ناشناخته خودش برمی‌گردد تا داده‌ی قدیمی گم نشود."""
    if not key:
        return ""
    return TRADE_LABELS.get(key, key)


def trades_of_group(group_key: str) -> tuple[str, ...]:
    for g in TRADE_GROUPS:
        if g.key == group_key:
            return tuple(t.key for t in g.trades)
    return ()


def clean_trades(keys: list[str] | None) -> list[str]:
    """فهرستِ اصنافِ ورودی را یکتا و مرتب می‌کند و ناشناخته‌ها را دور می‌ریزد.

    ترتیبِ خروجی همان ترتیبِ `TRADE_GROUPS` است، نه ترتیبِ ورودی — تا دو ذخیره‌ی
    یکسان دو مقدارِ متفاوت در دیتابیس نسازند.
    """
    if not keys:
        return []
    wanted = set(keys)
    return [t.key for g in TRADE_GROUPS for t in g.trades if t.key in wanted]
