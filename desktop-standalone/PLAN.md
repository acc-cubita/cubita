# اپلیکیشنِ حسابداریِ محلیِ دسکتاپ (نسخه‌ی فروشی) — نقشه‌ی معماری و اجرا

> پوشه‌ی جدا در همین مخزن. محصولِ **جدا از کوبیتا**. این سند مرجعِ تصمیم‌ها و نقشه‌ی راه است؛
> با هر پیشرفت به‌روز شود (مثلِ `PROJECT_OVERVIEW.md`).

## Context — چرا و چیست
یک نرم‌افزارِ حسابداریِ **دسکتاپیِ محلی‌محور** و **فروشی (خریدِ یک‌باره، جعبه‌ای)** که ظاهر و
ساختارش **خیلی شبیهِ سپیدار** است. کامل‌ترین ماژول‌های حسابداری **مثلِ کوبیتا، منهای «اتصال فروشگاه»**.
داده روی **سیستمِ خودِ کاربر** ذخیره می‌شود؛ فقط ماژول‌های نیازمندِ اینترنت (مثلِ **مؤدیان**) آنلاین
کار می‌کنند. دسکتاپ‌محور (Electron)، همان استکِ کوبیتا.

## تصمیم‌های تأییدشده‌ی کاربر
1. **رویکرد = ترکیبی:** بازاستفاده از **منطق/ماژول‌های حسابداریِ کوبیتا** + **شل/ظاهرِ نوِ شبیهِ سپیدار**.
2. **محل = پوشه‌ی جدا در همین مخزن** (`desktop-standalone/`).
3. **پلتفرم = فقط دسکتاپ.**
4. **موتورِ حسابداری = بسته‌بندیِ همان بک‌اندِ FastAPIِ پایتون + SQLite، محلی** (نه Postgres/ابری).

## یافته‌ی کلیدیِ کاوش (مبنای طراحی)
برنامه‌ی فعلیِ کوبیتا یک **کلاینتِ نازکِ ابری (SaaS)** است: کلِ موتورِ حسابداری (دفترِ کل،
شماره‌گذاریِ اسناد، بهای تمام‌شده، گزارش‌ها، حقوق و…) سمتِ **سرور** (FastAPI + Postgres) است. فقط ۴
ماژولِ نوشتاری (سند، فاکتور فروش/خرید، چک) صفِ آفلاین دارند، و **بازکردنِ برنامه هم بدونِ لاگینِ ابری
ممکن نیست**. پس اپِ محلی باید موتور را **محلی** اجرا کند.

## معماریِ هدف
- **Electron main** یک فرایندِ **FastAPIِ محلی (سایدکار)** را روی یک پورتِ `127.0.0.1` بالا می‌آورد
  (پایتونِ بسته‌بندی‌شده با PyInstaller، به‌صورتِ یک exe کنارِ اپ).
- **React UI** (کپیِ ماژول‌های کوبیتا) به‌جای `acc.cubita.ir` به همان `http://127.0.0.1:<port>` وصل می‌شود.
- **SQLite** در `app.getPath('userData')/data/*.db` (تک‌کاربر، بدونِ RLS/چندمستأجری).
- **مؤدیان** تنها ماژولی است که به اینترنت (سرورِ مالیات) وصل می‌شود.

## بازاستفاده / حذف / افزودن
### بازاستفاده (Reuse)
- **کلِ منطقِ بک‌اند:** `backend/app/services/*` (journal/double-entry, invoices, inventory costing,
  banking/checks/reconciliation, payroll, period_close, reports, treasury, contacts, crm, moadian).
- **کلِ UIِ ماژول‌ها:** `desktop/src/pages/*` و `desktop/src/components/*`.
- **بسته‌بندیِ Electron:** NSIS installer، `electron-updater` (کانالِ self-hosted)، مدیریتِ نیتیوِ
  `better-sqlite3` — همه قابلِ انتقال (`desktop/electron/*`، `desktop/package.json` بخشِ build، `desktop/scripts/*`).
- **طراحیِ سپیدار:** پشتیبان در `…/scratchpad/sepidar-skin-backup/` (App.css, index.css, theme.ts,
  main.tsx, Sidebar.tsx, Dashboard.tsx, sepidarMenu.ts, icons/) به‌عنوانِ شل/ظاهرِ اپِ جدید.

### حذف (Strip — لایه‌ی SaaS/ابری)
- **اتصال فروشگاه:** `IntegrationPanel`, `NativeStorefrontPanel`, `StorefrontGallery` + APIهای storefront.
- **ورود/ثبت‌نامِ ابری:** `LoginScreen`, `SignupScreen`, `SetPasswordScreen` (سمتِ سرور).
- **اشتراک/ترایال/صورتحساب:** `TrialBanner`, `SubscriptionBanner`, `TrialExpiredScreen`, `FeatureUpsell`.
- **چندمستأجری/RLS/ادمینِ پلتفرم/تیم/membership** در بک‌اند (تبدیل به تک‌کاربرِ محلی).
- **لایه‌ی sync ابری:** `desktop/electron/sync.ts` + `pullAll/pushOutbox` + `API_BASE_URL`ها — حذف یا
  تبدیل به «ماژولِ آنلاینِ اختیاری» (فقط برای مؤدیان/به‌روزرسانی).

### افزودن (Add — تازه‌ساز)
- اسپاون و مدیریتِ **سایدکارِ FastAPI** از Electron main + سلامت‌سنجیِ پورت.
- پیکربندیِ **SQLite تک‌مستأجر** در بک‌اند (به‌جای Postgres).
- **ورودِ محلی** (بدونِ سرورِ ابری): بدونِ لاگین یا یک قفلِ محلیِ ساده.
- **لایسنس/فعال‌سازیِ آفلاین** (اکنون هیچ کدِ لایسنس/DRM وجود ندارد — باید ساخته شود).

## نکاتِ فنیِ مهم
- بک‌اند به Postgres وابسته است (RLS، ستِ tenant در سشن، احتمالاً SQL/نوع/تریگرِ خاص). برای SQLite:
  حذفِ RLS (تک‌کاربر لازم ندارد)، پورتِ هر SQLِ Postgres-only، بازبینیِ مهاجرت‌ها.
- شماره‌گذاریِ اسناد که سمتِ سرور بود، حالا محلی و مستقیم (بدونِ صفِ آفلاینِ ابری).
- برای نسخه‌ی فروشی، **امضای کدِ نصبی (code signing)** توصیه می‌شود (اکنون امضا نمی‌شود؛ به‌روزرسانی فقط با HTTPS محافظت می‌شود).
- `better-sqlite3` فقط `x64/win32` prebuild دارد (`desktop/scripts/rebuild-native.mjs`).

## نقشه‌ی راهِ مرحله‌ای
- **M0 — Scaffold ✅ (2026-08-07):** `desktop-standalone/` ساخته شد: `app/` = فورکِ فرانتِ Electronِ
  کوبیتا (۱۱۲ فایلِ src + electron/ + public/ + configs، بدونِ node_modules/dist/release)، `engine/` =
  فورکِ بک‌اند (۱۷۶ فایلِ app + alembic/ + tests، بدونِ venv/__pycache__/رازها). `app/package.json`
  هویتِ مستقل گرفت: name=`hesabdari-standalone`, version=`0.1.0`, appId=`ir.ipnetcity.hesabdari-standalone`,
  productName=`Hesabdari` (placeholder برای رِبرند). فایل‌های زائدِ log/tmp پاک شدند.
- **M1 — بک‌اندِ محلی روی SQLite تک‌مستأجر ✅ (2026-08-07):**
  - `engine/app/sqlite_compat.py` (نو): شیمِ `JSONB→JSON` روی SQLite (تنها نوعِ ناسازگار؛ `UUID` خودش کار می‌کند).
  - `database.py`: تشخیصِ SQLite + `connect_args(check_same_thread=False)` + `PRAGMA foreign_keys=ON` + importِ شیم.
  - `tenant_context.py`: `set_config`/RLS فقط روی Postgres اجرا می‌شود (روی SQLite no-op)؛ مهرِ `tenant_id` روی
    ردیف‌های جدید (`before_flush`) دست‌نخورده کار می‌کند → تک‌مستأجرِ محلی بدونِ RLS درست است.
  - `config.py`: پیش‌فرضِ `database_url` = SQLite محلی (Electron با `DATABASE_URL` بازنویسی می‌کند).
  - `local_bootstrap.py` (نو): `create_all` (بدونِ alembic روی SQLite) + seedِ اکانتِ پیش‌فرضِ محلی اگر خالی باشد
    (`owner@hesabdari.ir`). `run_local.py` (نو): نقطه‌ی ورودِ سایدکار (bootstrap + `uvicorn` روی `127.0.0.1:$PORT`).
  - **راستی‌آزمایی (با venvِ بک‌اند):** `create_all` هر ۸۴ جدول را روی SQLite ساخت؛ seed یک مستأجر/کاربر/۳۳ حساب/۲
    انبار ساخت (پس نوشتنِ تراکنشی روی SQLite کار می‌کند)؛ کلِ اپ با ۲۶۹ روت زیرِ SQLite import شد.
  - **کاواتِ باقی‌مانده:** بعضی سرویس‌ها ممکن است SQLِ خاصِ Postgres داشته باشند (date_trunc، ON CONFLICT،
    عملگرهای JSON، `::uuid`، DISTINCT ON) که هنگامِ اجرای هر ماژول باید ماژول‌به‌ماژول پورت شود.
- **M2 — سایدکار: اسپاونِ FastAPI از Electron + اتصالِ UI ✅ (2026-08-07):**
  - **راستی‌آزماییِ M1 به‌صورتِ زنده:** سرورِ محلی بالا آمد؛ health/login/`me`/accounts/گزارش‌ها همه کار کردند.
    مسیرِ **نوشتن** هم تأیید شد: سندِ حسابداری با شماره‌ی خودکارِ #۱ ثبت شد و تراز آزمایشی درست بازتاب داد؛
    متنِ فارسیِ بدنه‌ی درخواست (UTF-8) کامل round-trip شد.
  - **باگِ قابلیتِ حمل که پیدا و رفع شد:** `services/numbering.py` در SQLِ خام `str(uuid)` (۳۶ کاراکترِ
    خط‌تیره‌دار) را بایند می‌کرد، ولی ORM روی SQLite UUID را ۳۲‌hexِ بی‌خط‌تیره ذخیره می‌کند → هیچ‌وقت match
    نمی‌شد و «شمارنده ساخته نشده» می‌داد (Postgres هر دو را نرمال می‌کرد). رفع با هلپرِ `uuid_param()` در
    `sqlite_compat.py` (نرمال‌سازی به ۳۲‌hex؛ قابلِ قبول برای هر دو دیالکت). الگو برای هر SQLِ خامِ آینده.
  - **`electron/sidecar.ts` (نو):** پورتِ آزادِ پویا، اسپاونِ `run_local.py` (dev: پایتونِ venvِ بک‌اند؛
    packaged: exeِ PyInstaller در `resources/engine` — در M5)، تنظیمِ `DATABASE_URL` در `userData/data/hesabdari.db`،
    `ALLOWED_ORIGINS=*` (loopback + Bearer، پس امن) و `PYTHONUTF8=1`، انتظار تا سبزشدنِ `/api/health`
    (با fail-fast اگر پردازه بمیرد)، و `stopSidecar` روی `will-quit`.
  - **`electron/main.ts`:** پیش از ساختِ پنجره سایدکار را بالا می‌آورد، `API_BASE_URL` را با پورتِ واقعی ست
    می‌کند و از راهِ `additionalArguments` به renderer می‌دهد؛ شکستِ `initLocalDb`ِ قدیمی دیگر جلوی اجرا را
    نمی‌گیرد (try/catch؛ در M3 حذف می‌شود).
  - **`electron/preload.ts` + `src/api.ts` + `electron.d.ts`:** آدرسِ پایه از `window.hesabdariEnv.apiBaseUrl`
    خوانده می‌شود (منبعِ یگانه = پورتی که main گرفت)، با fallback به VITE_API_URL/پیش‌فرضِ محلی.
  - **راستی‌آزمایی:** `npm run build` (tsc + vite) سبز — main.js/preload.js/رندرر همه کامپایل شدند. اجرای زنده‌ی
    Electron (نسخه‌ی build): لاگِ راه‌اندازی نشان داد سایدکار روی پورتِ پویا (۶۲۳۴۹) اسپاون شد، health سبز شد،
    آدرس به renderer رفت، `dist/index.html` لود شد (`did-finish-load`)، و همان سایدکار login را روی دیتابیسِ
    واقعیِ `userData` (۱.۶MB، seed‌شده) سرو کرد. کاواتِ `better-sqlite3` (عدمِ تطبیقِ ABIِ Electron 42) بی‌اثر بود
    چون کش/صفِ قدیمی در M3 حذف می‌شود و کد نبودش را تحمل می‌کند.
  - **یادداشتِ dev:** برای `npm run dev`/اجرای مستقیمِ Electron باید `ELECTRON_RUN_AS_NODE` در محیط نباشد (وگرنه
    electron مثلِ Node اجرا می‌شود و `app` undefined است)؛ `scripts/dev.mjs` این را حذف می‌کند.
- **M2.5 — پیوندِ مستقیم (به‌جای صفِ آفلاینِ ابری): ✅ در M3d انجام شد** (۴ فرم مستقیم به سایدکار می‌نویسند؛ لایه‌ی outbox/sync حذف شد).
- **M3 — پاک‌سازیِ UI + حذفِ لایه‌ی SaaS/آفلاین ✅ (2026-08-07):**
  - **M3a ورودِ محلی:** `App.tsx` دیگر صفحه‌ی ورود/ثبت‌نام/بازیابی و نوارهای ترایال/اشتراک ندارد؛ هنگامِ باز
    شدن خودکار با اکانتِ محلیِ seed‌شده لاگین می‌کند (`localAuth.ts`) و مستقیم به داشبورد می‌رود (اسپلش +
    حالتِ خطا با «تلاش دوباره»). زنجیره‌ی توکن/principalِ بک‌اند دست‌نخورده بازاستفاده شد.
  - **M3b فروشگاه حذف شد:** ماژولِ «اتصال فروشگاه» از nav (Sidebar)، مسیریابیِ Dashboard، `moduleSections`،
    و راهنما (HelpPage) پاک شد؛ فایل‌های `IntegrationPanel`/`NativeStorefrontPanel`/`StorefrontGallery` حذف شدند.
  - **M3c ترایال/اشتراک/ادمین/تیم حذف شد:** فایل‌های `TrialBanner`/`SubscriptionBanner`/`TrialExpiredScreen`/
    `FeatureUpsell`/`PurchasesAdminPanel`/`AccountsAdminPage`/`TeamPage` و صفحاتِ ورودِ ابری
    (`LoginScreen`/`SignupScreen`/`SetPasswordScreen`) حذف شدند؛ گیت‌های `billing`/`accounts`/`team` و پلامبینگِ
    `is_platform_admin`/`is_super_admin` از Sidebar/Dashboard برداشته شد؛ تبِ مؤدیان دیگر پشتِ upsell قفل نیست.
  - **M3d داده مستقیم (نه صف/کشِ آفلاین):** ۴ فرم (سند/فاکتور فروش‌وخرید/چک) حالا فقط مستقیم به سایدکار می‌نویسند
    (شاخه‌ی `window.cubita.queue*` حذف شد)؛ Dashboard داده‌های مرجع را همیشه زنده می‌خواند (`refreshReferenceData`)؛
    کارت‌های «صف ارسال‌نشده» و دکمه‌ی «هم‌گام‌سازی» رفتند. کلِ لایه‌ی آفلاین حذف شد: `electron/db.ts`، `electron/sync.ts`،
    `electron/test-sync.ts`، هندلرهای IPCِ صف/کش، پلِ `cubita` در preload/‏`electron.d.ts`، وابستگیِ `better-sqlite3`
    (+ asarUnpack/allowScripts/rebuild-native/externalِ vite). `isElectron` حالا به `window.windowControls` گره خورده
    (نه `window.cubita`) تا حذفِ پلِ داده، پوسته‌ی دسکتاپ (نوار عنوان/به‌روزرسانی) را نشکند.
  - **راستی‌آزمایی:** `npm run build` سبز. اجرای زنده‌ی build: لاگ نشان داد auto-login (`POST /api/auth/login`→۲۰۰،
    `GET /api/auth/me`→۲۰۰) بدونِ صفحه‌ی ورود، رندرر بدونِ کرش مانت شد و `refreshReferenceData` مستقیم
    `/api/accounts`،`/api/warehouses`،`/api/items`،`/api/bank-accounts` و گزارش‌های داشبورد را (همه ۲۰۰) از سایدکار خواند.
  - **پاک‌سازیِ باقی‌مانده (کم‌اولویت، بی‌اثر بر عملکرد):** توابعِ مرده‌ی storefront/subscription/admin/member در
    `api.ts` هنوز هستند (unused export، بی‌ضرر)؛ برندِ سایدبار هنوز «کوبیتا/C» است (تا انتخابِ نامِ محصول در TBD)؛
    دکمه‌ی «خروج» فعلاً دوباره auto-login می‌کند (تا قفلِ محلیِ M6).
- **M4 — طراحیِ سپیدار ردّ شد؛ هویتِ تازه‌ی «دفترِ آرام» ✅ (2026-08-07):**
  - **مهم — پیوت:** کاربر شلِ سپیدار را **قاطعانه رد کرد** («اصلاً خوب نیست… نمی‌خوام شبیهِ برنامه‌ی قبلی باشه… بهم‌ریخته‌ست»)
    و **طراحیِ کاملاً تازه** خواست. پس هر چه از پشتیبانِ سپیدار آمده بود **کاملاً حذف شد** و یک هویتِ نو ساخته شد.
    **درسِ کلیدی برای آینده: از بازگردانیِ طرحِ سپیدارِ قبلی پرهیز کن؛ محصولِ جدید نباید شبیهِ برنامه‌ی قبلی باشد.**
  - **روند:** به‌جای حدسِ دوباره در کد، اول یک **ماکتِ بصریِ HTML** (Artifact) از طرحِ پیشنهادی ساخته و به کاربر نشان داده شد؛
    کاربر تأیید کرد («خوبه انجام بده»)، بعد روی برنامه پیاده شد.
  - **حذفِ کاملِ سپیدار:** `icons/`، `sepidarMenu.ts`، بلوک‌های CSSِ `[data-skin='sepidar']` در index.css/App.css، ماشینِ اسکین در
    `theme.ts`/`main.tsx`، و رندرِ سپیدار + نوارِ وضعیت در Sidebar/Dashboard — همه پاک شدند.
  - **هویتِ «دفترِ آرام»:** آرام و جادار (ضدِ شلوغی). لهجه = **سبزآبیِ عمیق** (`#0e7c6b`؛ حسِ مالی/اعتماد). زمینه‌ی «مِه»ِ سرد،
    کارت‌های سفید، **خطِ مو به‌جای کادرِ سنگین**، عددهای درشتِ tabular. **پیش‌فرض = پوسته‌ی روشن** (تیره به‌عنوانِ حالتِ جایگزین).
    فقط یک لهجه؛ رنگِ بستانکار=لهجه، بدهکار=گلگونِ ملایم، در انتظار=اُخرایی.
  - **پیاده‌سازی:** بازتعریفِ کاملِ توکن‌های رنگ در `index.css` (بلوکِ روشن و تیره) → کلِ برنامه‌ی توکن‌محور خودکار ری‌اسکین شد؛
    شعاع‌ها نرم‌تر؛ `theme.ts` پیش‌فرض روشن. **`Sidebar.tsx` بازنویسی شد**: فهرستِ گروه‌بندی‌شده‌ی همیشه‌باز با «قرصِ» نرمِ فعال
    (بدونِ آکاردئون/زیرمنوی شلوغ)، نشانِ برند + زیرعنوان. `App.css` یک بلوکِ پرداختِ افزودنی گرفت (سایدبار/نوارِ بالا).
  - **راستی‌آزمایی:** `npm run build` سبز؛ اجرای زنده: `did-finish-load`، `render-process-gone=0`، auto-login و همه‌ی خواندن‌ها ۲۰۰
    — رندرر با سایدبارِ تازه و پوسته‌ی روشنِ سبزآبی درست مانت شد. (برای دیدنِ پیش‌فرضِ روشن، `Local Storage`ِ اپ پاک شد چون اجراهای
    قبلی `cubita-theme=dark` را ذخیره کرده بودند.)
  - **بازِ باقی‌مانده:** صفحاتِ داخلی (داشبورد/فرم‌ها/جدول‌ها) هنوز فقط از راهِ توکن‌ها ری‌اسکین شده‌اند، نه بازچینیِ کاملِ چیدمان مثلِ
    ماکت؛ در صورتِ بازخوردِ کاربر صیقل می‌خورند. برندِ «حسابداری / نسخه‌ی محلی» جای‌گیرِ موقت است (تا انتخابِ نامِ محصول).
    ماکتِ مرجع: `scratchpad/ui-proposal.html`.
- **M5 — بسته‌بندی:** PyInstallerِ سایدکار + NSIS + آزمونِ نصبِ کاملاً آفلاین.
- **M6 — لایسنس/فعال‌سازیِ آفلاین.**
- **M7 — مؤدیانِ آنلاین + تستِ end-to-end.**

## بازِ تصمیم (TBD — منتظرِ کاربر)
- **نامِ محصول/برند** (نام، لوگو، appId).
- **مدلِ لایسنس/فعال‌سازی** (کدِ لایسنس؟ فعال‌سازیِ آنلاینِ یک‌باره؟ بدونِ قفل؟).
- **نمونه‌های طراحیِ سپیدار** که مدِنظرِ کاربر است (اسکرین‌شات/جزییات).
- **فهرستِ دقیقِ ماژول‌ها** (همه‌ی کوبیتا منهای فروشگاه؟ POS/باشگاه مشتریان هم بمانند؟).

## فایل‌های مرجعِ کوبیتا
- Electron/packaging: `desktop/electron/{main,db,sync,preload,updater}.ts`، `desktop/package.json` (build)، `desktop/scripts/*`، `desktop/vite.config.ts`.
- Backend: `backend/app/services/*`، `backend/app/models/*`، `backend/app/database.py`، `backend/alembic/*`، `backend/app/routers/*`.
- UI: `desktop/src/pages/*`، `desktop/src/components/*`، `desktop/src/api.ts`، `desktop/src/App.tsx`.
