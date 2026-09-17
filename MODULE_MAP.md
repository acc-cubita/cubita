# نقشه‌ی ماژول‌های کوبیتا

> تولیدشده از خودِ کد — نه از حافظه. منابع: `desktop/src/lib/navModel.tsx` (گروه‌های
> عملیات)، `desktop/src/components/moduleLists.tsx` (فهرست‌ها و نگاشتِ عملیات↔فهرست)،
> `desktop/src/components/moduleSections.tsx` (تب‌های ماژول‌های تب‌دار)، و ورودی‌های
> داده از ردیابیِ فراخوان‌های `fetch*` در درختِ کامپوننتِ هر صفحه تا سه سطح.

> **تاریخ تولید:** ۱۴۰۵/۰۶/۲۶ · **شاخه:** `feat/contact-role-flags`

**سه نوع صفحه** در این پروژه هست و مرزشان جدی است:

* **عملیات** — کاری که کاربر *انجام می‌دهد*. از کارتِ «عملیات» باز می‌شود.
* **فهرست** — داده‌ای که *ذخیره شده*. از کارتِ «فهرست» باز می‌شود.
* **تب** — ماژول‌های تب‌دار (انبار، خرید، تولید…) هر بخششان دفترِ خودش را درون خود دارد.

---

## بخش ۱ — فهرستِ ماژول‌ها و زیرمجموعه‌ها

| # | ماژول | عملیات | فهرست | تب |
|---|---|---|---|---|
| 1 | میزکار | 1 | 0 | — |
| 2 | مشتریان و فروش | 22 | 12 | 10 |
| 3 | اتصال فروشگاه | 1 | 0 | 2 |
| 4 | تامین‌کنندگان و انبار | 3 | 0 | 21 |
| 5 | تولید | 1 | 0 | 10 |
| 6 | دریافت و پرداخت | 19 | 9 | — |
| 7 | دارایی ثابت | 1 | 0 | 13 |
| 8 | حسابداری | 22 | 7 | — |
| 9 | حقوق و دستمزد | 11 | 2 | 4 |
| 10 | پیمانکاری | 5 | 4 | — |
| 11 | سامانه مؤدیان | 1 | 1 | 3 |
| 12 | شرکت | 10 | 16 | 2 |
| 13 | تنظیمات | 9 | 4 | — |

---

### میزکار

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `overview` | داشبورد | _خودش فهرست/گزارش است_ |

---

### مشتریان و فروش

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `contacts` | اشخاص | `contactlist` — طرف حساب‌ها |
| `crm` | باشگاه مشتریان | _خودش فهرست/گزارش است_ |
| `pos` | صندوق فروشگاهی | _خودش فهرست/گزارش است_ |
| `salesflow` | فرآیند فروش | _چیزی ثبت نمی‌کند_ |
| `salesinvoice` | فاکتور فروش | `saleslist` — فاکتورهای فروش |
| `quotations` | پیش‌فاکتور | `quotationlist` — پیش‌فاکتورها |
| `salesreturn` | فاکتور برگشتی | `returnlist` — فاکتورهای برگشتی |
| `invoiceclose` | بستن فاکتور | _وضعیت عوض می‌کند، رکورد نمی‌سازد_ |
| `creditnote` | اعلامیه بدهکار بستانکار | `notelist` — اعلامیه‌های بدهکار و بستانکار |
| `contactstatement` | صورت حساب طرف مقابل | _خودش فهرست/گزارش است_ |
| `commission` | پورسانت | `commissionrulelist` — قواعد پورسانت |
| `commissioncalc` | محاسبه پورسانت | `commissionrunlist` — محاسبه‌های پورسانت |
| `customs` | اظهارنامه گمرکی | `customslist` — اظهارنامه‌های گمرکی |
| `saletype` | نوع فروش | `saletypelist` — انواع فروش |
| `returnreason` | علت برگشت کالا | _خودش فهرست/گزارش است_ |
| `priceannounce` | اعلامیه قیمت | `priceannouncelist` — اعلامیه‌های قیمت |
| `bundle` | بسته محصول جدید | `bundlelist` — بسته‌های محصول |
| `discount` | تخفیف جدید | `pricingfactorlist` — تخفیف‌ها و عوامل افزاینده |
| `discountgroup` | گروه کالای تخفیف جدید | `discountgrouplist` — گروه‌های کالای تخفیف |
| `markup` | عامل افزاینده جدید | `pricingfactorlist` — تخفیف‌ها و عوامل افزاینده |
| `salesbrowse` | مرور فروش | _خودش فهرست/گزارش است_ |
| `contactoverview` | مرور جامع طرف حساب | _خودش فهرست/گزارش است_ |

**فهرست**

* `saleslist` — فاکتورهای فروش
* `quotationlist` — پیش‌فاکتورها
* `returnlist` — فاکتورهای برگشتی
* `notelist` — اعلامیه‌های بدهکار و بستانکار
* `commissionrulelist` — قواعد پورسانت
* `commissionrunlist` — محاسبه‌های پورسانت
* `customslist` — اظهارنامه‌های گمرکی
* `saletypelist` — انواع فروش
* `priceannouncelist` — اعلامیه‌های قیمت
* `bundlelist` — بسته‌های محصول
* `pricingfactorlist` — تخفیف‌ها و عوامل افزاینده
* `discountgrouplist` — گروه‌های کالای تخفیف

**تب‌های «اشخاص»** (`contacts`)

* `contacts` — طرف حساب‌ها
* `aging` — سنین مطالبات
* `import` — ورود گروهی اشخاص

**تب‌های «باشگاه مشتریان»** (`crm`)

* `leads` — سرنخ‌ها
* `activities` — پیگیری‌ها
* `loyalty` — باشگاه مشتریان
* `segments` — بخش‌بندی
* `tiers` — سطوح باشگاه
* `rewards` — جوایز
* `birthdays` — تولدها

---

### اتصال فروشگاه

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `integration` | اتصال فروشگاه | _چیزی ثبت نمی‌کند_ |

**تب‌های «اتصال فروشگاه»** (`integration`)

* `build` — فروشگاهِ کوبیتا
* `connect` — اتصال به سایتِ موجود

---

### تامین‌کنندگان و انبار

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `purchases` | خرید | _خودش فهرست/گزارش است_ |
| `inventory` | انبار | _خودش فهرست/گزارش است_ |
| `creditnote` | اعلامیه بدهکار بستانکار | `notelist` — اعلامیه‌های بدهکار و بستانکار |

**تب‌های «خرید»** (`purchases`)

* `invoices` — فاکتور خرید
* `services` — فاکتور خرید خدمات
* `receipts` — رسید انبار
* `returns` — برگشت از خرید
* `deductions` — انواع کسورات

**تب‌های «انبار»** (`inventory`)

* `products` — کالاها
* `stock` — موجودی
* `kardex` — کاردکس
* `low` — نیازمندِ سفارش
* `warehouses` — انبارها
* `count` — انبارگردانی
* `adjust` — تعدیل دستی
* `issues` — خروج انبار
* `issue-returns` — برگشت خروج انبار
* `transfer` — انتقال بین انبار
* `valuation` — قیمت‌گذاری اسناد
* `unpriced` — قیمت‌گذاری ورودی‌ها
* `pricelists` — لیست قیمت
* `batches` — بچ و انقضا
* `serials` — جستجوی سریال
* `import` — ورود گروهی کالا

---

### تولید

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `manufacturing` | تولید | _خودش فهرست/گزارش است_ |

**تب‌های «تولید»** (`manufacturing`)

* `boms` — فرمول‌های ساخت
* `orders` — سفارش تولید
* `materials` — تحویل مواد
* `receipts` — رسید محصول
* `costing` — محاسبه قیمت تمام‌شده
* `bom-list` — فهرست فرمول‌های ساخته‌شده
* `order-list` — سفارشات تولید
* `variance` — انحراف مصرف مواد
* `kardex` — کاردکس تولید
* `cost-report` — گزارش قیمت تمام‌شده

---

### دریافت و پرداخت

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `payflow` | فرآیند دریافت و پرداخت | _چیزی ثبت نمی‌کند_ |
| `receiptvoucher` | رسید دریافت | `treasuryledger` — دریافت‌ها و پرداخت‌ها |
| `paymentvoucher` | اعلامیه پرداخت | `paymentnoticelist` — اعلامیه‌های پرداخت |
| `checkops` | عملیات بانکی چک دریافتنی | `checksearch` — جستجوی چک |
| `contactsettle` | تسویه حساب طرف مقابل | `contactsettlelist` — تسویه‌های طرف مقابل |
| `checkreturn` | استرداد چک | `checkoplist` — عملیات چک |
| `checkpayclear` | وصول چک پرداختنی | `checkoplist` — عملیات چک |
| `checksearch` | جستجوی چک | _خودش فهرست/گزارش است_ |
| `possettle` | تسویه کارت خوان | `possettlelist` — تسویه‌های کارتخوان |
| `bankstatement` | صورت حساب بانکی | `statementlist` — ردیف‌های صورت‌حساب بانکی |
| `bankreconcile` | مغایرت بانکی | _وضعیت عوض می‌کند، رکورد نمی‌سازد_ |
| `cashbox` | صندوق | _خودش فهرست/گزارش است_ |
| `cashboxes` | تعریف صندوق | _خودش فهرست/گزارش است_ |
| `bankaccounts` | حساب بانکی | _خودش فهرست/گزارش است_ |
| `posterminals` | دستگاه کارت خوان | `posterminallist` — دستگاه‌های کارتخوان |
| `checkbooks` | دسته چک | `checkbooklist` — دسته‌چک‌ها |
| `pettyholder` | تنخواه دار | `pettylist` — گردش تنخواه |
| `pettyexpense` | صورت هزینه تنخواه | `pettylist` — گردش تنخواه |
| `bankledger` | مرور عملیات بانکی | _خودش فهرست/گزارش است_ |

**فهرست**

* `treasuryledger` — دریافت‌ها و پرداخت‌ها
* `paymentnoticelist` — اعلامیه‌های پرداخت
* `checkbooklist` — دسته‌چک‌ها
* `posterminallist` — دستگاه‌های کارتخوان
* `possettlelist` — تسویه‌های کارتخوان
* `checkoplist` — عملیات چک
* `contactsettlelist` — تسویه‌های طرف مقابل
* `statementlist` — ردیف‌های صورت‌حساب بانکی
* `pettylist` — گردش تنخواه

---

### دارایی ثابت

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `fixedassets` | دارایی ثابت | _خودش فهرست/گزارش است_ |

**تب‌های «دارایی ثابت»** (`fixedassets`)

* `assets` — کارت دارایی
* `placement` — تحویل و استقرار
* `depreciation-calc` — محاسبه استهلاک
* `depreciation-post` — صدور سند استهلاک
* `estimate` — تغییر روش یا عمر مفید
* `transfer` — جابه‌جایی دارایی
* `disposal` — خروج دارایی
* `improvement` — تعمیرات اساسی
* `registry` — فهرست دارایی‌ها
* `depreciation-list` — فهرست محاسبات استهلاک
* `depreciation-docs` — گزارش اسناد استهلاک
* `assignments` — جابه‌جایی‌ها و تحویل‌ها
* `disposals` — خروج و فروش دارایی

---

### حسابداری

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `acctchart` | درختواره حساب‌ها | `accountlist` — فهرست حساب‌ها |
| `newaccount` | سرفصل جدید | `accountlist` — فهرست حساب‌ها |
| `openingbalance` | مانده اول دوره | `entrylist` — اسناد حسابداری |
| `journalentry` | سند حسابداری | `entrylist` — اسناد حسابداری |
| `entrycartable` | کارتابل صدور سند حسابداری | _وضعیت عوض می‌کند، رکورد نمی‌سازد_ |
| `finalizeentries` | تبدیل اسناد موقت به دائم | _وضعیت عوض می‌کند، رکورد نمی‌سازد_ |
| `renumber` | شماره‌گذاری مجدد اسناد | _وضعیت عوض می‌کند، رکورد نمی‌سازد_ |
| `mergeentries` | ادغام اسناد | `entrylist` — اسناد حسابداری |
| `reclassify` | جابه‌جایی حساب در درختواره | _وضعیت عوض می‌کند، رکورد نمی‌سازد_ |
| `analytics` | تفصیلی سایر | `analyticlist` — تفصیلی‌های سایر |
| `fxrevaluation` | صدور سند تسعیر ارز | `entrylist` — اسناد حسابداری |
| `balancereclass` | اصلاح طبقه‌بندی مانده | `entrylist` — اسناد حسابداری |
| `generaldoc` | صدور سند کل | _خودش فهرست/گزارش است_ |
| `closepnl` | بستن حساب‌های سود و زیان | `periodcloselist` — دوره‌های بسته‌شده |
| `closingopening` | صدور سند اختتامیه و افتتاحیه | `entrylist` — اسناد حسابداری |
| `vat` | مالیات بر ارزش افزوده | _خودش فهرست/گزارش است_ |
| `ebooks` | دفاتر تجارت الکترونیک | _خودش فهرست/گزارش است_ |
| `accountbrowse` | مرور حساب‌ها | _خودش فهرست/گزارش است_ |
| `balancereport` | گزارش ترازها | _خودش فهرست/گزارش است_ |
| `ledgerreport` | گزارش دفتر | _خودش فهرست/گزارش است_ |
| `integrity` | بررسی یکپارچگی | _خودش فهرست/گزارش است_ |
| `reports` | گزارش‌ها | _خودش فهرست/گزارش است_ |

**فهرست**

* `entrylist` — اسناد حسابداری
* `accountlist` — فهرست حساب‌ها
* `recurringlist` — اسناد تکرارشونده
* `budgetlist` — بودجه‌بندی
* `currencylist` — ارزها و نرخ ارز
* `periodcloselist` — دوره‌های بسته‌شده
* `analyticlist` — تفصیلی‌های سایر

---

### حقوق و دستمزد

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `contractnew` | قرارداد جدید | `contractlist` — قراردادها |
| `servicelocation` | محل خدمت جدید | _خودش فهرست/گزارش است_ |
| `jobtitle` | شغل جدید | _خودش فهرست/گزارش است_ |
| `payrollfactors` | عوامل حقوق و مزایا | _خودش فهرست/گزارش است_ |
| `payrolltaxgroups` | گروه مالیاتی و شعب | _خودش فهرست/گزارش است_ |
| `taxtables` | جداول مالیات | _خودش فهرست/گزارش است_ |
| `loantype` | نوع وام جدید | _خودش فهرست/گزارش است_ |
| `employeeloans` | تقسیط — وام‌های پرسنلی | _خودش فهرست/گزارش است_ |
| `settlement` | تسویه حساب | _خودش فهرست/گزارش است_ |
| `deploymentinfo` | اطلاعات استقرار | _خودش فهرست/گزارش است_ |
| `payroll` | حقوق و دستمزد | _خودش فهرست/گزارش است_ |

**فهرست**

* `contractlist` — قراردادها
* `payslipledger` — مرور حقوق

**تب‌های «حقوق و دستمزد»** (`payroll`)

* `staff` — پرسنل و احکام
* `run` — کارکرد و صدور فیش
* `benefits` — مزایا
* `settings` — تنظیماتِ حقوق

---

### پیمانکاری

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `contractingnew` | پیمان | `contractinglist` — پیمان‌ها |
| `contractingamendment` | متمم پیمان | `contractingamendmentlist` — متمم‌های پیمان |
| `contractingstatement` | صورت وضعیت دریافتی | `contractingstatementlist` — صورت وضعیت‌های دریافتی |
| `contractingsettlement` | تسویه حساب پیمان | `contractingsettlementlist` — تسویه‌حساب‌های پیمان |
| `contractingstatus` | تغییر وضعیت پیمان | _وضعیت عوض می‌کند، رکورد نمی‌سازد_ |

**فهرست**

* `contractinglist` — پیمان‌ها
* `contractingamendmentlist` — متمم‌های پیمان
* `contractingstatementlist` — صورت وضعیت‌های دریافتی
* `contractingsettlementlist` — تسویه‌حساب‌های پیمان

---

### سامانه مؤدیان

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `moadian` | سامانه مؤدیان | `moadianhistory` — تاریخچه ارسال‌ها |

**فهرست**

* `moadianhistory` — تاریخچه ارسال‌ها

**تب‌های «سامانه مؤدیان»** (`moadian`)

* `status` — وضعیت و آمادگی
* `send` — ارسال صورتحساب
* `settings` — تنظیمات و اعتبارنامه

---

### شرکت

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `contactnew` | طرف حساب جدید | `contactlist` — طرف حساب‌ها |
| `ownertxn` | تراکنش شریک | `ownertxnlist` — تراکنش‌های شریک |
| `installments` | فروش اقساطی | `installmentplans` — قراردادهای اقساطی |
| `costcenter` | مرکز هزینه | `costcenterlist` — مراکز هزینه |
| `geo` | محل‌های جغرافیایی | `geolist` — محل‌های جغرافیایی |
| `contactgroup` | گروه جدید | `contactgrouplist` — گروه‌های طرف حساب |
| `openingops` | عملیات اول دوره | _چیزی ثبت نمی‌کند_ |
| `yearendops` | عملیات پایان سال | _چیزی ثبت نمی‌کند_ |
| `yearendreminder` | یادآوری عملیات پایان سال | `calendarlist` — رویدادهای تقویم |
| `calendar` | تقویم و یادآوری | `calendarlist` — رویدادهای تقویم |

**فهرست**

* `dataexport` — ارسال اطلاعات
* `dataimport` — دریافت اطلاعات
* `reportbuilder` — گزارش‌ساز
* `dynamicreports` — گزارش‌های پویا
* `dayactivity` — فعالیت‌های روز
* `mgmtreports` — گزارش‌ها و نمودارهای مدیریتی
* `usagereport` — گزارش استفاده از نرم‌افزار
* `contactlist` — طرف حساب‌ها
* `ownertxnlist` — تراکنش‌های شریک
* `relatedpeople` — افراد مرتبط
* `installmentplans` — قراردادهای اقساطی
* `allinstallments` — همه اقساط
* `costcenterlist` — مراکز هزینه
* `geolist` — محل‌های جغرافیایی
* `contactgrouplist` — گروه‌های طرف حساب
* `calendarlist` — رویدادهای تقویم

**تب‌های «تقویم و یادآوری»** (`calendar`)

* `reminders` — کارهای امروز
* `calendar` — تقویم ماهانه

---

### تنظیمات

**عملیات**

| کلید | منو | فهرستِ نظیر |
|---|---|---|
| `fiscalyear` | سال مالی | `fiscalyearlist` — سال‌های مالی |
| `coding` | کدینگ | `accountlist` — فهرست حساب‌ها |
| `personalization` | شخصی‌سازی | `accountlist` — فهرست حساب‌ها |
| `numbering` | روش‌های شماره‌گذاری | `numberinglist` — روش‌های شماره‌گذاری |
| `team` | کاربر جدید | `userlist` — کاربران |
| `password` | تغییر کلمه عبور | _چیزی ثبت نمی‌کند_ |
| `backup` | پشتیبان‌گیری خودکار | `backuplist` — نسخه‌های پشتیبانی و بازیابی |
| `theme` | ظاهر و پوسته | _چیزی ثبت نمی‌کند_ |
| `help` | راهنما | _چیزی ثبت نمی‌کند_ |

**فهرست**

* `backuplist` — نسخه‌های پشتیبانی و بازیابی
* `userlist` — کاربران
* `fiscalyearlist` — سال‌های مالی
* `numberinglist` — روش‌های شماره‌گذاری

---

## بخش ۲ — هر زیرمجموعه چه دریافت می‌کند

برای هر صفحه: فایلِ پیاده‌سازی، و داده‌هایی که از **بیرونِ خودش** می‌گیرد،
گروه‌بندی‌شده بر اساسِ دامنه‌ای که داده از آن می‌آید.

هر ردیفِ جدول یعنی: «این صفحه برای کار کردن، به آن بخش وابسته است».
صفحه‌ای که جدول ندارد یا فرمِ محلیِ خالص است، یا داده‌اش را از والدش می‌گیرد.

---

### میزکار

#### داشبورد

`overview` · عملیات · `src/components/GuidedDashboard.tsx`

| از | چه می‌گیرد |
|---|---|
| **گزارش** | `fetchIncomeStatement`، `fetchTrialBalance` |
| **سیستم** | `fetchAlerts` |

---

### مشتریان و فروش

#### اشخاص

`contacts` · عملیات · `src/pages/ContactsPage.tsx`

**تب‌ها:** طرف حساب‌ها · سنین مطالبات · ورود گروهی اشخاص

| از | چه می‌گیرد |
|---|---|
| **گزارش** | `fetchAging`، `fetchContactStatement` |
| **طرف حساب** | `fetchContacts` |
| **خزانه** | `fetchPosTerminals` |

#### باشگاه مشتریان

`crm` · عملیات · `src/pages/CrmPage.tsx`

**تب‌ها:** سرنخ‌ها · پیگیری‌ها · باشگاه مشتریان · بخش‌بندی · سطوح باشگاه · جوایز · تولدها

| از | چه می‌گیرد |
|---|---|
| **باشگاه مشتریان** | `fetchBirthdays`، `fetchCrmActivities`، `fetchLeads`، `fetchLoyaltyBalances`، `fetchLoyaltySettings`، `fetchLoyaltyTransactions`، `fetchRewards`، `fetchSegments`، `fetchTierMembers`، `fetchTiers` |
| **طرف حساب** | `fetchContacts` |

#### صندوق فروشگاهی

`pos` · عملیات · `src/pages/PosPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **انبار** | `fetchStockLevels`، `fetchWarehousesLive` |
| **طرف حساب** | `fetchContacts` |
| **کالا** | `fetchItemsLive` |
| **خزانه** | `fetchPosTerminals` |
| **فروش** | `fetchSaleTypes` |

#### فرآیند فروش

`salesflow` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### فاکتور فروش

`salesinvoice` · عملیات · `src/pages/sales/SalesDocumentPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **باشگاه مشتریان** | `fetchContactTier`، `fetchLoyaltySettings`، `fetchMembers` |
| **طرف حساب** | `fetchContacts`، `fetchCreditStatus` |
| **حسابداری** | `fetchCurrencies`، `fetchLatestRate` |
| **شرکت** | `fetchCostCenters` |
| **فروش** | `fetchSaleTypes` |
| **انبار** | `fetchStockLevels` |

#### پیش‌فاکتور

`quotations` · عملیات · `src/pages/sales/SalesDocumentPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **طرف حساب** | `fetchContacts` |
| **انبار** | `fetchStockLevels` |

#### فاکتور برگشتی

`salesreturn` · عملیات · `src/pages/sales/SalesDocumentPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchReturnable`، `fetchSalesInvoices`، `fetchSalesReturnReasons`، `fetchSalesReturns` |

#### بستن فاکتور

`invoiceclose` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchSalesInvoices` |

#### اعلامیه بدهکار بستانکار

`creditnote` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchCurrencies`، `fetchLatestRate` |
| **فروش** | `fetchNoteAccounts` |

#### صورت حساب طرف مقابل

`contactstatement` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchJournalEntriesFiltered` |
| **فروش** | `fetchSalesInvoices` |

#### پورسانت

`commission` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchCommissionRules` |
| **باشگاه مشتریان** | `fetchMembers` |

#### محاسبه پورسانت

`commissioncalc` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchCommissionPreview` |

#### اظهارنامه گمرکی

`customs` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### نوع فروش

`saletype` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartAccounts` |
| **فروش** | `fetchSaleTypes` |

#### علت برگشت کالا

`returnreason` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchSalesReturnReasons` |

#### اعلامیه قیمت

`priceannounce` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchDiscountGroups`، `fetchSaleTypes` |
| **شرکت** | `fetchContactGroups` |
| **حسابداری** | `fetchCurrencies` |
| **کالا** | `fetchUnits` |

#### بسته محصول جدید

`bundle` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### تخفیف جدید

`discount` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchDiscountGroups` |

#### گروه کالای تخفیف جدید

`discountgroup` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### عامل افزاینده جدید

`markup` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchDiscountGroups` |

#### مرور فروش

`salesbrowse` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **گزارش** | `fetchPreinvoiceProgress`، `fetchSalesByCustomer`، `fetchSalesByItem`، `fetchSalesByWarehouse`، `fetchSalesReviewDocuments`، `fetchSalesReviewLines`، `fetchSalesReviewSummary` |

#### مرور جامع طرف حساب

`contactoverview` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **گزارش** | `fetchCounterpartyEventLines`، `fetchCounterpartyEvents`، `fetchCounterpartySummary` |

#### فاکتورهای فروش

`saleslist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchSalesInvoices`، `fetchWarehouseIssues` |
| **طرف حساب** | `fetchContacts` |
| **خرید** | `fetchWarehouseReceipts` |

#### پیش‌فاکتورها

`quotationlist` · فهرست · `src/pages/sales/SalesDocumentPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **طرف حساب** | `fetchContacts` |
| **فروش** | `fetchSalesQuotations` |

#### فاکتورهای برگشتی

`returnlist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchSalesReturns` |

#### اعلامیه‌های بدهکار و بستانکار

`notelist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchNoteDuplicateDraft`، `fetchNotes` |
| **طرف حساب** | `fetchContacts` |

#### قواعد پورسانت

`commissionrulelist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchCommissionRules` |

#### محاسبه‌های پورسانت

`commissionrunlist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchCommissionRuns` |

#### اظهارنامه‌های گمرکی

`customslist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchCustoms` |

#### انواع فروش

`saletypelist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchSaleTypes` |

#### اعلامیه‌های قیمت

`priceannouncelist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchDiscountGroups`، `fetchPriceAnnouncements`، `fetchSaleTypes` |
| **کالا** | `fetchItemsLive`، `fetchUnits` |
| **شرکت** | `fetchContactGroups` |

#### بسته‌های محصول

`bundlelist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchBundles` |

#### تخفیف‌ها و عوامل افزاینده

`pricingfactorlist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchPricingFactors` |

#### گروه‌های کالای تخفیف

`discountgrouplist` · فهرست · `src/pages/sales/SalesListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **فروش** | `fetchDiscountGroups` |

---

### اتصال فروشگاه

#### اتصال فروشگاه

`integration` · عملیات

**تب‌ها:** فروشگاهِ کوبیتا · اتصال به سایتِ موجود

_ورودیِ مستقیمی از بخش دیگری ندارد._

---

### تامین‌کنندگان و انبار

#### خرید

`purchases` · عملیات · `src/pages/PurchasesPage.tsx`

**تب‌ها:** فاکتور خرید · فاکتور خرید خدمات · رسید انبار · برگشت از خرید · انواع کسورات

| از | چه می‌گیرد |
|---|---|
| **خرید** | `fetchPurchaseDeductionTypes`، `fetchPurchaseInvoiceDuplicate`، `fetchPurchaseInvoices`، `fetchPurchaseInvoicesOfKind`، `fetchPurchasePriceInfo`، `fetchPurchaseReturnable`، `fetchPurchaseReturns`، `fetchPurchaseSummary`، `fetchWarehouseReceipts` |
| **حسابداری** | `fetchAccountsLive`، `fetchCurrencies`، `fetchJournalEntry`، `fetchLatestRate` |
| **انبار** | `fetchAllWarehouseReceipts`، `fetchReceiptPaymentContext`، `fetchReceiptReturnable` |
| **فروش** | `fetchSalesInvoices`، `fetchWarehouseIssues` |
| **طرف حساب** | `fetchContacts` |
| **شرکت** | `fetchCostCenters` |
| **کالا** | `fetchItemsLive` |

#### انبار

`inventory` · عملیات · `src/pages/InventoryPage.tsx`

**تب‌ها:** کالاها · موجودی · کاردکس · نیازمندِ سفارش · انبارها · انبارگردانی · تعدیل دستی · خروج انبار · برگشت خروج انبار · انتقال بین انبار · قیمت‌گذاری اسناد · قیمت‌گذاری ورودی‌ها · لیست قیمت · بچ و انقضا · جستجوی سریال · ورود گروهی کالا

| از | چه می‌گیرد |
|---|---|
| **انبار** | `fetchBatchSerials`، `fetchIssueInvoiceContext`، `fetchIssueReturn`، `fetchIssueReturnBasis`، `fetchIssueReturnBasisDetail`، `fetchIssueReturnLedger`، `fetchLowStock`، `fetchOverStock`، `fetchStockAdjustments`، `fetchStockBatches`، `fetchStockCount`، `fetchStockCountDrift`، `fetchStockCounts`، `fetchStockLevels`، `fetchUnpricedOutputs`، `fetchValuationPreview`، `fetchValuationRunList`، `fetchWarehouseIssue`، `fetchWarehouseIssueLedger`، `fetchWarehouseStock`، `fetchWarehousesAdmin`، `fetchWarehousesLive` |
| **کالا** | `fetchItemAttributes`، `fetchItemGroups`، `fetchItemsLive`، `fetchUnits` |
| **فروش** | `fetchDiscountGroups`، `fetchSaleTypes`، `fetchSalesQuotations` |
| **حسابداری** | `fetchAccountsLive`، `fetchJournalEntry` |
| **قیمت‌گذاری** | `fetchPriceListItems`، `fetchPriceLists` |
| **شرکت** | `fetchContactGroups` |
| **طرف حساب** | `fetchContacts` |
| **گزارش** | `fetchKardex` |

#### اعلامیه بدهکار بستانکار

`creditnote` · عملیات · `src/pages/sales/SalesOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchCurrencies`، `fetchLatestRate` |
| **فروش** | `fetchNoteAccounts` |

---

### تولید

#### تولید

`manufacturing` · عملیات · `src/pages/ManufacturingPage.tsx`

**تب‌ها:** فرمول‌های ساخت · سفارش تولید · تحویل مواد · رسید محصول · محاسبه قیمت تمام‌شده · فهرست فرمول‌های ساخته‌شده · سفارشات تولید · انحراف مصرف مواد · کاردکس تولید · گزارش قیمت تمام‌شده

| از | چه می‌گیرد |
|---|---|
| **تولید** | `fetchBoms`، `fetchMaterialVariance`، `fetchProductionCostReport`، `fetchProductionKardex`، `fetchProductionPlans` |
| **انبار** | `fetchAllWarehouseReceipts`، `fetchStockLevels`، `fetchWarehouseIssueLedger`، `fetchWarehousesLive` |
| **کالا** | `fetchItemsLive` |

---

### دریافت و پرداخت

#### فرآیند دریافت و پرداخت

`payflow` · عملیات · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchPettyCashBalance`، `fetchTreasuryTransactions` |

#### رسید دریافت

`receiptvoucher` · عملیات · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchCashboxes`، `fetchPosTerminals`، `fetchReceiptDocuments` |
| **حسابداری** | `fetchAccountsLive`، `fetchCurrencies`، `fetchLatestRate` |
| **طرف حساب** | `fetchContacts` |

#### اعلامیه پرداخت

`paymentvoucher` · عملیات · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchCashboxes`، `fetchCheckbooks`، `fetchEligibleReceivedCheques`، `fetchNextCheckNumber`، `fetchPaymentDocuments` |
| **حسابداری** | `fetchAccountsLive`، `fetchCurrencies`، `fetchJournalEntry`، `fetchLatestRate` |
| **طرف حساب** | `fetchContacts` |

#### عملیات بانکی چک دریافتنی

`checkops` · عملیات · `src/pages/treasury/CheckOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchCashboxes`، `fetchCheckTimeline`، `fetchChecks` |
| **طرف حساب** | `fetchContacts` |

#### تسویه حساب طرف مقابل

`contactsettle` · عملیات · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchAllocationHistory`، `fetchCounterpartyAccounts`، `fetchOpenItems` |
| **طرف حساب** | `fetchContacts` |

#### استرداد چک

`checkreturn` · عملیات · `src/pages/treasury/CheckOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchCashboxes`، `fetchCheckTimeline`، `fetchChecks` |

#### وصول چک پرداختنی

`checkpayclear` · عملیات · `src/pages/treasury/CheckOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchCashboxes`، `fetchCheckTimeline`، `fetchChecks` |

#### جستجوی چک

`checksearch` · عملیات · `src/pages/treasury/CheckOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchCheckSummary`، `fetchCheckTimeline`، `fetchChecks` |

#### تسویه کارت خوان

`possettle` · عملیات · `src/pages/treasury/BankOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchPosPending`، `fetchPosSettlementPreview`، `fetchPosTerminals` |

#### صورت حساب بانکی

`bankstatement` · عملیات · `src/pages/treasury/BankOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchStatementLines` |

#### مغایرت بانکی

`bankreconcile` · عملیات · `src/pages/treasury/BankOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchReconciliationSummary`، `fetchStatementLines` |

#### صندوق

`cashbox` · عملیات · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchTreasuryTransactions` |

#### تعریف صندوق

`cashboxes` · عملیات · `src/pages/treasury/CashboxPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAnalytics` |
| **خزانه** | `fetchCashboxes` |

#### حساب بانکی

`bankaccounts` · عملیات · `src/pages/treasury/BankOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAnalytics`، `fetchJournalEntry` |
| **خزانه** | `fetchBankAccountsAdmin` |
| **گزارش** | `fetchGeneralLedger` |

#### دستگاه کارت خوان

`posterminals` · عملیات · `src/pages/treasury/BankOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAnalytics` |
| **خزانه** | `fetchPosTerminals` |

#### دسته چک

`checkbooks` · عملیات · `src/pages/treasury/CheckOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchCheckbookLeaves`، `fetchCheckbooks`، `fetchNextCheckNumber` |
| **طرف حساب** | `fetchContacts` |

#### تنخواه دار

`pettyholder` · عملیات · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchPettyCashBalance`، `fetchPettyCashTransactions` |

#### صورت هزینه تنخواه

`pettyexpense` · عملیات · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchPettyCashBalance`، `fetchPettyCashTransactions` |

#### مرور عملیات بانکی

`bankledger` · عملیات · `src/pages/treasury/BankOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsLive`، `fetchBankTransactions` |

#### دریافت‌ها و پرداخت‌ها

`treasuryledger` · فهرست · `src/pages/treasury/TreasuryOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchTreasuryTransactions` |

#### اعلامیه‌های پرداخت

`paymentnoticelist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchPaymentDocuments` |

#### دسته‌چک‌ها

`checkbooklist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchCheckbooks` |

#### دستگاه‌های کارتخوان

`posterminallist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchPosTerminals` |

#### تسویه‌های کارتخوان

`possettlelist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchPosSettlement`، `fetchPosSettlements` |

#### عملیات چک

`checkoplist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchCheckOperations` |

#### تسویه‌های طرف مقابل

`contactsettlelist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchContactSettlement`، `fetchContactSettlements` |

#### ردیف‌های صورت‌حساب بانکی

`statementlist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsAdmin`، `fetchStatementLines` |

#### گردش تنخواه

`pettylist` · فهرست · `src/pages/treasury/TreasuryListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchPettyCashTransactions` |

---

### دارایی ثابت

#### دارایی ثابت

`fixedassets` · عملیات

**تب‌ها:** کارت دارایی · تحویل و استقرار · محاسبه استهلاک · صدور سند استهلاک · تغییر روش یا عمر مفید · جابه‌جایی دارایی · خروج دارایی · تعمیرات اساسی · فهرست دارایی‌ها · فهرست محاسبات استهلاک · گزارش اسناد استهلاک · جابه‌جایی‌ها و تحویل‌ها · خروج و فروش دارایی

_ورودیِ مستقیمی از بخش دیگری ندارد._

---

### حسابداری

#### درختواره حساب‌ها

`acctchart` · عملیات · `src/pages/accounting/ChartPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartAccounts`، `fetchJournalEntry`، `fetchNextAccountCode` |
| **گزارش** | `fetchGeneralLedger`، `fetchTrialBalance` |

#### سرفصل جدید

`newaccount` · عملیات · `src/pages/accounting/ChartPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartAccounts`، `fetchNextAccountCode` |

#### مانده اول دوره

`openingbalance` · عملیات · `src/pages/accounting/OpeningBalancePage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAccountsLive`، `fetchOpeningStatus` |
| **کالا** | `fetchItemsLive` |
| **انبار** | `fetchWarehousesLive` |

#### سند حسابداری

`journalentry` · عملیات · `src/pages/accounting/JournalPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAnalytics`، `fetchCurrencies`، `fetchLatestRate`، `fetchTafsiliMode` |
| **شرکت** | `fetchCostCenters` |

#### کارتابل صدور سند حسابداری

`entrycartable` · عملیات · `src/pages/accounting/JournalPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchCartable` |

#### تبدیل اسناد موقت به دائم

`finalizeentries` · عملیات · `src/pages/accounting/JournalPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchCartable` |

#### شماره‌گذاری مجدد اسناد

`renumber` · عملیات · `src/pages/accounting/JournalPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchRenumberPreview` |

#### ادغام اسناد

`mergeentries` · عملیات · `src/pages/accounting/JournalPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchJournalEntriesFiltered` |

#### جابه‌جایی حساب در درختواره

`reclassify` · عملیات · `src/pages/accounting/ChartPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartAccounts` |

#### تفصیلی سایر

`analytics` · عملیات · `src/pages/accounting/ChartPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAnalytics` |

#### صدور سند تسعیر ارز

`fxrevaluation` · عملیات · `src/pages/accounting/ClosingPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchCurrencies`، `fetchFxPreview`، `fetchRates` |

#### اصلاح طبقه‌بندی مانده

`balancereclass` · عملیات · `src/pages/accounting/ClosingPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartAccounts`، `fetchReclassSources` |

#### صدور سند کل

`generaldoc` · عملیات · `src/pages/accounting/ClosingPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAccountBalances`، `fetchChartAccounts` |

#### بستن حساب‌های سود و زیان

`closepnl` · عملیات · `src/pages/accounting/ClosingPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchPeriodCloses`، `fetchPnlClosePreview` |

#### صدور سند اختتامیه و افتتاحیه

`closingopening` · عملیات · `src/pages/accounting/ClosingPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchClosingPreview`، `fetchOpeningPreview` |

#### مالیات بر ارزش افزوده

`vat` · عملیات · `src/pages/accounting/ReportPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **گزارش** | `fetchVatReport` |

#### دفاتر تجارت الکترونیک

`ebooks` · عملیات · `src/pages/accounting/ReportPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchLegalBook` |

#### مرور حساب‌ها

`accountbrowse` · عملیات · `src/pages/accounting/ChartPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAccountBalances`، `fetchAnalytics`، `fetchChartAccounts`، `fetchJournalEntry` |
| **شرکت** | `fetchCostCenters`، `fetchSavedReports` |
| **گزارش** | `fetchGeneralLedger` |

#### گزارش ترازها

`balancereport` · عملیات · `src/pages/accounting/ReportPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAccountBalances`، `fetchAnalytics`، `fetchChartAccounts`، `fetchJournalEntry` |
| **گزارش** | `fetchGeneralLedger`، `fetchMissingTafsili`، `fetchNatureViolations` |
| **شرکت** | `fetchCostCenters`، `fetchSavedReports` |

#### گزارش دفتر

`ledgerreport` · عملیات · `src/pages/accounting/ReportPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAnalytics`، `fetchChartAccounts`، `fetchJournalEntriesFiltered`، `fetchJournalEntry` |
| **گزارش** | `fetchAnalyticLedger`، `fetchGeneralLedger` |
| **شرکت** | `fetchCostCenters`، `fetchSavedReports` |

#### بررسی یکپارچگی

`integrity` · عملیات · `src/pages/accounting/IntegrityPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **گزارش** | `fetchGeneralLedger`، `fetchIntegrityReport`، `fetchKardex` |
| **حسابداری** | `fetchAnalytics`، `fetchJournalEntry` |
| **شرکت** | `fetchCostCenters`، `fetchSavedReports` |

#### گزارش‌ها

`reports` · عملیات

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### اسناد حسابداری

`entrylist` · فهرست · `src/pages/accounting/JournalPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchJournalEntriesFiltered` |

#### فهرست حساب‌ها

`accountlist` · فهرست · `src/pages/accounting/ChartPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartAccounts` |

#### اسناد تکرارشونده

`recurringlist` · فهرست · `src/pages/accounting/AccountingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchCostCenters` |
| **حسابداری** | `fetchRecurringEntries` |

#### بودجه‌بندی

`budgetlist` · فهرست · `src/pages/accounting/AccountingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchBudgetLines` |

#### ارزها و نرخ ارز

`currencylist` · فهرست · `src/pages/accounting/AccountingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchCurrencies`، `fetchRates` |

#### دوره‌های بسته‌شده

`periodcloselist` · فهرست · `src/pages/accounting/AccountingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchPeriodCloses` |

#### تفصیلی‌های سایر

`analyticlist` · فهرست · `src/pages/ledgers/ModuleListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAnalytics` |

---

### حقوق و دستمزد

#### قرارداد جدید

`contractnew` · عملیات · `src/pages/payroll/ContractFormPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchAllowedContractTypes`، `fetchEmployeeCandidates`، `fetchInsuranceTaxBranches`، `fetchJobTitles`، `fetchPayrollFactors`، `fetchPayrollTaxGroups`، `fetchServiceLocations` |
| **شرکت** | `fetchCostCenters` |

#### محل خدمت جدید

`servicelocation` · عملیات · `src/pages/payroll/PayrollRefPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchServiceLocations` |

#### شغل جدید

`jobtitle` · عملیات · `src/pages/payroll/PayrollRefPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchJobTitles` |

#### عوامل حقوق و مزایا

`payrollfactors` · عملیات · `src/pages/payroll/PayrollRefPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchAccountsLive` |
| **حقوق** | `fetchPayrollFactors` |

#### گروه مالیاتی و شعب

`payrolltaxgroups` · عملیات · `src/pages/payroll/PayrollRefPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchInsuranceTaxBranches`، `fetchPayrollTaxGroups` |
| **طرف حساب** | `fetchContacts` |
| **شرکت** | `fetchCostCenters` |

#### جداول مالیات

`taxtables` · عملیات · `src/pages/payroll/TaxTablesPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchPayrollTaxGroups`، `fetchTaxTables` |

#### نوع وام جدید

`loantype` · عملیات · `src/pages/payroll/PayrollLoanPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchLoanTypes` |

#### تقسیط — وام‌های پرسنلی

`employeeloans` · عملیات · `src/pages/payroll/PayrollLoanPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchEmployeeLoans`، `fetchEmployees`، `fetchLoanTypes` |

#### تسویه حساب

`settlement` · عملیات · `src/pages/payroll/PayrollLoanPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchEmployeeLoans`، `fetchEmployees`، `fetchSettlements` |

#### اطلاعات استقرار

`deploymentinfo` · عملیات · `src/pages/payroll/PayrollLoanPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchDeploymentInfo`، `fetchEmployees` |

#### حقوق و دستمزد

`payroll` · عملیات

**تب‌ها:** پرسنل و احکام · کارکرد و صدور فیش · مزایا · تنظیماتِ حقوق

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### قراردادها

`contractlist` · فهرست · `src/pages/payroll/ContractListPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchJobTitles`، `fetchSalaryContracts`، `fetchServiceLocations` |

#### مرور حقوق

`payslipledger` · فهرست · `src/pages/payroll/PayslipLedgerPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حقوق** | `fetchEmployees`، `fetchPayrollPeriods`، `fetchPayslipLedger` |

---

### پیمانکاری

#### پیمان

`contractingnew` · عملیات · `src/pages/contracting/ContractingOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **طرف حساب** | `fetchContacts` |
| **پیمانکاری** | `fetchContracts` |
| **شرکت** | `fetchCostCenters` |

#### متمم پیمان

`contractingamendment` · عملیات · `src/pages/contracting/ContractingOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContractAmendments`، `fetchContracts` |

#### صورت وضعیت دریافتی

`contractingstatement` · عملیات · `src/pages/contracting/ContractingOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContractStatements`، `fetchContracts` |

#### تسویه حساب پیمان

`contractingsettlement` · عملیات · `src/pages/contracting/ContractingOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContractSettlements`، `fetchContractStatements`، `fetchContracts` |

#### تغییر وضعیت پیمان

`contractingstatus` · عملیات · `src/pages/contracting/ContractingOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContracts` |

#### پیمان‌ها

`contractinglist` · فهرست · `src/pages/contracting/ContractingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContracts` |

#### متمم‌های پیمان

`contractingamendmentlist` · فهرست · `src/pages/contracting/ContractingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContractAmendments` |

#### صورت وضعیت‌های دریافتی

`contractingstatementlist` · فهرست · `src/pages/contracting/ContractingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContractStatements` |

#### تسویه‌حساب‌های پیمان

`contractingsettlementlist` · فهرست · `src/pages/contracting/ContractingListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **پیمانکاری** | `fetchContractSettlements` |

---

### سامانه مؤدیان

#### سامانه مؤدیان

`moadian` · عملیات · `src/pages/moadian/MoadianModulePage.tsx`

**تب‌ها:** وضعیت و آمادگی · ارسال صورتحساب · تنظیمات و اعتبارنامه

| از | چه می‌گیرد |
|---|---|
| **مؤدیان** | `fetchMoadianPending`، `fetchMoadianReadiness`، `fetchMoadianSettings`، `fetchMoadianSubmissions`، `fetchMoadianUnitMaps`، `fetchMoadianUnmappedUnits` |

#### تاریخچه ارسال‌ها

`moadianhistory` · فهرست · `src/pages/moadian/MoadianModulePage.tsx`

| از | چه می‌گیرد |
|---|---|
| **مؤدیان** | `fetchMoadianPending`، `fetchMoadianReadiness`، `fetchMoadianSettings`، `fetchMoadianSubmissions` |

---

### شرکت

#### طرف حساب جدید

`contactnew` · عملیات · `src/pages/company/ContactFormPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **طرف حساب** | `fetchContactAddresses`، `fetchContactChannels`، `fetchContactTafsiliRequirement`، `fetchContacts` |
| **شرکت** | `fetchContactGroups`، `fetchGeoLocations`، `fetchRelatedPersons` |
| **حقوق** | `fetchEmployees` |

#### تراکنش شریک

`ownertxn` · عملیات · `src/pages/company/OwnerTransactionPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchBankAccountsAdmin`، `fetchCashboxes` |
| **شرکت** | `fetchOwnerTransactions`، `fetchPartnerBalances` |
| **طرف حساب** | `fetchContacts` |

#### فروش اقساطی

`installments` · عملیات · `src/pages/company/InstallmentSalesPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchEarlySettlement`، `fetchInstallmentPlans`، `fetchInstallmentSummary` |
| **طرف حساب** | `fetchContacts` |

#### مرکز هزینه

`costcenter` · عملیات · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchCostCenterAnalysis`، `fetchCostCenterBudget`، `fetchCostCenterLedger`، `fetchCostCenterReport`، `fetchCostCenters` |

#### محل‌های جغرافیایی

`geo` · عملیات · `src/pages/company/CompanyBasicsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchGeoLocations` |

#### گروه جدید

`contactgroup` · عملیات · `src/pages/company/CompanyBasicsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchContactGroups` |

#### عملیات اول دوره

`openingops` · عملیات · `src/pages/company/CompanyOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartSetup`، `fetchFiscalYears` |

#### عملیات پایان سال

`yearendops` · عملیات · `src/pages/company/CompanyOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchFiscalYears` |

#### یادآوری عملیات پایان سال

`yearendreminder` · عملیات · `src/pages/company/CompanyOpsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchCalendarEvents` |
| **حسابداری** | `fetchFiscalYears` |

#### تقویم و یادآوری

`calendar` · عملیات · `src/pages/CalendarPage.tsx`

**تب‌ها:** کارهای امروز · تقویم ماهانه

| از | چه می‌گیرد |
|---|---|
| **سیستم** | `fetchAlerts` |
| **شرکت** | `fetchCalendarEvents` |

#### ارسال اطلاعات

`dataexport` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **سیستم** | `fetchBackupExport` |

#### دریافت اطلاعات

`dataimport` · فهرست · `src/pages/company/CompanyListPages.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### گزارش‌ساز

`reportbuilder` · فهرست · `src/pages/company/ReportBuilderPages.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### گزارش‌های پویا

`dynamicreports` · فهرست · `src/pages/company/ReportBuilderPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchSavedReports` |

#### فعالیت‌های روز

`dayactivity` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **سیستم** | `fetchAuditEntries` |

#### گزارش‌ها و نمودارهای مدیریتی

`mgmtreports` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **گزارش** | `fetchAging`، `fetchBalanceSheet`، `fetchCashFlow`، `fetchContactStatement`، `fetchEquityStatement`، `fetchIncomeStatement`، `fetchInventoryReport`، `fetchKardex`، `fetchSeasonalReport` |
| **حسابداری** | `fetchBudgetReport` |
| **طرف حساب** | `fetchContacts` |
| **شرکت** | `fetchCostCenterReport` |
| **کالا** | `fetchItemsLive` |

#### گزارش استفاده از نرم‌افزار

`usagereport` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **سیستم** | `fetchAuditSummary` |

#### طرف حساب‌ها

`contactlist` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchContactGroups`، `fetchGeoLocations` |
| **طرف حساب** | `fetchContacts` |

#### تراکنش‌های شریک

`ownertxnlist` · فهرست · `src/pages/company/OwnerTransactionListPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchOwnerTransactions`، `fetchPartnerBalances` |

#### افراد مرتبط

`relatedpeople` · فهرست · `src/pages/company/CompanyBasicsPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **طرف حساب** | `fetchContacts` |
| **شرکت** | `fetchRelatedPersons` |

#### قراردادهای اقساطی

`installmentplans` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchInstallmentPlans` |

#### همه اقساط

`allinstallments` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchInstallmentPlans` |

#### مراکز هزینه

`costcenterlist` · فهرست · `src/pages/company/CompanyListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchCostCenterReport` |

#### محل‌های جغرافیایی

`geolist` · فهرست · `src/pages/ledgers/ModuleListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchGeoLocations` |

#### گروه‌های طرف حساب

`contactgrouplist` · فهرست · `src/pages/ledgers/ModuleListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchContactGroups` |

#### رویدادهای تقویم

`calendarlist` · فهرست · `src/pages/ledgers/ModuleListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **شرکت** | `fetchCalendarEvents` |

---

### تنظیمات

#### سال مالی

`fiscalyear` · عملیات · `src/pages/FiscalYearPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchFiscalYearSuggestion`، `fetchFiscalYears` |

#### کدینگ

`coding` · عملیات · `src/pages/CodingPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchChartTemplates`، `fetchCodingRule`، `fetchDeletableAccounts` |

#### شخصی‌سازی

`personalization` · عملیات · `src/pages/PersonalizationPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **خزانه** | `fetchChequeControl` |
| **فروش** | `fetchSalesPosting` |
| **حسابداری** | `fetchTafsiliMode` |

#### روش‌های شماره‌گذاری

`numbering` · عملیات · `src/pages/NumberingPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **سیستم** | `fetchNumbering` |

#### کاربر جدید

`team` · عملیات · `src/pages/TeamPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **باشگاه مشتریان** | `fetchMembers`، `fetchPermissionModules`، `fetchRoles` |

#### تغییر کلمه عبور

`password` · عملیات · `src/pages/ChangePasswordPage.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### پشتیبان‌گیری خودکار

`backup` · عملیات · `src/pages/BackupPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **سیستم** | `fetchBackupExport` |

#### ظاهر و پوسته

`theme` · عملیات · `src/components/ThemeGallery.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### راهنما

`help` · عملیات · `src/pages/HelpPage.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### نسخه‌های پشتیبانی و بازیابی

`backuplist` · فهرست · `src/pages/BackupListPage.tsx`

_ورودیِ مستقیمی از بخش دیگری ندارد._

#### کاربران

`userlist` · فهرست · `src/pages/UserListPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **باشگاه مشتریان** | `fetchMembers`، `fetchPermissionModules`، `fetchRoles` |

#### سال‌های مالی

`fiscalyearlist` · فهرست · `src/pages/FiscalYearListPage.tsx`

| از | چه می‌گیرد |
|---|---|
| **حسابداری** | `fetchFiscalYears` |

#### روش‌های شماره‌گذاری

`numberinglist` · فهرست · `src/pages/ledgers/ModuleListPages.tsx`

| از | چه می‌گیرد |
|---|---|
| **سیستم** | `fetchNumbering` |

---

## پیوست — فرهنگِ ورودی‌ها

هر تابعِ `fetch*` و اندپوینتی که می‌خوانَد — برای وقتی که می‌خواهی بدانی یک ورودی
دقیقاً از کجای سرور می‌آید.

| تابع | اندپوینت | دامنه |
|---|---|---|
| `fetchAccountBalances` | `/api/accounting/balances` | حسابداری |
| `fetchAccountsLive` | `/api/accounts` | حسابداری |
| `fetchAdminAccounts` | `/api/admin/accounts` | سیستم |
| `fetchAdminPurchases` | `/api/admin/purchases` | سیستم |
| `fetchAging` | `/api/reports/aging` | گزارش |
| `fetchAlerts` | `/api/alerts` | سیستم |
| `fetchAllWarehouseReceipts` | `/api/warehouse-receipts` | انبار |
| `fetchAllocationHistory` | `/api/settlements/history` | خزانه |
| `fetchAllowedContractTypes` | `/api/payroll/contract-types` | حقوق |
| `fetchAnalyticLedger` | `/api/reports/general-ledger` | گزارش |
| `fetchAnalytics` | `/api/accounting/analytics` | حسابداری |
| `fetchAssetAssignments` | `/api/asset-assignments` | دارایی ثابت |
| `fetchAttendance` | `/api/attendance` | حقوق |
| `fetchAuditEntries` | `/api/audit` | سیستم |
| `fetchAuditSummary` | `/api/audit/summary` | سیستم |
| `fetchBackupExport` | `/api/backup/export` | سیستم |
| `fetchBalanceSheet` | `/api/reports/balance-sheet` | گزارش |
| `fetchBankAccountsAdmin` | `/api/bank-accounts` | خزانه |
| `fetchBankAccountsLive` | `/api/bank-accounts` | خزانه |
| `fetchBankTransactions` | `/api/bank-transactions` | خزانه |
| `fetchBatchSerials` | `/api/stock-batches` | انبار |
| `fetchBenefits` | `/api/payroll/benefits` | حقوق |
| `fetchBirthdays` | `/api/crm/birthdays` | باشگاه مشتریان |
| `fetchBoms` | `/api/boms` | تولید |
| `fetchBudgetLines` | `/api/budgets` | حسابداری |
| `fetchBudgetReport` | `/api/budgets/report` | حسابداری |
| `fetchBundles` | `/api/sales-ops/bundles` | فروش |
| `fetchCalendarEvents` | `/api/calendar-events` | شرکت |
| `fetchCartable` | `/api/accounting/cartable` | حسابداری |
| `fetchCashFlow` | `/api/reports/cash-flow` | گزارش |
| `fetchCashboxes` | `/api/cashboxes` | خزانه |
| `fetchChartAccounts` | `/api/accounts` | حسابداری |
| `fetchChartSetup` | `/api/accounts/setup-status` | حسابداری |
| `fetchChartTemplates` | `/api/accounts/templates` | حسابداری |
| `fetchCheckOperations` | `/api/check-operations` | خزانه |
| `fetchCheckSummary` | `/api/checks/summary` | خزانه |
| `fetchCheckTimeline` | `/api/checks` | خزانه |
| `fetchCheckbookLeaves` | `/api/checkbooks` | خزانه |
| `fetchCheckbooks` | `/api/checkbooks` | خزانه |
| `fetchChecks` | `/api/checks` | خزانه |
| `fetchChequeControl` | `/api/cheque-number-control` | خزانه |
| `fetchClosingPreview` | `/api/accounting/closing-entry/preview` | حسابداری |
| `fetchCodingRule` | `/api/accounts/coding-rule` | حسابداری |
| `fetchCommissionPreview` | `/api/sales-ops/commission/preview` | فروش |
| `fetchCommissionRules` | `/api/sales-ops/commission-rules` | فروش |
| `fetchCommissionRuns` | `/api/sales-ops/commission/runs` | فروش |
| `fetchContactAddresses` | `/api/contacts` | طرف حساب |
| `fetchContactChannels` | `/api/contacts` | طرف حساب |
| `fetchContactGroups` | `/api/company/groups` | شرکت |
| `fetchContactSettlement` | `/api/settlements` | خزانه |
| `fetchContactSettlements` | `/api/settlements` | خزانه |
| `fetchContactStatement` | `/api/reports/contact-statement` | گزارش |
| `fetchContactTafsiliRequirement` | `/api/contacts/tafsili-requirement` | طرف حساب |
| `fetchContactTier` | `/api/crm/loyalty/tier` | باشگاه مشتریان |
| `fetchContacts` | `/api/contacts` | طرف حساب |
| `fetchContractAmendments` | `/api/contracting/amendments` | پیمانکاری |
| `fetchContractSettlements` | `/api/contracting/settlements` | پیمانکاری |
| `fetchContractStatements` | `/api/contracting/statements` | پیمانکاری |
| `fetchContracts` | `/api/contracting/contracts` | پیمانکاری |
| `fetchCostCenterAnalysis` | `/api/cost-centers` | شرکت |
| `fetchCostCenterBudget` | `/api/cost-centers` | شرکت |
| `fetchCostCenterLedger` | `/api/cost-centers` | شرکت |
| `fetchCostCenterReport` | `/api/cost-centers/report` | شرکت |
| `fetchCostCenters` | `/api/cost-centers` | شرکت |
| `fetchCounterpartyAccounts` | `/api/settlements/accounts` | خزانه |
| `fetchCounterpartyEventLines` | `/api/reports/counterparty` | گزارش |
| `fetchCounterpartyEvents` | `/api/reports/counterparty` | گزارش |
| `fetchCounterpartySummary` | `/api/reports/counterparty` | گزارش |
| `fetchCreditStatus` | `/api/contacts` | طرف حساب |
| `fetchCrmActivities` | `/api/crm/activities` | باشگاه مشتریان |
| `fetchCurrencies` | `/api/currencies` | حسابداری |
| `fetchCustoms` | `/api/sales-ops/customs` | فروش |
| `fetchDeletableAccounts` | `/api/accounts/deletable` | حسابداری |
| `fetchDeploymentInfo` | `/api/payroll-deployment` | حقوق |
| `fetchDepreciationEntries` | `/api/depreciation` | دارایی ثابت |
| `fetchDiscountGroups` | `/api/sales-ops/discount-groups` | فروش |
| `fetchEarlySettlement` | `/api/installment-plans` | شرکت |
| `fetchEligibleReceivedCheques` | `/api/payments/eligible-received-cheques` | خزانه |
| `fetchEmployeeCandidates` | `/api/payroll/employee-candidates` | حقوق |
| `fetchEmployeeLoans` | `/api/employee-loans` | حقوق |
| `fetchEmployees` | `/api/employees` | حقوق |
| `fetchEquityStatement` | `/api/reports/equity-statement` | گزارش |
| `fetchFactorInputs` | `/api/payroll-periods` | حقوق |
| `fetchFiscalYearSuggestion` | `/api/fiscal-years/suggest` | حسابداری |
| `fetchFiscalYears` | `/api/fiscal-years` | حسابداری |
| `fetchFixedAssets` | `/api/fixed-assets` | دارایی ثابت |
| `fetchFxPreview` | `/api/accounting/fx-revaluation/preview` | حسابداری |
| `fetchGeneralLedger` | `/api/reports/general-ledger` | گزارش |
| `fetchGeoLocations` | `/api/company/locations` | شرکت |
| `fetchIncomeStatement` | `/api/reports/income-statement` | گزارش |
| `fetchInstallmentPlans` | `/api/installment-plans` | شرکت |
| `fetchInstallmentSummary` | `/api/installment-plans/summary` | شرکت |
| `fetchInsuranceTaxBranches` | `/api/insurance-tax-branches` | حقوق |
| `fetchIntegrityReport` | `/api/reports/integrity` | گزارش |
| `fetchInventoryBreakdown` | `/api/reports/inventory-breakdown` | گزارش |
| `fetchInventoryReport` | `/api/reports/inventory` | گزارش |
| `fetchIssueInvoiceContext` | `/api/warehouse-issues` | انبار |
| `fetchIssueReturn` | `/api/warehouse-issue-returns` | انبار |
| `fetchIssueReturnBasis` | `/api/warehouse-issue-returns/basis` | انبار |
| `fetchIssueReturnBasisDetail` | `/api/warehouse-issue-returns/basis` | انبار |
| `fetchIssueReturnLedger` | `/api/warehouse-issue-returns` | انبار |
| `fetchItemAttributes` | `/api/item-attributes` | کالا |
| `fetchItemGroups` | `/api/item-groups` | کالا |
| `fetchItemsLive` | `/api/items` | کالا |
| `fetchItemsWithPricingLive` | `/api/items` | کالا |
| `fetchJobTitles` | `/api/job-titles` | حقوق |
| `fetchJournalEntries` | `/api/journal-entries` | حسابداری |
| `fetchJournalEntriesFiltered` | `/api/journal-entries` | حسابداری |
| `fetchJournalEntry` | `/api/journal-entries` | حسابداری |
| `fetchKardex` | `/api/reports/kardex` | گزارش |
| `fetchLatestRate` | `/api/currencies/rates/latest` | حسابداری |
| `fetchLeads` | `/api/crm/leads` | باشگاه مشتریان |
| `fetchLegalBook` | `/api/accounting/legal-book` | حسابداری |
| `fetchLoanTypes` | `/api/loan-types` | حقوق |
| `fetchLowStock` | `/api/stock/low` | انبار |
| `fetchLoyaltyBalances` | `/api/crm/loyalty` | باشگاه مشتریان |
| `fetchLoyaltySettings` | `/api/crm/loyalty/settings` | باشگاه مشتریان |
| `fetchLoyaltyTransactions` | `/api/crm/loyalty/transactions` | باشگاه مشتریان |
| `fetchMaterialVariance` | `/api/production-reports/material-variance` | تولید |
| `fetchMembers` | `/api/members` | باشگاه مشتریان |
| `fetchMissingTafsili` | `/api/reports/missing-tafsili` | گزارش |
| `fetchMoadianPending` | `/api/moadian/pending` | مؤدیان |
| `fetchMoadianReadiness` | `/api/moadian/readiness` | مؤدیان |
| `fetchMoadianSettings` | `/api/moadian/settings` | مؤدیان |
| `fetchMoadianSubmissions` | `/api/moadian/submissions` | مؤدیان |
| `fetchMoadianUnitMaps` | `/api/moadian/unit-maps` | مؤدیان |
| `fetchMoadianUnmappedUnits` | `/api/moadian/unmapped-units` | مؤدیان |
| `fetchModules` | `/api/modules` | سیستم |
| `fetchMpCatalog` | `/api/marketplace/retailer/catalog` | بازارگاه |
| `fetchMpCommissionOverview` | `/api/marketplace/admin/commissions/overview` | بازارگاه |
| `fetchMpCommissions` | `/api/marketplace/admin/commissions` | بازارگاه |
| `fetchMpDistributorConnections` | `/api/marketplace/distributor/connections` | بازارگاه |
| `fetchMpDistributorOrders` | `/api/marketplace/distributor/orders` | بازارگاه |
| `fetchMpDistributorReturns` | `/api/marketplace/distributor/returns` | بازارگاه |
| `fetchMpDistributors` | `/api/marketplace/retailer/distributors` | بازارگاه |
| `fetchMpListings` | `/api/marketplace/distributor/listings` | بازارگاه |
| `fetchMpMessages` | `/api/marketplace/connections` | بازارگاه |
| `fetchMpOrderMessages` | `/api/marketplace/orders` | بازارگاه |
| `fetchMpRetailerConnections` | `/api/marketplace/retailer/connections` | بازارگاه |
| `fetchMpRetailerOrders` | `/api/marketplace/retailer/orders` | بازارگاه |
| `fetchMpRetailerReturns` | `/api/marketplace/retailer/returns` | بازارگاه |
| `fetchMpSettings` | `/api/marketplace/distributor/settings` | بازارگاه |
| `fetchMpUnread` | `/api/marketplace/unread` | بازارگاه |
| `fetchMpZones` | `/api/marketplace/distributor/zones` | بازارگاه |
| `fetchMyMpCommissions` | `/api/marketplace/distributor/commissions` | بازارگاه |
| `fetchNativeStorefront` | `/api/storefront` | فروشگاه |
| `fetchNatureViolations` | `/api/reports/nature-violations` | گزارش |
| `fetchNextAccountCode` | `/api/accounts/next-code` | حسابداری |
| `fetchNextCheckNumber` | `/api/checkbooks` | خزانه |
| `fetchNote` | `/api/sales-ops/notes` | فروش |
| `fetchNoteAccounts` | `/api/sales-ops/notes/accounts` | فروش |
| `fetchNoteDuplicateDraft` | `/api/sales-ops/notes` | فروش |
| `fetchNotes` | `/api/sales-ops/notes` | فروش |
| `fetchNumbering` | `/api/numbering` | سیستم |
| `fetchOpenItems` | `/api/settlements/open-items` | خزانه |
| `fetchOpeningPreview` | `/api/accounting/opening-entry/preview` | حسابداری |
| `fetchOpeningStatus` | `/api/opening-balances/status` | حسابداری |
| `fetchOverStock` | `/api/stock/over` | انبار |
| `fetchOwnerTransactions` | `/api/owner-transactions` | شرکت |
| `fetchPartnerBalances` | `/api/owner-transactions/partner-balances` | شرکت |
| `fetchPaymentDocuments` | `/api/payments` | خزانه |
| `fetchPayrollFactors` | `/api/payroll-factors` | حقوق |
| `fetchPayrollPeriods` | `/api/payroll-periods` | حقوق |
| `fetchPayrollSettings` | `/api/payroll-settings` | حقوق |
| `fetchPayrollTaxGroups` | `/api/payroll-tax-groups` | حقوق |
| `fetchPayslipLedger` | `/api/payslips` | حقوق |
| `fetchPayslips` | `/api/payslips` | حقوق |
| `fetchPeriodCloses` | `/api/fiscal-period-closes` | حسابداری |
| `fetchPermissionModules` | `/api/members/permission-modules` | باشگاه مشتریان |
| `fetchPettyCashBalance` | `/api/petty-cash/balance` | خزانه |
| `fetchPettyCashTransactions` | `/api/petty-cash` | خزانه |
| `fetchPnlClosePreview` | `/api/accounting/pnl-close/preview` | حسابداری |
| `fetchPosPending` | `/api/pos-settlements/pending` | خزانه |
| `fetchPosSettlement` | `/api/pos-settlements` | خزانه |
| `fetchPosSettlementPreview` | `/api/pos-settlements/preview` | خزانه |
| `fetchPosSettlements` | `/api/pos-settlements` | خزانه |
| `fetchPosTerminals` | `/api/pos-terminals` | خزانه |
| `fetchPreinvoiceProgress` | `/api/reports/sales-review/preinvoices` | گزارش |
| `fetchPriceAnnouncements` | `/api/sales-ops/price-announcements` | فروش |
| `fetchPriceListItems` | `/api/price-lists` | قیمت‌گذاری |
| `fetchPriceLists` | `/api/price-lists` | قیمت‌گذاری |
| `fetchPricingFactors` | `/api/sales-ops/pricing-factors` | فروش |
| `fetchPricingSuggestion` | `/api/sales-ops/pricing/suggest` | فروش |
| `fetchProductionCostReport` | `/api/production-reports/cost` | تولید |
| `fetchProductionKardex` | `/api/production-reports/kardex` | تولید |
| `fetchProductionOrders` | `/api/production-orders` | تولید |
| `fetchProductionPlans` | `/api/production-plans` | تولید |
| `fetchPurchaseDeductionTypes` | `/api/purchase-deduction-types` | خرید |
| `fetchPurchaseInvoiceDuplicate` | `/api/purchase-invoices` | خرید |
| `fetchPurchaseInvoices` | `/api/purchase-invoices` | خرید |
| `fetchPurchaseInvoicesOfKind` | `/api/purchase-invoices` | خرید |
| `fetchPurchasePriceInfo` | `/api/purchase-price-info` | خرید |
| `fetchPurchaseReturnable` | `/api/purchase-invoices` | خرید |
| `fetchPurchaseReturns` | `/api/purchase-returns` | خرید |
| `fetchPurchaseSummary` | `/api/purchase-invoices/summary` | خرید |
| `fetchRates` | `/api/currencies/rates` | حسابداری |
| `fetchReceiptDocument` | `/api/receipts` | خزانه |
| `fetchReceiptDocuments` | `/api/receipts` | خزانه |
| `fetchReceiptDuplicate` | `/api/receipts` | خزانه |
| `fetchReceiptPaymentContext` | `/api/warehouse-receipts` | انبار |
| `fetchReceiptReturnable` | `/api/warehouse-receipts` | انبار |
| `fetchReclassSources` | `/api/accounting/balance-reclass/sources` | حسابداری |
| `fetchReconciliationSummary` | `/api/bank-accounts` | خزانه |
| `fetchRecurringEntries` | `/api/recurring-entries` | حسابداری |
| `fetchRelatedPersons` | `/api/company/persons` | شرکت |
| `fetchRenumberPreview` | `/api/accounting/entries/renumber/preview` | حسابداری |
| `fetchReturnable` | `/api/sales-invoices` | فروش |
| `fetchRewards` | `/api/crm/loyalty/rewards` | باشگاه مشتریان |
| `fetchRoles` | `/api/members/roles` | باشگاه مشتریان |
| `fetchSalaryContracts` | `/api/salary-contracts` | حقوق |
| `fetchSaleTypes` | `/api/sales-ops/sale-types` | فروش |
| `fetchSalesByCustomer` | `/api/reports/sales-review/customers` | گزارش |
| `fetchSalesByItem` | `/api/reports/sales-review/items` | گزارش |
| `fetchSalesByWarehouse` | `/api/reports/sales-review/warehouses` | گزارش |
| `fetchSalesDashboard` | `/api/reports/dashboard` | گزارش |
| `fetchSalesInvoices` | `/api/sales-invoices` | فروش |
| `fetchSalesPosting` | `/api/sales-invoice-posting` | فروش |
| `fetchSalesQuotations` | `/api/sales-quotations` | فروش |
| `fetchSalesReturnReasons` | `/api/sales-return-reasons` | فروش |
| `fetchSalesReturns` | `/api/sales-returns` | فروش |
| `fetchSalesReviewDocuments` | `/api/reports/sales-review/documents` | گزارش |
| `fetchSalesReviewLines` | `/api/reports/sales-review/lines` | گزارش |
| `fetchSalesReviewSummary` | `/api/reports/sales-review/summary` | گزارش |
| `fetchSalesSummary` | `/api/sales-invoices/summary` | فروش |
| `fetchSavedReports` | `/api/company/reports` | شرکت |
| `fetchSeasonalReport` | `/api/reports/seasonal` | گزارش |
| `fetchSegments` | `/api/crm/segments` | باشگاه مشتریان |
| `fetchServiceLocations` | `/api/service-locations` | حقوق |
| `fetchSettlements` | `/api/payroll-settlements` | حقوق |
| `fetchStatementLines` | `/api/bank-accounts` | خزانه |
| `fetchStockAdjustments` | `/api/stock-adjustments` | انبار |
| `fetchStockBatches` | `/api/stock-batches` | انبار |
| `fetchStockCount` | `/api/stock-counts` | انبار |
| `fetchStockCountDrift` | `/api/stock-counts` | انبار |
| `fetchStockCounts` | `/api/stock-counts` | انبار |
| `fetchStockLevels` | `/api/stock` | انبار |
| `fetchStockTransfers` | `/api/stock-transfers` | انبار |
| `fetchStorefrontGateways` | `/api/storefront/gateways` | فروشگاه |
| `fetchStorefrontItems` | `/api/storefront/items` | فروشگاه |
| `fetchStorefrontOrders` | `/api/storefront/orders` | فروشگاه |
| `fetchStorefrontSettings` | `/api/integration/settings` | فروشگاه |
| `fetchSubscription` | `/api/subscription` | سیستم |
| `fetchTafsiliMode` | `/api/accounts/tafsili-mode` | حسابداری |
| `fetchTaxBreakdown` | `/api/payslips` | حقوق |
| `fetchTaxTables` | `/api/tax-tables` | حقوق |
| `fetchTierMembers` | `/api/crm/loyalty/tier-members` | باشگاه مشتریان |
| `fetchTiers` | `/api/crm/loyalty/tiers` | باشگاه مشتریان |
| `fetchTreasuryTransactions` | `/api/treasury` | خزانه |
| `fetchTrialBalance` | `/api/reports/trial-balance` | گزارش |
| `fetchUnits` | `/api/units` | کالا |
| `fetchUnpricedOutputs` | `/api/warehouse-receipts/unpriced` | انبار |
| `fetchValuationPreview` | `/api/inventory-valuation/preview` | انبار |
| `fetchValuationRunList` | `/api/inventory-valuation/runs` | انبار |
| `fetchVatReport` | `/api/reports/vat` | گزارش |
| `fetchWarehouseIssue` | `/api/warehouse-issues` | انبار |
| `fetchWarehouseIssueLedger` | `/api/warehouse-issues` | انبار |
| `fetchWarehouseIssues` | `/api/sales-invoices` | فروش |
| `fetchWarehouseReceipts` | `/api/purchase-invoices` | خرید |
| `fetchWarehouseStock` | `/api/warehouses` | انبار |
| `fetchWarehousesAdmin` | `/api/warehouses` | انبار |
| `fetchWarehousesLive` | `/api/warehouses` | انبار |
