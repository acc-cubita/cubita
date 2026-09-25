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

> **حادثه‌ی «دو سرِ زنجیره» — بسته شد (۱۴۰۵/۰۶/۲۴).**
>
> تنخواه `0151` گرفت و پیمانکاری هم `0152` را پشتِ `0150` گذاشت: **دو سر روی یک
> ریشه.** اصلاحش (#81) تاریخچه را بازنویسی کرد و merge‌ی PR #76 را انداخت — پس
> صندوقِ تنخواه و «هدف حرکت» از `master` غایب شدند بی‌آنکه کسی متوجه شود، چون
> GitHub همچنان «merged» نشانشان می‌داد. با PR #87 و شماره‌ی `0157` برگشتند و
> تولید روی `0157` مستقر شد.
>
> **درسِ عملی:** پیش از هر مهاجرت، شماره را از **سرِ فعلیِ `master`** بگیر
> (`alembic heads` یا پیمودنِ زنجیره)، نه از آخرین چیزی که خودت دیده‌ای. و اگر
> اصلاحی تاریخچه را بازنویسی کرد، **بسنج کدام merge‌ها افتاده‌اند** — «merged»
> بودن در GitHub تضمین نمی‌کند کامیت روی `master` است.

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
| Claude Code (آرش) | `pages/accounting/RecurringPage.tsx` (تازه) و تستش، `components/RecurringEntriesPanel.tsx` (حذف)، `AccountingListPages.tsx`، `lib/recurringSheet.ts` (تازه) و تستش، `JalaliDatePicker.tsx`، `App.css`، `HelpPage.tsx` | «اسناد تکرارشونده» با تمِ اکسلیِ سند حسابداری | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `lib/navModel.tsx`، `moduleLists.tsx`، `ModulePanels.tsx`، `TopNav.tsx`، `Sidebar.tsx`، `Dashboard.tsx`، `AccountTreePanel.tsx` و تستش، `pages/accounting/*`، `ModuleListPages.tsx`، `CompanyOpsPages.tsx`، `FiscalYearPage.tsx`، `HelpPage.tsx`، `lib/reportCatalog.ts`، `App.css`، سه پیامِ بک‌اند، تست‌های ناوبری | بازچینیِ منوهای حسابداری: ادغامِ تکراری‌ها، شش دسته، نام‌های روشن | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `.claude/skills/cubita-excel-theme/SKILL.md` (تازه)، `CLAUDE.md`، `PROJECT_OVERVIEW.md` | ثبتِ روشِ بازسازیِ صفحه‌ها با تمِ اکسلیِ سند حسابداری | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `FxRevaluationPage.tsx` (تازه) و تستش، `ClosingPages.tsx`، `DocFooter.tsx` (تازه)، `BalanceFooter.tsx`، `SheetFooter.tsx`، `CurrenciesPanel.tsx` و تستش، `lib/currencySheet.ts` و تستش، `App.css` | «صدور سند تسعیر ارز» و «ارزها/نرخ برابری» با تمِ سند حسابداری؛ پایه‌ی مشترکِ نوارِ پایین؛ تقویم بالای نوار | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `AnalyticsPage.tsx` (تازه) و تستش، `ChartPages.tsx`، `SheetFooter.tsx`، `FitText.tsx`، `BalanceFooter.tsx`، `lib/analyticsSheet.ts` و تستش، `lib/useSheetNav.ts`، `HelpPage.tsx`، `App.css` | «تفصیلی سایر» به برگه‌ی اکسلیِ ویرایشِ درجا | ۱۴۰۵/۰۷/۰۲ |
| Claude Code (آرش) | `OpeningBalancePage.tsx` و تستش، `BalanceFooter.tsx` (تازه)، `lib/balanceState.ts`، `lib/useSheetNav.ts` (تازه)، `lib/alignToGrid.ts`، `lib/journalGridNav.ts`، `AccountCombo.tsx`، `JournalEntryForm.tsx`، `App.css` | «مانده اول دوره» با تمِ اکسلیِ سند حسابداری | ۱۴۰۵/۰۷/۰۲ |
| Claude Code (آرش) | `JournalEntryForm.tsx`، `App.css`، `lib/alignToGrid.ts`، `lib/useColumnWidths.ts`، `JournalGrid.tsx`، `JournalPages.tsx` و تست‌ها | سربرگ و نوارِ پایینِ سند ستون‌به‌ستون با گریدِ اکسلی؛ کفِ زمانِ نمایشِ ستونِ «حساب» | ۱۴۰۵/۰۷/۰۲ |
| Claude Code (آرش) | `lib/useColumnWidths.ts`، `JournalGrid.tsx`، `JournalPages.tsx`، `App.css` و تستش | جدولِ اکسلی: «جا در قاب» — ستون‌های ثابت، بی اسکرولِ افقی، کشیدن میانِ دو هم‌سایه | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `lib/useColumnWidths.ts`، `JournalGrid.tsx`، `JournalPages.tsx`، `App.css` و تستش | جدولِ اکسلی: جدول باریک‌تر از قاب نمی‌شود؛ ستونِ آخر جای خالی را می‌گیرد | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `routers/journal.py`، `JournalGrid.tsx`، `JournalEntryForm.tsx`، `XlGrid.tsx`، `lib/rowSelection.ts`، `lib/useColumnWidths.ts`، `lib/useDebounced.ts`، `lib/journalLineOps.ts`، `JournalPages.tsx`، `api.ts`، `ShortcutsPage.tsx`، `App.css` و تست‌ها | جدولِ اکسل‌مانند: گریدِ ثبتِ سند + فهرستِ اسناد | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `ModulePanels.tsx`، `lib/menuOrder.ts` (تازه)، `ShortcutsPage.tsx`، `App.css` (`.mod-op-*`) و تست‌ها | کارت‌های «عملیات» و «فهرست»: جابه‌جاییِ منوها با فلش و Alt+↑/↓ | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `JournalEntryForm.tsx`، `lib/useFitText.ts` (تازه)، `App.css` (`.jb-*`) | ثبتِ سند: خانه‌های ثابتِ جمع/توازن؛ عددِ بلند کوچک می‌شود نه خانه | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `JournalGrid.tsx`، `JournalEntryForm.tsx`، `AccountCombo.tsx` (تازه)، `lib/gridPicker.ts`، `ShortcutsPage.tsx`، `App.css`، `e2e/accountant-journal.e2e.mjs` و تست‌ها | ثبتِ سند: فوترِ نهایی، پنجره‌ی میان‌برها، عرضِ ستون‌ها، جست‌وجوی درجای حساب، Enter از حساب به مبلغ | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `JournalEntryForm.tsx`، `JournalEntryForm.footer.test.tsx` (تازه)، `ShortcutsPage.tsx`، `App.css` (`.jf-*`/`.jb-*`/`.jg-keys`/`.jg-actions`) | ثبتِ سند: نوارِ پایانیِ شناور، راهنمای تاشو (Ctrl+/)، کنش‌های ردیف روی hover | ۱۴۰۵/۰۷/۰۳ |
| Claude Code (آرش) | `JournalEntryForm.tsx`، `JournalGrid.tsx`، `SearchSelect.tsx`، `lib/journalGridNav.ts`، `lib/faText.ts`، `lib/gridPicker.ts` (تازه)، `ShortcutsPage.tsx`، `App.css` (`.jh-*`/`.jb-*`/`.jg-legend`) و تست‌ها | ارگونومیِ ثبتِ سند: سربرگِ فشرده، نوارِ توازن، Tab/←→/F2/F4، راهنمای میان‌بر، رتبه‌بندیِ جست‌وجو | ۱۴۰۵/۰۷/۰۳ |
| Claude Code | `desktop/src/lib/tenantScope.ts`، `App.tsx`، `AccountBrowser.tsx`، `descriptionMemory.ts` و تست‌هایشان، `PROJECT_OVERVIEW.md` | کلیدِ `sessionStorage` به‌ازای کسب‌وکار (باگِ بازبینیِ #191) | ۱۴۰۵/۰۷/۰۲ |
| Claude Code | `backend/app/routers/journal.py`، `backend/app/schemas/accounting.py`، `backend/tests/test_journal_list_filters.py`، `desktop/src/api.ts`، `desktop/src/pages/accounting/ReportPages.tsx`، `Daybook.test.tsx`، `App.css`، `PROJECT_OVERVIEW.md`؛ پایگاه‌داده‌ی یک‌بارمصرفِ `cubita_verify` (حذف شد) | دفتر روزنامه: صفحه‌بندیِ سرور، جمعِ `/summary`، فیلترهای مشترک، برچسبِ جست‌وجو | ۱۴۰۵/۰۷/۰۲ |
| Claude Code | `services/accounting_ops.py` (`get_balance_tree`)، `services/reports.py` (`get_general_ledger`: `limit/offset`)، دو روتر و دو شِما، `AccountBrowser.tsx` (تازه)، `lib/accountTree.ts` (تازه)، `ChartPages.tsx`، `Dashboard.tsx`، `api.ts`، `App.css`، `HelpPage.tsx`، `e2e/account-browser.e2e.mjs`، `ci.yml` | UI-02 مرور حسابِ حرفه‌ای: درختِ تجمیعیِ سمتِ سرور، گردشِ صفحه‌بندی‌شده، کیبورد، جست‌وجو، حفظِ زمینه — بی‌مهاجرت | ۱۴۰۵/۰۷/۰۲ |
| Claude Code | `.github/workflows/ci.yml`، `PROJECT_OVERVIEW.md` | گروهِ concurrency روی `master` به‌ازای sha؛ مرجِ بعدی دیگر CIِ قبلی را لغو نمی‌کند (✗ ۲/۴ روی #۱۷۴–#۱۷۶) | ۱۴۰۵/۰۷/۰۲ |
| Claude Code | `desktop/e2e/accountant-journal.e2e.mjs`، `PROJECT_OVERVIEW.md`؛ اسکیمای یک‌بارمصرفِ `cubita_verify` (حذف شد) | رفعِ ناپایداریِ E2E (فوکوسِ کادرِ جست‌وجو) که CIِ مرجِ M2ِ آرش را قرمز کرد؛ بررسیِ اینکه UI-01 چیزی از M1/M2 نشکسته | ۱۴۰۵/۰۷/۰۲ |
| Claude Code | `routers/journal.py`، `main.py`، `test_journal_line_error_contract.py`، `desktop/package.json`، `PROJECT_OVERVIEW.md` | خطای ردیفیِ سند raise می‌شود تا تراکنش rollback شود (handlerِ `{detail, line_errors}` در main.py)؛ نسخه‌ی دسکتاپ ۱.۷.۰. بک‌اند ۳۸۷۳، فرانت ۴۲۱ | ۱۴۰۵/۰۷/۰۲ |
| Codex | قرارداد خطای ردیفی journal، نمایش ردیف در دسکتاپ، سنجه و بهینه‌سازی گرید ۳۰۰ ردیفی، نصاب ۱٫۶٫۱ | تکمیل UI-01 روی master به‌روز؛ ۹۳ تست بک‌اند و ۴۲۱ تست دسکتاپ پاس؛ نصاب محلی ساخته شد | ۱۴۰۵/۰۷/۰۲ |
| Claude Opus 5 | مهاجرت‌های `0177`–`0179`، `models/assurance.py`، `services/assurance.py`/`assurance_access.py`/`assurance_score.py`/`assurance_checks.py`، `routers/assurance.py`/`admin_assurance.py`، `services/modules.py` (ماژولِ مشتق)، `deps.py`، `routers/auth.py`، `services/members.py`، `models/tenant.py` (`expires_at`)، `models/user.py` (نقشِ `auditor`)، `services/integrity.py` (خانواده‌بندی)، `pages/assurance/*`، `pages/AssuranceAdminPage.tsx`، `navModel.tsx`، `moduleLists.tsx` | ماژولِ حسابرسی فازِ ۱: درخواستِ مشتری، تأییدِ ستاد، گیتِ زیرمنوها با ماژولِ مشتق، دسترسیِ موقتِ فقط‌خواندنیِ حسابرس، و دوازده بررسیِ خودکار با نمره‌ی سلامت و snapshot | ۱۴۰۵/۰۶/۲۹ |
| Claude Opus 5 | مهاجرت `0163`، `models/assets.py` (`AssetAssignment` + سه ستونِ استقرار)، `schemas/assets.py`، `services/assets.py`، `routers/assets.py`، `FixedAssetsPanel.tsx` (تب‌دار شد)، `wizard/FixedAssetWizard.tsx`، `Dashboard.tsx`، `moduleSections.tsx`، `api.ts` | دارایی ثابت، فازِ ۱: تحویل/استقرار و جابه‌جایی با تاریخچه‌ی دوسره؛ ماژول از صفحه‌ی تخت به پنج تب رفت و ویزارد داخلِ تبِ اول با درفتِ مشترک نشست | ۱۴۰۵/۰۶/۲۵ |
| Claude Opus 5 | مهاجرت `0162`، `services/production_reports.py` (تازه)، `schemas/manufacturing.py`، `routers/manufacturing.py`، `models/manufacturing.py`، `services/manufacturing.py`، `ManufacturingPage.tsx`، `moduleSections.tsx`، `HelpPage.tsx`، `api.ts` | تولید، فازِ ۴: سه گزارشِ انحرافِ مصرفِ مواد، کاردکسِ خطِ تولید و قیمتِ تمام‌شده — مشتق از همان اسنادِ واقعی، بدونِ جدولِ گزارشیِ موازی؛ سندِ باطل‌شده شمرده نمی‌شود | ۱۴۰۵/۰۶/۲۵ |
| Claude Opus 5 | مهاجرت `0161`، `models/invoices.py` (نوعِ `production` در `ISSUE_TYPES` + دو ستونِ `production_plan_id`)، `models/manufacturing.py` (`material_cost_issued`)، `schemas/invoices.py`، `schemas/manufacturing.py`، `services/manufacturing.py`، `services/warehouse_issues.py`، `services/warehouse_receipts.py`، `routers/manufacturing.py`، `routers/warehouse_issues.py`، `ManufacturingPage.tsx` (بازنویسی به پنج تب)، حذفِ `ProductionCostDrawer.tsx`، `moduleSections.tsx`، `moduleLists.tsx`، `HelpPage.tsx`، `api.ts` | تولید، فازِ ۳: «تحویل مواد»، «رسید محصول» و «محاسبه قیمت تمام‌شده» به‌عنوانِ سه عملیاتِ واقعیِ جدا — روی موتورهای موجودِ حواله/رسیدِ انبار، نه موتورِ سوم. تبِ «سند تولید»ِ اتمی بازنشسته شد (موتور و دیتایش دست‌نخورده) | ۱۴۰۵/۰۶/۲۵ |
| Claude Sonnet 5 | مهاجرت `0160` (بک‌فیلِ داده، بدونِ تغییرِ اسکیما) | بک‌فیلِ `contracting` در `enabled_modules`ِ مستأجرهای شخصی‌سازی‌شده — کاربر گزارش داد ماژول را نمی‌بیند؛ ریشه یافت شد با کوئریِ read-only روی production (همان شکافِ الگوی `0073`) | ۱۴۰۵/۰۶/۲۵ |
| Claude Sonnet 5 | `desktop/src/pages/ManufacturingPage.tsx` (بدونِ مهاجرت/بک‌اند) | تولید، فازِ ۲: هشدارِ «جلوگیری از خروجِ مواد» — تبِ سند تولید، پیش از ثبت، چک می‌کند بعدِ این سند برای هر جزء چقدر می‌ماند در برابرِ چیزی که سفارش‌های بازِ *دیگر* (started/in_progress/stopped، همان انبار) رویش حساب کرده‌اند؛ فقط هشدار (تصمیمِ کاربر)، نه قفل. کاملاً سمتِ کلاینت از دادهٔ از قبل واکشی‌شده + `/api/stock`ِ موجود؛ صفر تغییرِ بک‌اند | ۱۴۰۵/۰۶/۲۵ |
| Claude Opus 5 | مهاجرت `0157` (پشتِ `0156`؛ اول `0151` بود)، `models/banking.py` (`PettyCashFund`)، `schemas/banking.py`، `services/banking.py`، `routers/banking.py`، `services/inventory_analytics.py`، `tests/test_inventory_reporting.py` | بازگردانیِ کارِ گم‌شده‌ی PR #76 + صندوقِ تنخواه با تنخواه‌دار/سقف/مدرک و استردادِ مانده + «هدف حرکت» که تولید را از خرید و مصرف را از فروش جدا می‌کند (از `receipt_type`/`issue_type`ِ خودِ سند، بی ستونِ تازه). یک FK بی‌پوششِ `rls_disabled` پیش از استقرار گرفته شد | ۱۴۰۵/۰۶/۲۴ |
| Claude Opus 5 | مهاجرت `0150`، `services/banking.py`، `models/banking.py`، `services/reports.py`، `services/chart_codes.py`، `seed.py`، `models/crm.py`، `ReconciliationPanel.tsx`، `ACCOUNTING_KB_AUDIT.md` (تازه)، `GAPS.md` | مقابله‌ی کد با پایگاه دانشِ حسابداری (۱۴۷ قسمت): کنترلِ تکرارِ وارداتِ صورت‌حسابِ بانکی · صورت جریان وجوه نقد روی **نقش** به‌جای متنِ کد + گروهِ ۲۲ که در چارتِ پایه نبود · تصحیحِ کامنتِ تومان/ریالِ امتیازِ باشگاه. دو ادعای `GAPS.md` در آزمون رد شدند و ثبت شدند | ۱۴۰۵/۰۶/۲۴ |
| Claude Sonnet 5 | مهاجرت `0156` (پشتِ `0155`)، `models/manufacturing.py` (`ProductionPlan` تازه، `production_plan_id` روی `ProductionOrder`)، `schemas/manufacturing.py`، `services/manufacturing.py`، `routers/manufacturing.py`، `models/counters.py`، `routers/numbering.py`، `audit.py`، `services/entry_source.py`، `desktop/src/pages/ManufacturingPage.tsx`، `moduleSections.tsx`، `moduleLists.tsx`، `HelpPage.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و پنج schemaِ probeِ یک‌بارمصرف (`cubita_probe6`–`10`، حذف شدند) | تولید، فازِ ۱ (شاخه‌ی `feat/manufacturing-plan-document-split`): تفکیکِ سفارش (برنامه، بدونِ اثرِ انبار) از سند (اجرا، دست‌نخورده) — موتورِ ثبتِ سند عمداً به WarehouseIssue/WarehouseReceipt سیم‌کشی نشد (ریسکِ بازآراییِ موتورِ تست‌شده زیرِ فشارِ زمان)؛ سناریوی بحرانیِ افزودنِ FK روی جدولِ دارای ردیفِ واقعی جداگانه تست شد | ۱۴۰۵/۰۶/۲۴ |
| Claude Sonnet 5 | مهاجرت `0154`→`0155` (پشتِ `0153`؛ **۱۴۰۵/۰۶/۲۴: بعداً دوباره شماره‌گذاری شد به `0155` پشتِ `0154`، همراهِ رفعِ دوسرِ مهاجرت — `fix/contracting-migration-renumber`**)، `models/contracting.py` (`ContractSettlement`)، `schemas/contracting.py`، `services/contracting.py`، `routers/contracting.py`، `models/counters.py`، `routers/numbering.py`، `audit.py`، `services/chart_codes.py` (چهار نقشِ تازه: درآمدِ پیمانکاری، سپرده‌ی حسن انجامِ کار، پیش‌دریافتِ پیمان، سایرِ کسورات)، `seed.py CHART_OF_ACCOUNTS` (همان چهار کد: ۱۱۱۶/۲۱۱۴/۴۱۰۹/۵۱۱۹)، `services/entry_source.py` (ثبتِ `contract_settlement` در `SOURCE_MODELS`)، `desktop/src/pages/contracting/ContractingOpsPages.tsx` و `ContractingListPages.tsx`، `navModel.tsx`، `moduleLists.tsx`، `Dashboard.tsx`، `HelpPage.tsx`، انتهای `api.ts`؛ آزادسازی `pytest` و پنج schemaِ probeِ یک‌بارمصرف (`cubita_probe2`–`6`، حذف شدند) | پیمانکاری، فازِ ۴ — آخرین فاز (شاخه‌ی `feat/contracting-settlement`، پشتِ `feat/contracting-statement`): تسویه‌حسابِ پیمان — تنها سندِ ماژول که حسابداریِ واقعی و `VoidableMixin` دارد؛ مبالغ از جمعِ صورت‌وضعیت‌ها خودکار، ابطال از مسیرِ مشترکِ `voiding.py`؛ ماژولِ پیمانکاری کامل شد | ۱۴۰۵/۰۶/۲۴ |
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
