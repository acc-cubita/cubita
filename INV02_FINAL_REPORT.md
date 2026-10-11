# INV-02 — Final Implementation Report

وضعیت 2026-10-04: پیاده‌سازی روی شاخهٔ توسعه تکمیل؛ منتشر یا روی دادهٔ واقعی مهاجرت نشده است. این گزارش جایگزین وضعیت «کارهای باقی» در checkpointهای پیشین است.


الحاق وضعیت انتشار2026-10-06: کد ونسخه درPR265/266 ادغام؛ production0189 وکانال امضاشدهٔ۱.۹.۱۲ منتشر وراستی‌آزمایی شدند. شرح نهایی در[INV02_RELEASE_1_9_12.md](INV02_RELEASE_1_9_12.md) است؛ بخش‌های زیر شواهد تاریخی پیاده‌سازی2026-10-04 هستند. ارتقای محلی واقعی وGUI/دو نصب مستقل هنوز آزموده نشده‌اند.

## Current HEAD

Implementation HEAD: `79dd52c21cb700650e97f7bd5fa8e7ba7b62c72e`. Backend final: a0866dc؛ UI final: 79dd52c. گزارش و مستندات یک commit بعد از این HEAD دارند؛ HEAD واقعی تحویل را با git rev-parse HEAD ببینید.

## Current Unit Architecture Before

کالا یک واحد اصلی/فرعی و ضریب ثابت یا متغیر داشت. مسیرهای سند و بازار مقدار تجاری و پایه را یکسان فرض می‌کردند؛ بازسازی تاریخ با ضریب زنده، مقادیر شناور رابط و جمع واحدهای ناهمگون قابل اتکا نبودند. ممیزی پیش از پیاده‌سازی: INV02_AUDIT.md.

## Database Design

مهاجرت منتشرنشدهٔ 0189 پشت 0188: item_units، item_unit_conversions و batch_unit_conversions با FORCE RLS و FK مرکب شرکت/کالا. واحد پایهٔ کالا NOT NULL و عضو همان کالا با قید deferred است. 44 ستون مقدار به Numeric(24,8)، نسبت به Numeric(30,12)، و اسناد به مقدار واردشده/پایه و JSON snapshot مجهز شدند. دادهٔ قدیمی فقط base تاریخی و original_input_known=false می‌گیرد؛ نسبت ساختگی ندارد. restore پیش از حذف داده رجیستری قدیمی را نرمال/اعتبارسنجی می‌کند. قراردادهای خصوصی بازار در نگاشت موجود شرکت با GIN ذخیره می‌شوند.

## Conversion Engine

services/units.py تنها مرجع محاسبهٔ تبدیل است. دامنه‌ها convert_transaction، document_conversion، historical_return_conversion، convert_frozen_quantity و scale_document_conversion را مصرف می‌کنند. market_units تطبیق قرارداد/ردیف را انجام می‌دهد و محاسبهٔ نسبت را به موتور مشترک واگذار می‌کند. Decimal ورودی و Fraction نسبت/مسیر، بدون binary float؛ رجیستری در هر عملیات bulk بارگیری می‌شود.

## Fixed Conversion

قاعدهٔ ثابت کالامحور، تبدیل مستقیم و معکوس و کنترل عضویت/اجازهٔ کاربرد. مثال 2 کارتن با ضریب 24، موجودی 48 عدد؛ ویرایش بعدی ضریب به 100 سند قبلی را عوض نمی‌کند.

## Multi-stage Conversion

گراف مسیر چندمرحله‌ای و معکوس با BFS؛ کنترل تعارض مسیر/چرخه. مثال پالت → کارتن → بسته → عدد، 1 پالت = 2880 عدد. گردکردن در انتهای تبدیل انجام می‌شود.

## Variable Conversion

اندازه‌گیری واقعی با مقدار خام دو طرف؛ تقدم مشاهدهٔ تراکنش بر بچ و سپس کالا. نسبت صرفاً از مشاهدهٔ پذیرفته‌شده محاسبه می‌شود؛ بدون مشاهده، تبدیل متغیر مسدود است. مثال 36 کیلوگرم = 150 متر؛ سفارش 36 واحد عرضه دقیقاً 150 متر را رزرو/مصرف می‌کند. هر طرف بازار اندازه‌گیری خصوصی مستقل دارد.

## Snapshot

نام/شناسهٔ واحدها، مقدار اصلی و پایه، نسبت دقیق، مسیر/نسخه، اندازه‌گیری خام و اجازهٔ اعشار فریز می‌شوند. برگشت، خروج جزئی، ابطال و تولید از تاریخ ثبت‌شده استفاده می‌کنند. آخرین برگشت/مصرف جزئی ته‌ماندهٔ گردکردن را می‌بندد؛ تغییر نام/ضریب تاریخ را بازنویسی نمی‌کند.

## Purchase Integration

خرید و رسید مقدار تجاری، قیمت همان واحد و مقدار پایهٔ مستقل دارند. رونوشت واحد/مقدار را نگه می‌دارد ولی snapshot جدید می‌سازد. خرید 2.00000001 کارتن در ضریب 24 سپس رونوشت با ضریب 30، دو پایهٔ تاریخی متفاوت و صحیح دارد. برگشت به سند اصلی لنگر می‌شود.

## Sales Integration

فروش، پیش‌فاکتور، خروج جزئی، برگشت و ابطال از موتور مشترک و snapshot استفاده می‌کنند. مقایسهٔ تحقق/مانده در واحد پایه است؛ مبلغ از مقدار تجاری و قیمت تجاری می‌آید. در جزئیات فاکتور نام واحد تاریخی و مقدار کامل نمایش داده می‌شود.

## POS Integration

واحد و نسبت واقعی از TransactionUnitPicker؛ ورودی رشته‌ای، افزایش/کاهش BigInt، پیش‌نمایش موجودی پایه و رسید با واحد انتخابی. قیمت مستقل واحد لازم است؛ پاسخ قیمت قدیمی به انتخاب تازه اعمال نمی‌شود. پرداخت نقدی/کارتی واحد و observations را می‌فرستند.

## Inventory Integration

رسید/خروج مستقیم، انتقال، تعدیل و برگشت رسید/خروج روی مقدار پایه ثبت می‌شوند؛ رابط مقدار تجاری و مشاهده را می‌گیرد. کارتکس snapshot مقدار اصلی و پایه را نمایش می‌دهد. رزرو خود سفارش بازار پیش از خروج در همان تراکنش مصرف می‌شود؛ خطا فاکتور و رزرو را با هم rollback می‌کند.

## Batch Integration

نسبت واقعی و snapshot بچ نگهداری می‌شوند؛ FEFO دقیق، تخصیص مشترک ردیف‌های تکراری و کنترل مانده از بیش‌مصرف جلوگیری می‌کنند. قیمت پیشنهادی کارتن/کیلوگرم به قیمت واحد پایهٔ بچ تعبیر نمی‌شود.

## Marketplace Integration

عرضهٔ تکی/بسته واحد هر جزء و مقدار تجاری انتخابی دارد. هنگام انتشار، snapshot خصوصی فروشنده با مرجع تصادفی نسخه‌دار بایگانی می‌شود. DTO عمومی فقط نام/مقدار تجاری و trade_contract نسخه 1/مرجع UUID دارد؛ واحد محلی، نسبت خصوصی، مشاهده و سند محلی خارج نمی‌شوند. آرشیو پیش از ارسال شبکه commit می‌شود. تغییر عرضه، ضریب یا نام سفارش قبلی را تغییر نمی‌دهد؛ قرارداد ناشناخته مسدود است. حذف نگاشت دارای تاریخ مجاز نیست.

دو عرضهٔ یک کالا با قراردادهای 24 و 30، مجموع 54 عدد می‌فروشند؛ برگشت فقط قرارداد اول 24 عدد است. خریدار و فروشنده پایهٔ خصوصی مستقل دارند. ثبت/بازپخش رویداد مالی exact-once است. quantity_inputs خصوصی رویداد با مجوز و tenant بررسی می‌شود و به ابر ارسال نمی‌شود. قیمت پیشنهادی در snapshot همان ردیف و همان واحد تجاری حفظ می‌شود؛ ترتیب تصادفی UUID ردیف‌ها قرارداد/قیمت را جابه‌جا نمی‌کند.

## Production Integration

BOM واحد بازده/مواد و snapshot؛ سفارش تولید recipe مستقل از ویرایش بعدی BOM؛ اجرای مستقیم، تحویل مواد، رسید محصول و تولید جزئی از همان تبدیل تاریخی استفاده می‌کنند. ته‌ماندهٔ گردکردن در مصرف نهایی بسته می‌شود؛ فرمول قدیمی مبهم نیاز به بررسی دستی دارد. مثال 100 محصول × 1.5 متر با 36 کیلو=150 متر، موجودی پارچه صفر و بهای واحد محصول 180 شد.

## Pricing Integration

قیمت به واحد/مشتری/زمینهٔ فروش حل می‌شود. واحد جایگزین بدون قیمت مستقل خودکار از ضریب قیمت نمی‌سازد. قیمت بازار با واحد تجاری اصلی بایگانی می‌شود؛ consumer_price بچ فقط برای معامله در پایه و قیمت یکتای قابل اتکا ثبت می‌شود.

## Valuation Integration

گردش و ارزش موجودی در مقدار پایه؛ مبلغ تجاری مستقل است. بهای جزئیات فاکتور از base_qty × unit_cost محاسبه می‌شود. حساب‌ها و سیاست مالی/پولی موجود عوض نشده‌اند؛ تبدیل واحد سیاست گردکردن پول تازه ایجاد نمی‌کند.

## Reports

گزارش فروش/اقلام/مشتری/سند/انبار و داشبورد بر مقدار پایهٔ تاریخی تکیه دارند. quantity_totals به تفکیک واحد است؛ scalar جمع ناهم‌واحد null و رابط تفکیک را نشان می‌دهد. واحد قدیمی نامعلوم از معلوم جدا می‌ماند. چاپ/نمایش مقدار اصلی هشت‌رقمی و نام تاریخی را نگه می‌دارند.

## Precision / Rounding

مقدار 24 رقم/8 اعشار؛ نسبت 30 رقم/12 اعشار و Fraction در محاسبه. HALF_UP در مرز نهایی موجودی. مقدار نامتناهی، float نامعتبر، دقت اضافی و مقدار خارج ظرفیت رد می‌شوند. رشته/BigInt در رابط مانع افت دقت مقدار بزرگ 1234567890123456.12345678 است. اجازهٔ اعشار تاریخی در عرضه و برگشت حفظ می‌شود.

## Validation

کنترل واحد فعال/عضویت/کاربرد، ضریب مثبت، مسیر یکتا و سازگار، اندازه‌گیری لازم، موجودی و بچ، مرجوعی بیش از مانده، tenant و مجوز. downgrade با افت دقت، تاریخ عملیاتی تازه، اندازه‌گیری خصوصی یا قرارداد عرضهٔ ذخیره‌شده رد می‌شود. مهاجرت round-trip و منع افت دقت/حذف اندازه‌گیری روی اسکیمای یک‌بارمصرف مستقل آزموده شد. سه جدول رجیستری FORCE RLS؛ metadata مرتبط صفر اختلاف؛ backfill دو شرکت و 44 ستون مقدار کنترل شدند. شاخه هیچ DB واقعی را تغییر نداده است.

## Performance

بارگیری رجیستری عملیات 1000 کالا: حدود 5000 SELECT /3.9s به 3 SELECT /0.4s کاهش یافت؛ cache جهانی و نسبت کهنه وجود ندارد. بایگانی بازار فقط با مرجع قرارداد و GIN و محدودهٔ tenant خوانده می‌شود. ظرفیت عرضه با Fraction پیش از floor سیاست بسته محاسبه می‌شود.

## Tests

- Backend کامل در checkpoint پیش از اصلاحات نهایی بازار: 4354 passed، 1 skipped (566.68s).
- پس از تمام تغییرات نهایی: 269 passed، 4090 deselected (71.06s) در مجموعهٔ بازار/پل/موتور/اسناد/restore؛ این اجرا جای اجرای کامل مجدد پس از تغییرات نهایی معرفی نمی‌شود.
- آزمون skipped نصب واقعی PostgreSQL جداگانه با PG17 و cluster موقت: 1 passed (49.18s)، provision/migration/rollback/reprovision.
- Frontend نهایی: 1074 passed /136 files (28.85s).
- TypeScript، build وب و Electron موفق؛ ممیز 110 صفحه/188 جزء/3 CSS صفر خطا و هشدار؛ lint خطای تازه ندارد (هشدارهای موجود ثبت شدند).
- آزمون مرورگر fixture با ListingWizard/TransactionUnitPicker و CSS واقعی در عرض 1440 و390: بدون خطای JavaScript و overflow؛ screenshots بصری بررسی شدند. این آزمون نصب واقعی کاربر نیست.
- DB تست مستقل 127.0.0.1:55438؛ هیچ pytest روی5432/5433 اجرا نشد. probe مهاجرت اسکیمای خود را پاک کرد.

## Files Changed

فهرست کامل نسبت به origin/master در زمان گزارش، شامل کد، آزمون و مستندات:

- `AGENT_CLAIMS.md`
- `DEPLOY_NOTES.md`
- `INV02_AUDIT.md`
- `INV02_FINAL_REPORT.md`
- `INV02_PROGRESS.md`
- `MARKET_LIVE_QA.md`
- `OPEN_DECISIONS.md`
- `PROJECT_OVERVIEW.md`
- `backend/alembic/versions/0189_item_unit_registry.py`
- `backend/app/audit.py`
- `backend/app/models/__init__.py`
- `backend/app/models/advanced_inventory.py`
- `backend/app/models/batch_substitutions.py`
- `backend/app/models/enterprise_market_bridge.py`
- `backend/app/models/inventory.py`
- `backend/app/models/inventory_valuation.py`
- `backend/app/models/invoices.py`
- `backend/app/models/issue_returns.py`
- `backend/app/models/item_units.py`
- `backend/app/models/manufacturing.py`
- `backend/app/models/marketplace.py`
- `backend/app/models/marketplace_allocations.py`
- `backend/app/models/quantity_snapshot.py`
- `backend/app/models/quotations.py`
- `backend/app/models/returns.py`
- `backend/app/models/sales_ops.py`
- `backend/app/models/stock_count.py`
- `backend/app/models/stock_reservations.py`
- `backend/app/models/storefront_native.py`
- `backend/app/models/transfers.py`
- `backend/app/routers/backup.py`
- `backend/app/routers/enterprise_market_local.py`
- `backend/app/routers/inventory.py`
- `backend/app/routers/invoices.py`
- `backend/app/routers/manufacturing.py`
- `backend/app/schemas/enterprise_market_bridge.py`
- `backend/app/schemas/inventory.py`
- `backend/app/schemas/invoices.py`
- `backend/app/schemas/issue_returns.py`
- `backend/app/schemas/item_units.py`
- `backend/app/schemas/manufacturing.py`
- `backend/app/schemas/marketplace.py`
- `backend/app/schemas/quotations.py`
- `backend/app/schemas/reports.py`
- `backend/app/schemas/returns.py`
- `backend/app/schemas/transfers.py`
- `backend/app/services/batches.py`
- `backend/app/services/enterprise_market_catalog.py`
- `backend/app/services/enterprise_market_orders.py`
- `backend/app/services/enterprise_market_posting.py`
- `backend/app/services/inventory.py`
- `backend/app/services/issue_returns.py`
- `backend/app/services/manufacturing.py`
- `backend/app/services/market_units.py`
- `backend/app/services/marketplace.py`
- `backend/app/services/pricing.py`
- `backend/app/services/printing.py`
- `backend/app/services/production_reports.py`
- `backend/app/services/quotations.py`
- `backend/app/services/reports.py`
- `backend/app/services/returns.py`
- `backend/app/services/sales_invoices.py`
- `backend/app/services/sales_review.py`
- `backend/app/services/transfers.py`
- `backend/app/services/units.py`
- `backend/app/services/valuation.py`
- `backend/app/services/voiding.py`
- `backend/app/services/warehouse_issues.py`
- `backend/app/services/warehouse_receipts.py`
- `backend/app/tenant_context.py`
- `backend/tests/test_audit_log.py`
- `backend/tests/test_backup.py`
- `backend/tests/test_enterprise_market_financial_flow.py`
- `backend/tests/test_enterprise_market_posting.py`
- `backend/tests/test_item_unit_registry.py`
- `backend/tests/test_market_unit_contracts.py`
- `backend/tests/test_pricing_matrix.py`
- `backend/tests/test_printing.py`
- `backend/tests/test_sales_dashboard.py`
- `backend/tests/test_sales_review.py`
- `backend/tests/test_unit_conversion_graph.py`
- `backend/tests/test_unit_conversion_queries.py`
- `backend/tests/test_unit_document_snapshots.py`
- `desktop/src/api.ts`
- `desktop/src/components/BatchAllocationPicker.tsx`
- `desktop/src/components/EnterpriseMarketStatus.test.tsx`
- `desktop/src/components/EnterpriseMarketStatus.tsx`
- `desktop/src/components/InvoiceList.tsx`
- `desktop/src/components/IssueReturnsTab.tsx`
- `desktop/src/components/ItemUnitsEditor.test.tsx`
- `desktop/src/components/ItemUnitsEditor.tsx`
- `desktop/src/components/KardexTable.tsx`
- `desktop/src/components/MpDistributorReturns.tsx`
- `desktop/src/components/MpRetailerReturns.tsx`
- `desktop/src/components/PosReceipt.tsx`
- `desktop/src/components/ProductsPanel.tsx`
- `desktop/src/components/PurchaseInvoiceForm.tsx`
- `desktop/src/components/QuotationForm.tsx`
- `desktop/src/components/SalesInvoiceForm.tsx`
- `desktop/src/components/SalesReturnForm.tsx`
- `desktop/src/components/StockAdjustmentForm.tsx`
- `desktop/src/components/TransactionUnitPicker.test.tsx`
- `desktop/src/components/TransactionUnitPicker.tsx`
- `desktop/src/components/TransferForm.tsx`
- `desktop/src/components/WarehouseIssuesTab.tsx`
- `desktop/src/components/WarehouseReceiptsTab.tsx`
- `desktop/src/components/wizard/ListingWizard.tsx`
- `desktop/src/components/wizard/PurchaseInvoiceWizard.tsx`
- `desktop/src/components/wizard/PurchaseReturnWizard.tsx`
- `desktop/src/components/wizard/QuotationWizard.tsx`
- `desktop/src/components/wizard/SalesInvoiceWizard.tsx`
- `desktop/src/components/wizard/SalesReturnWizard.tsx`
- `desktop/src/components/wizard/StockAdjustmentWizard.tsx`
- `desktop/src/components/wizard/TransferWizard.tsx`
- `desktop/src/lib/batchAllocation.test.ts`
- `desktop/src/lib/batchAllocation.ts`
- `desktop/src/lib/listingDraft.test.tsx`
- `desktop/src/lib/listingDraft.ts`
- `desktop/src/lib/purchaseInvoiceDraft.ts`
- `desktop/src/lib/purchaseReturnDraft.ts`
- `desktop/src/lib/quantityDisplay.test.ts`
- `desktop/src/lib/quantityDisplay.ts`
- `desktop/src/lib/quotationDraft.ts`
- `desktop/src/lib/returnQuantity.test.ts`
- `desktop/src/lib/returnQuantity.ts`
- `desktop/src/lib/salesInvoiceDraft.ts`
- `desktop/src/lib/salesQuantityDisplay.test.ts`
- `desktop/src/lib/salesQuantityDisplay.ts`
- `desktop/src/lib/salesReturnDraft.ts`
- `desktop/src/lib/stockAdjustmentDraft.ts`
- `desktop/src/lib/transferDraft.ts`
- `desktop/src/pages/DistributorPage.tsx`
- `desktop/src/pages/ManufacturingPage.tsx`
- `desktop/src/pages/MarketplacePage.tsx`
- `desktop/src/pages/PosPage.test.tsx`
- `desktop/src/pages/PosPage.tsx`
- `desktop/src/pages/sales/SalesOpsPages.tsx`

## Remaining Gaps

شکاف شناخته‌شدهٔ پیاده‌سازی در دامنه‌های این فصل باقی نمانده است. باقی‌ماندهٔ تحویل عملیاتی: بررسی PR/CI، تعیین نسخه و ساخت نصاب انتشار، آزمون GUI نصب واقعی و سناریوی دو نصب سازمانی مستقل، سپس استقرار با هماهنگی کاربر و آرش. هیچ‌یک انجام‌شده فرض نشده‌اند. تاریخ قدیمیِ بدون واحد/مشاهده قابل بازسازی قطعی نیست؛ عمداً مجهول حفظ شده و برای تولید جزئی مبهم بررسی دستی لازم است. محدودیت موجود restore کالاهای دارای ارجاع broker حفظ شده است.

## Git

شاخه feat/inv02-multi-uom؛ پایه origin/master=8710633 (PR264). تغییر backend و UI در commitهای جدا ثبت شدند. PR به صورت Draft آماده می‌شود؛ master ادغام و production مستقر نشده‌اند. شمارهٔ مهاجرت0189 هنوز منتشر نشده؛ شمارهٔ بعدی0190 است. نصب فعلی1.9.11 با این شاخه یکسان فرض نمی‌شود.
