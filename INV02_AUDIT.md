# INV-02 — ممیزی و طرح اجرایی پیش از مهاجرت

تاریخ: 2026-10-02. این گزارش **قبل از پیاده‌سازی** است؛ هیچ مهاجرت یا تغییر رفتار عملیاتی انجام نشده است.

## Current HEAD

- شاخهٔ آغاز: `feat/enterprise-market-release-1.9.10`.
- کامیت آغاز محلی: `55dba61b0f88d0a39c7117e5012547664953913e`.
- مبنای توسعه پس از fetch: `origin/master` در `25e8ab58e8c12bc500a9c9db689c76f1a58b2c3a`؛ PR #262 ادغام شده است.
- شاخهٔ کار: `feat/inv02-multi-uom`، ساخته‌شده از همین master.
- درخت کار هنگام آغاز تمیز بود. هیچ ادعای فعال دیگری نبود.
- سر فعلی فایل‌های مهاجرت `0188` است؛ شمارهٔ نامزد `0189`، پیش از ساخت باید دوباره سر و ادعاها بررسی شوند.

## معماری موجود و تمام مصرف‌کنندگان چهار فیلد قدیمی

جست‌وجوی `primary_unit_id|secondary_unit_id|conversion_factor|conversion_mode` در کد اجرایی backend و desktop:

| فایل | کاربرد |
|---|---|
| `backend/app/models/inventory.py` | تعریف چهار ستون روی Item؛ ضریب `Numeric(18,6)`، شناسه‌های واحد nullable |
| `backend/app/schemas/inventory.py` | ورودی ایجاد/ویرایش و خروجی کالا، اعتبارسنجی mode و factor |
| `backend/app/routers/inventory.py` | `_apply_units`، حل متن قدیمی به واحد، شمارش استفاده برای غیرفعال‌کردن، همگامی نام واحد اصلی |
| `backend/app/services/units.py` | resolve/get_or_create، حفاظت غیرفعال‌کردن، sync_item_unit، assert_conversion، to_primary، row |
| `backend/app/services/warehouse_issues.py` | تبدیل حوالهٔ مستقیم با to_primary؛ محاسبهٔ نمایشی فرعی با تقسیم جداگانه در `_secondary` |
| `backend/app/services/sales_review.py` | تقسیم qty بر ضریب فعلی برای نمایش فرعی، نام اصلی/فرعی در گزارش |
| `desktop/src/api.ts` | انواع Item/Input؛ ضریب ورودی فعلاً number |
| `desktop/src/components/ProductsPanel.tsx` | بارگذاری/ارسال فرم اصلی و فرعی، نمایش نسبت؛ تبدیل رشته به Number |

مصرف‌کنندگان مستقیم `to_primary` فقط حوالهٔ مستقیم و دو مسیر در `services/issue_returns.py` هستند. اشاره‌های docstring در schemas مصرف اجرایی نیستند.

`UnitOfMeasure` دادهٔ پایهٔ **مستأجرمحور** است، نه یک جدول مشترک بین تمام شرکت‌ها. در طرح جدید هم واحدها بین کالاهای همان شرکت مشترک‌اند؛ UUID واحد یک شرکت به شرکت دیگر انتقال داده نمی‌شود.

مهاجرت `0118_units_of_measure.py` واحدهای متنی را به رجیستری برده؛ `0167_standard_units_backfill.py` فهرست استاندارد را تکمیل می‌کند. سابقهٔ این مهاجرت‌ها تغییر نمی‌کند.

## Trace دامنه‌ها و شکاف‌ها

وضعیت‌های زیر مربوط به **امروز** هستند؛ FOLLOW-UP یعنی کار لازم در INV-02، نه مجوز اعلام Done با این شکاف.

| دامنه | شاهد موجود | وضعیت امروز / کار لازم |
|---|---|---|
| Items | inventory model/router، units service، ProductsPanel | FOLLOW-UP؛ حداکثر دو واحد، یک تبدیل مستقیم، variable عمداً رد می‌شود |
| Purchases | `inventory.post_purchase_invoice`، PurchaseInvoiceLine، purchaseInvoiceDraft/PurchaseInvoiceForm | FOLLOW-UP؛ qty ورودی در فاکتور و Ledger یکسان؛ effective cost بر همان qty تقسیم می‌شود؛ unit_id ورودی ندارد |
| Sales | `inventory.post_sales_invoice`، sales_invoices، sales_posting، SalesInvoiceLine، salesInvoiceDraft/SalesInvoiceForm | FOLLOW-UP؛ کنترل موجودی و ایجاد حواله با qty مستقیم، unit_snapshot از Item.unit؛ price policy بدون زمینهٔ unit فراخوانی می‌شود |
| POS | PosPage از همان فروش استفاده می‌کند | FOLLOW-UP؛ cart فقط item/qty/price، بدون واحد انتخابی؛ مقایسهٔ موجودی در همان مقدار مستقیم |
| Inventory | `get_stock_qty/get_total_stock_qty` = SUM(StockLedger.qty) | SUPPORTED برای کالای تک‌واحد؛ تبدیل باید پیش از ثبت انجام شود و SUM همین مقدار پایه بماند |
| Receipt | warehouse_receipts، WarehouseReceiptLine، WarehouseReceiptsTab | FOLLOW-UP؛ رسید مستقیم qty/cost مستقیم؛ رسید فاکتور باقی‌مانده را با qty فاکتور مقایسه می‌کند؛ تاریخچهٔ تبدیل ندارد |
| Issue | warehouse_issues، WarehouseIssueLine، WarehouseIssuesTab | FOLLOW-UP؛ ورودی واحد پذیرفته می‌شود، اما مقدار ورودی و path/source کامل ذخیره نمی‌شود؛ دادهٔ فرعی نمایشی کافی نیست |
| Transfers | transfers، StockTransferLine، TransferForm/transferDraft | FOLLOW-UP؛ qty مستقیم در هر دو سمت، بدون واحد/نسبت تاریخی؛ ابطال از حرکت اصلی برمی‌گردد |
| Returns | returns و issue_returns، ReturnLineها، PurchaseReturnForm/SalesReturnForm/IssueReturnsTab | FOLLOW-UP؛ reference ردیف اصلی وجود دارد، اما qty تجاری و پایه تفکیک نشده؛ نباید ضریب جاری را برای برگشت تاریخی خواند |
| Batch | advanced_inventory.StockBatch و batches | FOLLOW-UP؛ ماندهٔ Batch برچسب‌خورده از SUM دفتر، fallback قدیمی صریح؛ override واحد ندارد |
| Marketplace | marketplace، listing/component، enterprise_market_orders/posting/catalog/sync/recovery | FOLLOW-UP؛ listing.unit متن و component.qty نسبت بسته است؛ fulfillment واحد/qty دارد ولی conversion metadata ندارد؛ نگاشت فقط هویت کالا را می‌سنجد |
| Production | manufacturing، Bom/BomLine، ProductionPlan/Order، ManufacturingPage | FOLLOW-UP؛ qty اجزا × qty_produced/yield_qty مستقیماً مصرف می‌شود؛ BOM و خروجی واحد انتخابی ندارند |
| Kardex | StockLedger و valuation | SUPPORTED برای running base qty؛ FOLLOW-UP برای نمایش مقدار واردشده و نسبت تاریخی |
| Valuation | valuation و valuation_runs | SUPPORTED برای دریافت qty پایه و cost هر واحد پایه؛ FOLLOW-UP برای ورودی‌ها و دقت جدید؛ الگوریتم ارزش‌گذاری بازطراحی نمی‌شود |
| Pricing | advanced_inventory.PriceListItem.unit_id، pricing.resolve/quote_line/assert_within_policy | SUPPORTED برای قیمت مستقل هر واحد؛ FOLLOW-UP برای ارسال واحد انتخابی از تمام فرم‌ها و کنترل مجازبودن آن |
| Reports | sales_review، production_reports، گزارش و چاپ اسناد | FOLLOW-UP؛ شمارش تجاری و موجودی نباید جمع شوند؛ گزارش فرعی فعلی ضریب جاری را می‌خواند |
| Formula عمومی / تولید چندمرحله‌ای / landed cost / consignment | خارج از درخواست | NOT APPLICABLE |

نکتهٔ مثبت: ابطال عمومی در `voiding._compensating_moves` مقدار **حرکت اصلی** را منفی می‌کند؛ همین اصل باید حفظ شود. این مسیر امروز هم به ضریب جاری وابسته نیست.

در `OPEN_DECISIONS.md` بند ۲۹ موتور واحد تا فصل اختصاصی موکول شده است. INV-02 این تصمیم را باز می‌کند؛ متن قدیمی آن بند وضعیت فعلی رجیستری واحد را دقیق توصیف نمی‌کند و پس از پیاده‌سازی باید حذف و تصمیم در تاریخچه ثبت شود.

## طرح دادهٔ پیشنهادی

1. `item_units`: tenant/item/unit، مجوز چهار زمینه، decimal_allowed، is_active و timestamps؛ unique tenant/item/unit.
2. واحد پایهٔ یکتا در `Item.primary_unit_id` حفظ و non-null می‌شود؛ همین ستون تنها مرجع هویت Base است. is_base خروجی مشتق می‌شود تا دو پرچم مستقل برای Base نسازیم. عضویت Base در item_units با سرویس و قید سازگاری پایگاه‌داده تضمین می‌شود.
3. `item_unit_conversions`: tenant/item، from/to واحد مجاز، fixed/variable، factor مثبت برای fixed، version و وضعیت فعال؛ منع self-rule و قید factor/mode در DB. ارتباط دو سر به واحدهای همان کالا با FK مرکب و قید tenant.
4. `batch_unit_conversions`: tenant/batch/from/to، نسبت واقعی و metadata مقدارهای مشاهده‌شده. سازگاری batch/item/tenant سنجیده می‌شود.
5. Snapshot مشترک ردیف‌های عملیاتی: مقدار و واحد واردشده، مقدار و واحد پایه، نام واحدهای تاریخی، factor/path/source/version. JSON تاریخی فقط رشتهٔ Decimal دارد؛ فیلدهای قابل‌جمع numeric مستقل می‌مانند.
6. qty تجاری فاکتور برای قیمت و چاپ حفظ می‌شود؛ `base_qty` برای خروج/ورود و بها افزوده می‌شود. حواله/رسید/انتقال و Ledger.qty مقدار پایه‌اند و entered_qty جدا دارند. نام واحد خروجی صریح است؛ API قدیمی و تازه مخلوط و مبهم نمی‌شوند.
7. Batch metadata به رسید ورودی مرتبط می‌شود؛ انتقال Batch نسبت واقعی را به Batch مقصد منتقل می‌کند. برداشت از چند Batch با نسبت‌های متفاوت بدون تفکیک یا نسبت واقعی روشن رد می‌شود.
8. واحد BOM و yield/output افزوده می‌شود؛ مقدار پایهٔ مواد قبل از حواله با همین موتور محاسبه می‌شود. نسبت مواد به محصول همچنان BOM است.

هیچ ستون قدیمی در مهاجرت اول حذف نمی‌شود. چهار ستون legacy در API سازگاری باقی می‌مانند؛ secondary/factor/mode projection موتور جدید خواهند بود و نوشتن از API قدیمی به همان مدل جدید ترجمه می‌شود. dual-read دائمی ساخته نمی‌شود.

## مهاجرت دادهٔ قدیمی

- مهاجرت نامزد `0189` پشت `0188`، پس از تأیید کاربر و بازبینی سر/ادعاها.
- preflight: نبود واحد اصلی، واحد متعلق به tenant دیگر، فرعی برابر اصلی، mode نامعتبر و fixed factor غیرمثبت گزارش می‌شوند؛ دادهٔ خراب با ضریب فرضی ۱ پنهان نمی‌شود.
- primary خالی فقط از نام موجود Item.unit و رجیستری **همان tenant** قابل بازیابی است؛ نام خالی یا تناقض قابل‌حدس نیست و موجب خطای تشخیصی پیش از تغییر داده خواهد شد.
- واحد اصلی و فرعی در item_units وارد می‌شوند؛ fixed قدیمی تبدیل secondary → primary با همان factor؛ variable قدیمی rule بدون ضریب ثابت می‌گیرد.
- داده‌های تاریخی به ضریب **امروز** دوباره تبدیل نمی‌شوند. qty و unit_snapshot اصلی حفظ می‌شوند؛ جایی که ورودی تبدیل‌شدهٔ قدیمی ذخیره نشده، snapshot با منبع `legacy_base` و محدودیت شواهد مشخص می‌شود؛ path تاریخی اختراع نمی‌شود.
- backfill زیر rls_disabled روی جدول‌های مشخص، سپس بازگرداندن ENABLE/FORCE و سنجش واقعی؛ دادهٔ دو tenant در آزمون مهاجرت.
- downgrade بعد از معاملات چندواحدی امن نیست: جدول‌ها و snapshot جدید از بین می‌روند و دقت کاهش می‌یابد؛ باید downgrade دارای دادهٔ غیرقابل‌نمایش در legacy مسدود و مسیر بازیابی پشتیبان مستند شود.

## Precision و الگوریتم پیشنهادی

- مقدار ذخیره‌شده `Numeric(24,8)`؛ ۱۶ رقم صحیح، بیشتر از دامنهٔ فعلی Numeric(18,3) با ۱۵ رقم صحیح. تمام ستون‌های درگیر زنجیرهٔ انبار، رزرو، Batch، فاکتور، برگشت و تولید باید هماهنگ گسترش یابند؛ گسترش تنها Ledger کافی نیست.
- factor ذخیره‌شده `Numeric(30,12)`؛ مقدار موثر برگرفته از دو مقدار واقعی با numerator/denominator یا path تاریخی حفظ می‌شود تا 150/36 به یک ضریب گرد‌شده و مقدار 149.999999… تبدیل نشود.
- ورودی JSON رشتهٔ Decimal؛ خروجی هم رشته. frontend تبدیل canonical را محاسبه نمی‌کند و فقط preview سرور را نمایش می‌دهد. `Number` برای محاسبهٔ تبدیل حذف می‌شود.
- الگوریتم در `services/units.py` گسترش می‌یابد؛ wrapper قدیمی to_primary به همان موتور واگذار می‌کند. تقسیم‌های نمایشی مستقل warehouse_issues/sales_review نیز حذف می‌شوند.
- برای تطابق دقیق مسیرها و reverse دارای اعشار تکرارشونده، نسبت‌های Decimal در محاسبات گراف به کسر دقیق تبدیل می‌شوند؛ تبدیل خروجی Decimal فقط در مرز ذخیره با ROUND_HALF_UP و scale=8. هیچ float در موتور یا قرارداد Quantity نیست.
- مسیر قطعی با ترتیب پایدار واحد/rule؛ consistency چرخه و چندمسیر با نسبت دقیق، نه tolerance شناور. inverse همان edge است، نه rule جدا.
- اولویت transaction > batch > item؛ override فقط برای قاعدهٔ variable مجاز در زمینهٔ مشخص و با validation کامل. گراف contextual دوباره برای تناقض/ابهام سنجیده می‌شود.
- self مقدار ثابت ۱؛ ضریب نامعتبر، مسیر گم‌شده، واحد غیرفعال/غیرمجاز، اعشار ممنوع و مقدار گرد‌شدهٔ صفر خطای روشن می‌دهند.
- Base کالای دارای سابقهٔ عملیاتی عوض نمی‌شود؛ صرف تغییر Base بدون تبدیل تمام سوابق، معنای SUM دفتر را خراب می‌کند.
- برگشت جزئی از snapshot اصل سهم می‌گیرد و برگشت نهایی residual پایه را می‌بندد تا گردکردن چند برگشت، موجودی اضافی نسازد. Void عین حرکت اصلی را معکوس می‌کند.

## همزمانی، قیمت و بازار

- قفل Item پیش از خواندن graph و ثبت snapshot؛ تغییر rule نیز همان قفل را می‌گیرد؛ ترتیب قفل‌ها پایدار. retry از سند/receipt ذخیره‌شده استفاده می‌کند.
- اجازهٔ تعریف rule با مجوز تنظیمات کالا؛ cashier تنها واحد فروش مجاز را انتخاب می‌کند. تغییر rule در Audit موجود با old/new/user/date ثبت می‌شود.
- قیمت انتخابی مربوط به واحد تجاری است و از factor ضرب نمی‌شود. هزینهٔ پایه = ارزش واقعی ورود / base_qty؛ مبلغ و مالیات بر مقدار تجاری و قیمت تجاری‌اند.
- Marketplace metadata نسخه‌دار برای واحد تجاری، مقدار پایه و مسیر/نسبت snapshot؛ نگاشت واحد بین tenantها با تأیید و قواعد محلی، نه UUID فروشنده. فروشنده و خریدار ممکن است Base متفاوت داشته باشند؛ هویت تجاری مشترک به Base هر طرف جدا تبدیل می‌شود. DTO اطلاعات دفتر/انبار خصوصی اضافه نمی‌کند.
- بستهٔ مرکب Marketplace چند Item است و با یک تبدیل واحد کالا یکی نیست؛ component mapping و conversion هر کالا جدا حفظ می‌شوند.
- feature بازار سازمانی در تمام این کار خاموش می‌ماند؛ این درخواست مجوز فعال‌سازی یا استقرار نیست.

## فایل‌ها و ترتیب اجرای پیشنهادی

1. مدل/مهاجرت: inventory، invoices، transfers، returns، issue_returns، advanced_inventory، manufacturing، marketplace، enterprise_market_bridge و migration 0189.
2. schemas همین دامنه‌ها؛ units service؛ inventory، warehouse_receipts/issues، transfers، returns/issue_returns، manufacturing، pricing، sales_review، marketplace و enterprise_market_*؛ مسیر backup/restore و import برای دادهٔ جدید نیز بررسی و تطبیق داده می‌شود.
3. API مدیریت واحد کالا/قاعده/override و preview با permission موجود؛ endpoint preview جای اعتبارسنجی posting را نمی‌گیرد.
4. frontend: ProductsPanel/UnitsPanel، فرم و draft خرید/فروش/برگشت/انتقال، رسید/حواله، PosPage، ManufacturingPage، صفحات بازار، api.ts و راهنمای موجود. دسکتاپ و وب و نمای باریک مشترک‌اند.
5. مستندات: OPEN_DECISIONS بند ۲۹، PROJECT_OVERVIEW §۱۰، DEPLOY_NOTES و این گزارش/گزارش نهایی.
6. commit backend/data و frontend جدا طبق راهبرد درخواست. PR پس از راستی‌آزمایی؛ merge/deploy توسط کاربر و پس از هماهنگی تازه، نه هماهنگی انتشار قبلی.

## راستی‌آزمایی لازم

- موتور: fixed/reverse، زنجیرهٔ سه/چهار واحد، اعشار، variable، transaction/batch override، self، مسیر گم‌شده، factor صفر/منفی، چرخه/مسیر ناسازگار و rounding.
- integration: خرید 36kg=150m و بها بر 150؛ فروش 2carton=48unit از 100؛ انتقال 72 در هر دو سمت؛ برگشت 24 با تغییر rule؛ دو Batch با نسبت 3.8/4.1؛ تولید 100 محصول با مصرف 150m؛ بازار 5carton=120unit.
- tenant/permission، غیرفعال‌شدن rule، Base change guard، concurrency و idempotency، void و برگشت جزئی با residual، گزارش/چاپ/مؤدیان و قیمت واحد مستقل.
- preload graph همهٔ کالاهای سند با query گروهی؛ benchmark چندصد line و شمارش query قبل از افزودن cache. هنوز benchmark اجرا نشده است.
- upgrade/downgrade/upgrade واقعی روی PostgreSQL مستقل موقت با fixture legacy دو tenant و RLS؛ compare_metadata، یک head و ثابت‌ماندن DB واقعی.
- کل backend یک اجرای pytest در هر زمان؛ frontend regression/typecheck/build/audit، و QA نمای desktop و ≤760px. مشاهدهٔ واقعی رابط مستقل از unit test گزارش می‌شود.

## وضعیت تحویل این ممیزی

فقط خواندن کد و تهیهٔ طرح انجام شد. آزمون جدید، benchmark، migration و implementation انجام نشده‌اند. گزارش نهایی بند ۹۱ پس از اجرای واقعی باید به‌روزرسانی شود؛ جدول وضعیت فعلی، ادعای تکمیل INV-02 نیست.


## تکمیل پیاده‌سازی INV-02 — 2026-10-04

قرارداد نسخه‌دار عرضه، بایگانی خصوصی snapshot فروشنده، مرجوعی همان قرارداد، قیمت مستقل واحد تجاری و مصرف اتمیک رزرو سفارش تکمیل شدند. رابط انتخاب واحد عرضه و اندازه‌گیری واقعی، مقادیر رشته‌ای هشت‌رقمی و نمایش واحد تاریخی دارد. موتور واحد مشترک تنها مرجع تبدیل است. گزارش کامل و شواهد نهایی در [INV02_FINAL_REPORT.md](INV02_FINAL_REPORT.md) است؛ ورودی‌های قبلی این سند checkpoint تاریخی‌اند. نسخهٔ عملیاتی، DB واقعی و نصاب منتشرشده تغییر نکرده‌اند.
