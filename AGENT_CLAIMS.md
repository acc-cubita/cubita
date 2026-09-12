# تخته‌ی ادعا — کدام ایجنت روی چه کار می‌کند

**این فایل قفل نیست، قرارداد است.** چند ایجنت (Claude Code، Codex، …) روی *یک*
درختِ کاری می‌نویسند. هیچ merge‌ای محافظت نمی‌کند: دو نفر که یک فایل را ویرایش
کنند، آخرین نویسنده کلِ کارِ دیگری را **بی‌صدا** می‌برد.

پس قاعده ساده است: **قبل از نوشتن روی یک فایل، این‌جا ادعایش کن؛ بعد از تمام‌شدن،
ادعا را پس بگیر.**

---

## چطور کار کن

**۱) اولِ هر جلسه:** این فایل را بخوان، و بعد `git status` بگیر.
اگر فایلی تغییر کرده که تو نزده‌ای و این‌جا هم ادعا نشده، **از کاربر بپرس** —
یعنی یک ایجنتِ دیگر بدونِ ثبت کار می‌کند.

**۲) پیش از اولین ویرایش:** ردیفت را به جدولِ «ادعاهای فعال» اضافه کن و **همان
لحظه** فایل را ذخیره کن (قبل از اینکه سراغِ کدِ اصلی بروی).

**۳) پیش از نوشتن روی هر فایل:** دوباره بخوانش. ممکن است از آخرین باری که دیدی
عوض شده باشد.

**۴) وقتی تمام شد:** ردیفت را حذف کن و یک خط به «تاریخچه» اضافه کن.

**۵) اگر فایلی که می‌خواهی ادعا شده:** ننویس رویش. یا کارِ دیگری بردار، یا از
کاربر بخواه هماهنگ کند. **ادعای دیگری را پاک نکن.**

---

## ادعاهای فعال

<!-- ردیف: | ایجنت | فایل‌ها/مسیرها | چه کاری | از کِی | -->

| ایجنت | فایل‌ها | کار | از |
|---|---|---|---|
| Claude (hesabdari-93) | مهاجرت `0122`، `services/pricing.py`، `routers/advanced_inventory.py`، `routers/sales_ops.py`، `schemas/advanced_inventory.py`، `schemas/sales_ops.py`، `models/advanced_inventory.py`، `models/invoices.py`، `audit.py`، `salesInvoiceDraft.ts`، `PosPage.tsx`، `PriceListsPanel.tsx`، `SalesOpsPages.tsx`، `api.ts`؛ و `pytest` | فصلِ «اعلامیه قیمت»: ماتریسِ قیمت قابلِ ورود شود، یک موتورِ قیمت به‌جای سه، بستنِ مسیری که ماتریس را پاک می‌کند، تغییرِ گروهیِ فی با یکتاسازی | ۱۴۰۵/۰۶/۲۱ |

> **دو هشدار برای هر که بعد از من می‌آید:**
>
> ۱. شاخه‌ی محلیِ **`feat/sales-invoice-completion`** شش کامیتِ **push‌نشده** دارد
>    (`WarehouseIssue`، حساب‌های نوع فروش، Snapshotهای فاکتور خرید، پیش‌فاکتورِ
>    منبع). هیچ‌کدام روی `master` نیست، **۱۸ کامیت عقب** است، و شماره‌های
>    `0114`/`0115`/`0116`اش با `master` **تصادم** دارند (آن‌جا
>    `counterparty_settlement`/`cheque_traceability`/`warehouse_master` نشسته‌اند).
>    من دست بهش نزدم و checkout را به شاخه‌ی خودم بردم — آن شش کامیت با ref خودِ
>    شاخه امن‌اند. هر که خواست فرودش بیاورد: اول rebase روی master، بعد
>    شماره‌گذاریِ دوباره به `0122` به بعد.
> ۲. به همین دلیل §۳۰–§۳۴ (برگشت خروج انبار) و §۵۲/§۵۳ (حذفِ COGS از سندِ تجاری)
>    در این فصل **ساخته نشدند** — زیرساختشان همان شاخه است.

---

## فایل‌های پرتصادم — این‌ها را حتماً ادعا کن

این‌ها را تقریباً هر فصلی لمس می‌کند، پس بیشترین احتمالِ برخورد را دارند:

```
backend/app/models/__init__.py        backend/app/main.py
backend/app/models/banking.py         backend/app/models/counters.py
backend/app/services/banking.py       backend/app/services/check_ops.py
backend/app/services/entry_source.py  backend/app/services/reports.py
backend/app/routers/treasury.py       backend/app/audit.py
desktop/src/api.ts                    desktop/src/lib/navModel.tsx
desktop/src/components/Dashboard.tsx  desktop/src/components/moduleLists.tsx
PROJECT_OVERVIEW.md                   OPEN_DECISIONS.md
```

**`desktop/src/api.ts` نکته‌ی خاص دارد:** همیشه در **انتهای فایل** بلوکِ تازه
اضافه کن، هرگز وسطش. این‌طور دو ایجنت که هم‌زمان اضافه می‌کنند، در بدترین حالت
یک تعارضِ ساده در انتهای فایل می‌سازند نه یک فایلِ درهم.

---

## منابعِ مشترکی که ادعا لازم دارند

| منبع | چرا |
|---|---|
| **`pytest`** | یک دیتابیسِ تستِ مشترک. دو اجرای همزمان شکست‌هایی می‌سازد که واقعی به‌نظر می‌رسند و نیستند. |
| **`alembic upgrade`** | همان دیتابیس. اگر روی اسکیمای یک‌بارمصرف کار می‌کنی، نامش را در ادعا بنویس. |
| **شماره‌ی مهاجرتِ بعدی** | **حتماً ادعا کن.** دو ایجنت که هم‌زمان `0114` بردارند، یک زنجیره‌ی دوسر می‌سازند — و بدتر، ممکن است یک ستون را دو بار بسازند. |

### درسِ ۱۴۰۵/۰۶/۲۰ — چرا این فایل ساخته شد

سه فصل روی یک شاخه ساخته شدند در حالی که همکارِ انسانی هم‌زمان `0109` و `0110`
را برداشت و **روی تولید برد**. نتیجه:

* شماره‌های ما باید `0111`/`0112`/`0113` می‌شدند.
* مهاجرتِ `0110` از قبل `checks.sayad_id` و `back_number` را ساخته بود و مهاجرتِ
  ما دوباره می‌ساختشان — **روی تولید می‌شکست**. `git` هم چیزی نگفت، چون تعارضِ
  متنی نبود.
* `git` در مدل **دو تعریفِ تکراری** از یک ستون ساخت و بی‌صدا merge کرد؛ در پایتون
  تعریفِ دوم برنده می‌شود، پس طولِ اشتباه روی ستونِ مستقر می‌نشست.
* و یک فصل ثابتِ فصلِ دیگر را شکست: نوشتنِ مستقیمِ `checks.status` بدونِ ثبتِ
  رویداد، که یک مسیرِ **از‌دست‌رفتنِ پول** باز می‌کرد.

هیچ‌کدام را تست نگرفت. همه با خواندنِ کدِ طرفِ مقابل پیدا شدند.

---

## تاریخچه‌ی ادعاهای بسته‌شده

نگه‌داشتنِ چند ردیفِ آخر کافی است؛ قدیمی‌ترها را پاک کن.

| ایجنت | فایل‌ها | کار | بسته‌شده |
|---|---|---|---|
| Claude (hesabdari-93) | مهاجرت `0121`، `services/returns.py`، `voiding.py`، `open_items.py`، `reports.py`، `credit.py`، `chart_codes.py`، UI برگشت و مِسترِ علت؛ آزادسازی `pytest` | فصلِ «فاکتور برگشتی»: تخصیصِ سطحِ ردیف، ابطالِ برگشت (و رفعِ قفلِ ابدیِ فاکتور)، حسابِ ۴۱۰۷، علتِ برگشت | ۱۴۰۵/۰۶/۲۱ |
| Claude (hesabdari-93) | `services/receipts.py`, `routers/receipts.py`, `0111_receipt_document.py`, `ReceiptVoucherPage.tsx` + merge با master | رسید دریافت، و حلِ تصادمِ شماره‌ی مهاجرت | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `services/open_items.py`, `services/settlements.py`, `models/settlement.py`, `0114_counterparty_settlement.py`, `TreasuryOpsPages.tsx` + merge با master | تسویه حساب طرف مقابل؛ شماره‌ی مهاجرت ۰۱۱۴ برداشته شد | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `services/check_search.py`, `check_ops.py`, `routers/check_ops.py`, `0115_cheque_traceability.py`, `CheckOpsPages.tsx` | جستجو و ردیابی چک (مهاجرت ۰۱۱۵) | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `models/inventory.py`, `advanced_inventory.py`, `services/items.py`, `units.py`, `pricing.py`, `0117`–`0120`, `ProductsPanel.tsx`, `UnitsPanel.tsx`, `ItemTaxonomyPanel.tsx` | تعریف کالا و خدمت — Item Master (مهاجرت‌های ۰۱۱۷ تا ۰۱۲۰) | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `services/warehouses.py`, `models/inventory.py`, `routers/inventory.py`, `0116_warehouse_master.py`, `WarehousesPanel.tsx` | تعریف و مدیریت انبار (مهاجرت ۰۱۱۶) | ۱۴۰۵/۰۶/۲۰ |
