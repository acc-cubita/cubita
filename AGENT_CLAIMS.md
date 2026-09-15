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
| Claude Code | `routers/inventory.py`, `schemas/inventory.py`, `ContactsPage.tsx`, `api.ts` | حذف و غیرفعال‌سازیِ طرف حساب | ۱۴۰۵/۰۶/۲۴ |
| Claude Code | `routers/payroll.py`, `schemas/payroll.py`, `services/payroll_contracts.py` | ویرایش و غیرفعال‌سازیِ کارمند | ۱۴۰۵/۰۶/۲۴ |
| Claude Code | `models/inventory.py`, `services/inventory.py`, `alembic/versions/0150_*` | ابطالِ تعدیلِ انبار (**مهاجرتِ ۰۱۵۰ — شماره را نگیرید**، ولی ⚠️ زیر را بخوان) | ۱۴۰۵/۰۶/۲۴ |
| Claude Code | `services/reports.py`, `routers/reports.py` | صورت تغییرات در حقوق صاحبان سهام | ۱۴۰۵/۰۶/۲۴ |

> **⚠️ هشدارِ تازه (۱۴۰۵/۰۶/۲۴): ادعای `0150` بالا دیگر درست نیست.** #76 («تنخواه
> صندوق شد») هم زمان `0150` گرفت و روی master مرج شد؛ پیمانکاریِ فازِ ۱ هم `0151`
> گرفته بود و مرج شد — یعنی `alembic heads` دو سر داد. رفعش شد: زنجیره‌ی
> پیمانکاری (فازهای ۱ تا ۴) پشتِ `0150` به `0152`–`0155` شماره‌گذاریِ مجدد شد
> (`fix/contracting-migration-renumber`). اگر «ابطالِ تعدیلِ انبار» هنوز `0150`
> است، باید پشتِ `0155` بیاید (یا هرچه سرِ فعلیِ master بود — `alembic heads` را
> دوباره بسنج).
>
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
| Claude Sonnet 5 | مهاجرت `0153`→`0154` (پشتِ `0152`؛ **۱۴۰۵/۰۶/۲۴: بعداً دوباره شماره‌گذاری شد به `0154` پشتِ `0153`، همراهِ رفعِ دوسرِ مهاجرت — `fix/contracting-migration-renumber`**)، `models/contracting.py` (`ContractStatement`)، `schemas/contracting.py`، `services/contracting.py`، `routers/contracting.py`، `models/counters.py`، `routers/numbering.py`، `audit.py`، `desktop/src/pages/contracting/ContractingOpsPages.tsx` و `ContractingListPages.tsx`، `navModel.tsx`، `moduleLists.tsx`، `Dashboard.tsx`، `HelpPage.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و پنج schemaِ probeِ یک‌بارمصرف (`cubita_probe2`–`5`، حذف شدند) | پیمانکاری، فازِ ۳ (شاخه‌ی `feat/contracting-statement`، پشتِ `feat/contracting-amendment`): صورت‌وضعیتِ دریافتی — بدونِ سند (تصمیمِ کاربر)، کسرِ سپرده/پیش‌پرداخت خودکار و Snapshot‌شده از پیمان؛ یک باگِ Decimal/float در محاسبه پیدا و رفع شد | ۱۴۰۵/۰۶/۲۴ |
| Claude Sonnet 5 | مهاجرت `0152`→`0153` (پشتِ `0151`؛ **۱۴۰۵/۰۶/۲۴: بعداً دوباره شماره‌گذاری شد به `0153` پشتِ `0152`، همراهِ رفعِ دوسرِ مهاجرت — `fix/contracting-migration-renumber`**)، `models/contracting.py` (`ContractAmendment`)، `schemas/contracting.py`، `services/contracting.py`، `routers/contracting.py`، `models/counters.py`، `routers/numbering.py`، `audit.py`، `desktop/src/pages/contracting/ContractingOpsPages.tsx` و `ContractingListPages.tsx`، `navModel.tsx`، `moduleLists.tsx`، `Dashboard.tsx`، `HelpPage.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و سه schemaِ probeِ یک‌بارمصرف (`cubita_probe2/3/4`، هرسه حذف شدند) | پیمانکاری، فازِ ۲ (شاخه‌ی `feat/contracting-amendment`، پشتِ `feat/contracting`): متممِ پیمان — رکوردِ الحاقی نه بازنویسی، `total_amount` ثابت می‌ماند و مبلغِ روز از جمعِ متمم‌ها مشتق می‌شود؛ پیمانِ پایان‌یافته متممِ تازه نمی‌پذیرد | ۱۴۰۵/۰۶/۲۴ |
| Claude Sonnet 5 | مهاجرت `0151`→`0152` (پشتِ `0149`؛ `0150` مالِ ادعای دیگری بود، دست نخورد؛ **۱۴۰۵/۰۶/۲۴: بعداً دوباره شماره‌گذاری شد به `0152` پشتِ `0150`، چون #76 هم `0150` گرفت و هر دو روی master مرج شدند — `fix/contracting-migration-renumber`**)، `models/contracting.py` (تازه)، `schemas/contracting.py` (تازه)، `services/contracting.py` (تازه)، `routers/contracting.py` (تازه)، `models/counters.py`، `services/permissions.py`، `services/modules.py`، `main.py`، `audit.py`، `routers/numbering.py`، `desktop/src/pages/contracting/ContractingOpsPages.tsx` و `ContractingListPages.tsx` (تازه)، حذفِ `ContractingPage.tsx`، `navModel.tsx`، `moduleLists.tsx`، `Dashboard.tsx`، `HelpPage.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و schemaِ probeِ `cubita_probe` (حذف شد) | پیمانکاری، فازِ ۱ (شاخه‌ی `feat/contracting`، از صفر): ثبتِ پیمان بدونِ سندِ حسابداری، گذارِ محدودِ وضعیت، فهرستِ پیمان‌ها — الگوی «فروش» به‌جای تب‌دار، چون پنج عملیاتِ این ماژول پنج نوعِ رکوردِ متفاوت‌اند | ۱۴۰۵/۰۶/۲۳ |
| Claude Opus 5 | مهاجرت `0143` → `0149` پس از ادغامِ master (شاخه‌ی `feat/inventory-valuation-run`، پشتِ `0148`)؛ جابه‌جاییِ `0135`→`0141` و `0136`→`0142` با ادغامِ master در #47/#52/#54؛ `models/inventory_valuation.py`، `models/counters.py`، `models/__init__.py`، `services/valuation.py`، `services/valuation_runs.py`، `schemas/inventory_valuation.py`، `routers/inventory_valuation.py`، `routers/numbering.py`، `main.py`، `services/warehouse_issues.py`، `services/integrity.py`، `services/entry_source.py`، `audit.py`، `schemas/reports.py`، `InventoryValuationPanel.tsx` (تازه)، `InventoryPage.tsx`، `KardexTable.tsx`، `moduleSections.tsx`، `moduleLists.tsx`، `kit.tsx`، `HelpPage.tsx`، `App.css`، انتهای `api.ts`؛ آزادسازی `pytest`، schemaِ یک‌بارمصرفِ `cubita_probe` (حذف شد)؛ پایگاه دادهٔ توسعه روی `0134` ماند | فصلِ «قیمت‌گذاری اسناد انبار»، نوبتِ دوم: پیش‌نمایشِ بی‌نوشتن، سندِ اصلاحی با طرفِ مقابلِ حرکتِ اصلی، بهای برگشتِ خروج از خروجِ مبدأ، ابطالِ فقط-آخرین و قفلِ ابطالِ سندِ اصلاح‌شده، تبِ «قیمت‌گذاری اسناد» | ۱۴۰۵/۰۶/۲۳ |
| Claude Opus 5 | مهاجرت `0145`، `services/serials.py` (تازه)، `services/inventory_analytics.py` (تازه)، `models/advanced_inventory.py`، `routers/advanced_inventory.py`، `routers/reports.py`، `schemas/reports.py`، `schemas/advanced_inventory.py`، `SerialSearchTab.tsx` (تازه)، `api.ts` | فصلِ گزارش‌های انبار: ردیابیِ سریال از بن‌بست درآمد (دفترِ رویداد + جست‌وجو)، مجوزِ مقدار از مجوزِ بها جدا شد، و ابعادِ تأمین‌کننده/مشتری/هدف اضافه شدند | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0144`، `models/stock_count.py`، `models/counters.py`، `schemas/stock_count.py`، `services/stock_taking.py`، `services/printing.py`، `routers/stock_taking.py`، `routers/numbering.py`، `audit.py`، `StockCountPanel.tsx`، `api.ts` | فصلِ انبارگردانی: عکسِ سیستمی به لحظه‌ی شمارش رفت (حرکتِ وسطِ شمارش دو بار شمرده می‌شد)، شمارشِ کور با «نشمرده ≠ صفر»، دامنه‌ی انتخابی، برگه‌ی شمارشِ چاپی، گزارشِ حرکتِ پس از شمارش، شماره‌ی سند و حسابرسی | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0143`، `services/chart_codes.py`، `seed.py`، `tests/test_sales_rounding_account.py` (تازه)، `DEPLOY_NOTES.md` | نقشِ `sales_rounding` روی حسابِ ۴۱۰۲ («فروش کالا - آنلاین») نشسته بود و رندِ هر فاکتور داخلِ درآمدِ فروشِ آنلاین می‌رفت؛ به حسابِ اختصاصیِ ۴۱۰۸ منتقل شد، بدونِ بازنویسیِ ردیف‌های سندِ گذشته | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | `services/valuation.py` (تازه)، `voiding.py`، `inventory.py`، `warehouse_issues.py`، `warehouse_receipts.py`، `transfers.py`، `issue_returns.py`، `returns.py`، `manufacturing.py`، `onboarding.py`، `stock_taking.py`، `reports.py`، `integrity.py`، `schemas/reports.py`، `routers/reports.py`، `routers/inventory.py`، `routers/invoices.py`، `KardexTable.tsx` (تازه)، `KardexPanel.tsx`، `KardexDrawer.tsx`، `Reports.tsx`، `IntegrityPage.tsx`، `HelpPage.tsx`، `App.css`، `api.ts`؛ آزادسازی `pytest` | فصلِ «قیمت‌گذاری اسناد انبار»، نوبتِ اول (شاخه‌ی `feat/inventory-valuation`، پشتِ #52، بدونِ مهاجرت): یک موتورِ ارزش‌گذاری با ترتیبِ (تاریخ، seq)، بهای روزِ سندِ پیش‌تاریخ، گاردِ خطِ زمان در ثبت و ابطال، یکی‌شدنِ بازپخش با ثبت (برگشت از خرید، ابطالِ خروج/انتقال)، قفلِ ویرایشِ دستیِ میانگین، کاردکس و ارزشِ موجودیِ ریالی، دو بررسیِ تازه‌ی یکپارچگی | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0136` → `0142` (شاخه‌ی `feat/credit-debit-notice`، پشتِ `0141`ِ PR #47)، `models/sales_ops.py`، `schemas/sales_ops.py`، `services/sales_ops.py`، `routers/sales_ops.py`، `deps.py`، `services/open_items.py`، `services/reports.py`، `schemas/reports.py`، `SalesOpsPages.tsx`، `SalesListPages.tsx`، `ContactStatementDrawer.tsx`، `navModel.tsx`، `TopNav.tsx`، `CommandPalette.tsx`، `ModulesPage.tsx`، `Dashboard.tsx`، `kit.tsx`، `HelpPage.tsx`، `App.css`، `api.ts`، `mobile/src/api/contacts.ts`؛ آزادسازی `pytest` و پایگاه دادهٔ توسعه | فصلِ «اعلامیه بدهکار و بستانکار» (نوبتِ دوم): ارزِ اعمال‌شده، گاردِ دوقاعده‌ای حساب، ابطالِ قفل‌دار از مسیرِ مشترک، رونوشت/اصلاح، دفترِ سمتِ سرور، ردیابیِ کارتِ حساب، مجوزِ `invoices`/`accounting`، دسترسی از خرید | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0135` → `0141` پس از ادغامِ master (شاخه‌ی `feat/service-purchase-invoice`)، `models/invoices.py`، `models/purchase_deductions.py`، `schemas/purchase_deductions.py`، `services/purchase_deductions.py`، `routers/purchase_deductions.py`، `services/inventory.py`، `services/returns.py`، `services/warehouse_receipts.py`، `services/chart_codes.py`، `seed.py`، `printing.py`، `pdf_invoice.py`، `routers/invoices.py`، `ServicePurchaseTab.tsx`، `PurchaseDeductionTypesPanel.tsx`، `InvoiceList.tsx`، `PurchasesPage.tsx`، `Dashboard.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و پایگاه دادهٔ توسعه | فصلِ «فاکتور خرید خدمات»: نوعِ سند با سریِ شماره‌ی خودش، انواعِ کسر و کسوراتِ Snapshot، سندِ سه‌بدهی، حسابِ هزینه روی ردیف (باگِ برگشت)، مانده‌ی واقعی و میان‌برِ پرداخت، چاپ و رابط | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0140` · `models/payroll.py` · `services/payroll.py` · `services/payroll_contracts.py` · `schemas/payroll.py` · `routers/payroll.py` · `PayrollRefPages.tsx` · `api.ts` | کاتالوگِ عوامل: زنده‌کردنِ `is_active`، اولویتِ نمایش، ویرایشِ عامل، و پروفایلِ حسابداریِ عامل | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0138`/`0139` · `models/payroll.py` · `services/payroll.py` · `services/benefits.py` · `schemas/payroll.py` · `routers/payroll.py` · `services/chart_codes.py` · `PayrollSettingsPanel.tsx` · `api.ts` | تنظیمات حقوق: پارامترهای قانونی از کد به تنظیمات، و مشارکتِ عامل‌ها در مبناها | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0137` (پشتِ `0136`ِ PR #49)، `models/payroll.py`، `schemas/payroll.py`، `routers/payroll.py`، `services/payroll.py`، `services/benefits.py`، `audit.py`، صفحه‌ی جداول مالیات در رابط، انتهای `api.ts`؛ `pytest` | فصلِ «تعریف جداول مالیات»: جدولِ مالیات مِسترِ مستقل با تاریخِ اجرا/گروه/نوعِ محاسبه، بازنشستگیِ ضربِ درصدِ گروه، ردیابیِ قاعده روی فیش، عیدی با جدولِ خودش، و باگِ پلکانِ نامرتب | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0136` (پشتِ `0134`؛ **اگر PR #47 با `0135` زودتر merge شود، این باید پشتِ `0135` rebase شود**)، `models/payroll.py`، `schemas/payroll.py`، `routers/payroll.py`، `services/payroll.py`، `audit.py`، `PayrollRefPages.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` | فصل‌های «تعریف شعب بیمه و مالیات» و «تعریف شعب بیمه»: پیوندِ شعبه به طرف حساب، حسابرسی، مسیرِ ویرایش، نوعِ سومِ «بیمه تکمیلی»، هسته‌ی مشترکِ ثبتِ کارگاه، قیدِ نوع‌محورِ «نحوه محاسبه مالیات»، تغییرناپذیریِ نوع پس از استفاده، و عکسِ شعبه روی فیش | ۱۴۰۵/۰۶/۲۲ |
| Claude Opus 5 | مهاجرت `0134` (روی `feat/warehouse-issue-return`، پشتِ `0133` — ادعای `0129`–`0134` روی شاخه‌ی `chore/claim-0129-0134` برای master)، `models/issue_returns.py`، `services/issue_returns.py`، `routers/issue_returns.py`، `services/returns.py`، `services/warehouse_issues.py`، `voiding.py`، `printing.py`، `marketplace.py`، `IssueReturnsTab.tsx`، `InventoryPage.tsx`، `SalesListPages.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و پایگاه دادهٔ توسعه | فصلِ «برگشت خروج انبار»: سندِ مستقل با مبنای اجباری، بها و حساب از خروجِ مبدأ، جداشدنِ برگشتِ فیزیکی از فاکتور برگشتی (`stock_mode`)، دو باگِ برگشتِ فروش، چاپ و رابط | ۱۴۰۵/۰۶/۲۱ |
| Claude Opus 5 | مهاجرت `0133` (روی `feat/warehouse-issue`، پشتِ `0132`ِ `feat/warehouse-receipt` — هیچ‌کدام هنوز روی master نیست)، `services/warehouse_issues.py`، `services/transfers.py`، `routers/warehouse_issues.py`، `routers/transfers.py`، `services/returns.py`، `voiding.py`، `printing.py`، `WarehouseIssuesTab.tsx`، `InventoryPage.tsx`، `salesInvoiceDraft.ts`، فرم و ویزاردِ انتقال، انتهای `api.ts`؛ آزادسازی `pytest` و پایگاه دادهٔ توسعه | فصلِ «خروج انبار»: خروجِ مستقیم (فروش/مصرف/سایر)، انتقال از موتورِ خودش با پنج گاردِ تازه، خروج ← فاکتور فروش، چاپِ مجوز، فهرستِ خروج‌ها، بهای برگشتِ فروش | ۱۴۰۵/۰۶/۲۱ |
| Claude Opus 5 | مهاجرت‌های `0129`–`0132` (نخست `0123`–`0126`، سه بار جابه‌جا)، `warehouse_receipts.py`، `freight.py`، `returns.py`، `payments.py`، `printing.py`، `reports.py`، `WarehouseReceiptsTab.tsx`، `PurchasesPage.tsx`، `PaymentVoucherPage.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و پایگاه دادهٔ توسعه | فصل‌های «رسید انبار» و «برگشت رسید انبار»: رسیدِ مستقیم، کالای در راه، حمل و بهای تمام‌شده، برگشتِ لنگرزده به رسید، چاپ، میان‌برِ اعلامیه پرداخت و رابط | ۱۴۰۵/۰۶/۲۱ |
| Claude (hesabdari-93) | مهاجرت `0126`، `services/sales_posting.py`، `routers/invoices.py`، `models/tenant.py`، `PersonalizationPage.tsx`؛ آزادسازی `pytest` | سیاستِ صدورِ فاکتور فروش (خودکار/دومرحله‌ای) و رفعِ بن‌بستِ ابطال در حالتِ خودکار | ۱۴۰۵/۰۶/۲۱ |
| Claude (hesabdari-93) | ادغامِ پنج فصلِ کدکس با master؛ `0114`–`0116` → `0123`–`0125`، `voiding.py`، `warehouse_issues.py`، `sales_invoices.py`، `inventory.py`؛ آزادسازی `pytest` | فرودِ شاخه‌ی سرگردانِ کدکس: شماره‌های متصادم، ستونِ دوبارساخته، انحرافِ میانگینِ بها، و چهار گاردِ master که در ادغام برمی‌گشتند | ۱۴۰۵/۰۶/۲۱ |
| Claude (hesabdari-93) | مهاجرت `0122`، `services/pricing.py`، `routers/advanced_inventory.py`، `routers/sales_ops.py`، `audit.py`، `PriceListsPanel.tsx`، `SalesOpsPages.tsx`، `PosPage.tsx`، `salesInvoiceDraft.ts`؛ آزادسازی `pytest` | فصلِ «اعلامیه قیمت»: ماتریسِ قیمت قابلِ ورود شد، سه موتورِ قیمت یکی شد، مسیری که ماتریس را پاک می‌کرد بسته شد، تغییرِ گروهیِ فی با یکتاسازی | ۱۴۰۵/۰۶/۲۱ |
| Claude (hesabdari-93) | مهاجرت `0121`، `services/returns.py`، `voiding.py`، `open_items.py`، `reports.py`، `credit.py`، `chart_codes.py`، UI برگشت و مِسترِ علت؛ آزادسازی `pytest` | فصلِ «فاکتور برگشتی»: تخصیصِ سطحِ ردیف، ابطالِ برگشت (و رفعِ قفلِ ابدیِ فاکتور)، حسابِ ۴۱۰۷، علتِ برگشت | ۱۴۰۵/۰۶/۲۱ |
| Codex | مهاجرت `0116`، فاکتور فروش/خروج مستقل، UI، مستندات و تست‌ها؛ آزادسازی `pytest` و probe | جداسازی فاکتور/سند/خروج/وصول، Snapshot و وضعیت‌های مستقل | ۱۴۰۵/۰۶/۲۰ |
| Codex | مهاجرت `0115`، مسیر پیش‌فاکتور و Source Link فروش، UI، مستندات و تست‌ها؛ آزادسازی `pytest` و probe | تبدیل جزئی امن، Snapshot تاریخی، خاتمه/بازگشایی، تکثیر و جداسازی خروج انبار | ۱۴۰۵/۰۶/۲۰ |
| Codex | مهاجرت `0114`، مسیر Purchase/print، UI فهرست خرید، مستندات و تست‌ها؛ آزادسازی `pytest` و probe | Snapshot تاریخی طرفین، Trace پرداخت/سند و گارد ابطال وابستگی | ۱۴۰۵/۰۶/۲۰ |
| Codex | مسیر Payment/Purchase در بک‌اند، UI اعلامیه پرداخت، مستندات و تست‌ها؛ آزادسازی شماره `0114` و `pytest` | Reference بدون تخصیص زودهنگام، مجوز درست ابطال و ناوبری سند حسابداری | ۱۴۰۵/۰۶/۲۰ |
| Codex | مسیر خرید/رسید انبار در بک‌اند و `desktop/src/`؛ مستندات و تست‌ها؛ آزادسازی شماره `0114` | ابطال رسید در UI، idempotency صدور، و همگامی مانده بچ با ابطال | ۱۴۰۵/۰۶/۲۰ |
| Claude (hesabdari-93) | `services/receipts.py`, `routers/receipts.py`, `0111_receipt_document.py`, `ReceiptVoucherPage.tsx` + merge با master | رسید دریافت، و حلِ تصادمِ شماره‌ی مهاجرت | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `services/open_items.py`, `services/settlements.py`, `models/settlement.py`, `0114_counterparty_settlement.py`, `TreasuryOpsPages.tsx` + merge با master | تسویه حساب طرف مقابل؛ شماره‌ی مهاجرت ۰۱۱۴ برداشته شد | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `services/check_search.py`, `check_ops.py`, `routers/check_ops.py`, `0115_cheque_traceability.py`, `CheckOpsPages.tsx` | جستجو و ردیابی چک (مهاجرت ۰۱۱۵) | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `models/inventory.py`, `advanced_inventory.py`, `services/items.py`, `units.py`, `pricing.py`, `0117`–`0120`, `ProductsPanel.tsx`, `UnitsPanel.tsx`, `ItemTaxonomyPanel.tsx` | تعریف کالا و خدمت — Item Master (مهاجرت‌های ۰۱۱۷ تا ۰۱۲۰) | ۱۴۰۵/۰۶/۲۰ |
| Claude Opus 5 | `services/warehouses.py`, `models/inventory.py`, `routers/inventory.py`, `0116_warehouse_master.py`, `WarehousesPanel.tsx` | تعریف و مدیریت انبار (مهاجرت ۰۱۱۶) | ۱۴۰۵/۰۶/۲۰ |
