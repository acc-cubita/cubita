# راهنمای کلود برای مخزنِ کوبیتا

<!-- این فایل در هر نشستِ Claude Code خودکار خوانده می‌شود. کوتاه و دقیق نگهش دار. -->

## محصول

**کوبیتا (Cubita)** — نرم‌افزارِ حسابداریِ B2B فارسی/RTL همراهِ بازارِ عمده‌فروشی،
با چند‌مستأجری (multi-tenant) روی سه پلتفرم:

| بخش | مسیر | چیست |
|---|---|---|
| بک‌اند | `backend/` | FastAPI + PostgreSQL + SQLAlchemy 2.0 + Alembic — منبعِ حقیقت |
| دسکتاپ + وب | `desktop/` | یک کدِ React/TS که **هم** Electron **و هم** مرورگر را می‌راند |
| موبایل | `mobile/` | اپ نیتیوِ اندروید (Expo/React Native)، طراحیِ مستقل، همان بک‌اند |
| سایتِ معرفی | `website/` | React + Vite، مسیرِ پرداختِ زرین‌پال |

📖 **نقشه‌ی کاملِ پروژه: [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** — پیش از هر کارِ
جدی بخوانش؛ معماری، دامنه‌ها، استقرار و تاریخچه‌ی همه‌ی ارتقاها آنجاست.
🛠 **راه‌اندازیِ محیط از صفر: [CONTRIBUTING.md](CONTRIBUTING.md)**

---

## قیدهای سخت — این‌ها را نقض نکن

1. **هرگز `deploy.sh demo` را اجرا نکن.** گاردش وبِ demo را بازنویسی می‌کند و درِ
   تریال را می‌شکند. تازه‌سازیِ demo فقط با
   `rsync -a --delete /opt/hesabdari/web/ /opt/cubita-demo/web/`.
   این قاعده‌ی *درستی* است نه دسترسی — برای همه، از جمله صاحبِ پروژه.
2. **استقرار روی production: هر دو توسعه‌دهنده مجازند، ولی قبلش هماهنگ کن.**
   دو استقرارِ همزمان یعنی یکی سرویس را وسطِ مهاجرتِ دیگری ری‌استارت می‌کند.
   `deploy.sh` خودش پشتیبان می‌گیرد و روی خطا برمی‌گرداند، ولی از این محافظت
   نمی‌کند. اعلام کن، بعد اجرا کن.
3. **parityِ سه‌پلتفرمی:** هر قابلیت باید هم روی دسکتاپ و هم وب کار کند.
4. **نمای موبایل بخشی از «تمام‌شده» است:** بعد از هر تغییرِ UI، نمای `≤۷۶۰px` را
   هم بساز/راستی‌آزمایی کن.
5. **همه‌ی متنِ کاربر فارسی است.** ارقام با `toLocaleString('fa-IR')`، تاریخ‌ها
   جلالی از `desktop/src/lib/jalali`.
6. **دو نمای یک داده نساز.** اگر جدول/صفحه‌ای برای این داده هست، همان را گسترش بده.
7. **رازها هرگز کامیت نمی‌شوند.** `.env`ها نادیده گرفته شده‌اند؛ الگو در `*.env.example`.

---

## چیزهایی که بی‌صدا می‌شکنند

اینها خطا **نمی‌دهند** — فقط نتیجه‌ی غلط می‌دهند. مراقبشان باش:

- **RLS.** هر جدولِ مستأجرمحور `FORCE ROW LEVEL SECURITY` دارد و با
  `current_setting('app.tenant_id')` فیلتر می‌شود. در **مهاجرت‌های داده** حتماً
  `rls_disabled(conn, tables)` از `app/migration_utils.py` را بگذار — بدونِ آن
  `UPDATE` بی‌سروصدا صفر ردیف می‌بیند و مهاجرت «موفق» گزارش می‌شود.
- **شماره‌گذاریِ اسناد.** از `next_document_number(db, doc_type)` در
  `app/services/numbering.py` بگیر (شمارنده‌ی بی‌شکافِ درونِ همان تراکنش).
  SEQUENCE استفاده نکن — روی rollback شماره می‌سوزاند و شکاف می‌افتد.
- **صفحه‌بندی.** `MAX_LIMIT = 200` در `app/pagination.py`. `limit` بزرگ‌تر →
  پاسخِ ۴۲۲ و صفحه در UI بی‌صدا خالی می‌شود.
- **انتخابِ حساب.** سندهای خودکار حساب را با `system_role` پیدا می‌کنند، نه با کد
  یا نام: `get_account(db, role)` / `get_or_create_account(...)`.
- **قاعده‌ی نظیر.** هر منوی عملیاتی که رکورد می‌سازد باید یک «فهرست»ِ متناظر داشته
  باشد و در `OPS_LIST_MAP` ثبت شود. استثناها: `'state'` (تغییردهنده‌ی وضعیت)،
  `'view'` (گزارش/دفترِ خودی)، `'none'` (غیرثبتی). ممیزِ **R11** نبودش را خطا می‌دهد.

---

## ناوبریِ فرانت‌اند — چهار جا باید هماهنگ بمانند

افزودنِ یک صفحه یعنی ویرایشِ **هر چهار**:

1. `desktop/src/lib/navModel.tsx` — اتحادِ `PageKey` و `NAV_GROUPS`
2. `desktop/src/components/moduleSections.tsx` — `MODULE_SECTIONS`
3. `desktop/src/components/moduleLists.tsx` — `LIST_MENUS` / `LIST_PAGE_GROUP` /
   `MODULE_LISTS` / `OPS_LIST_MAP`
4. `PAGE_MODULE_KEY` — صفحه را زیرِ کلیدِ ماژول می‌بندد

مهارتِ `.claude/skills/cubita-page/SKILL.md` این کار را قدم‌به‌قدم دارد.

**قراردادِ واکنش‌گرا (CSS):** `.mod-panels` زیرِ ۱۰۲۴px پنهان می‌شود؛
`.workspace-split` زیرِ ۹۸۰px جمع می‌شود؛ جدول‌ها زیرِ ۷۶۰px کارت می‌شوند —
جدول کلاسِ `cards-on-mobile` و هر `td` صفتِ `data-label` می‌خواهد
(به‌جز `card-title`/`card-actions`/`card-wide`/`card-full`/`card-hide`).
جدولی که کارت نمی‌شود `table-plain` می‌گیرد.

---

## دستورها

### بک‌اند (از `backend/`)

```bash
venv/Scripts/python.exe -m pytest -q                     # کلِ سوییت باید سبز بماند
ZARINPAL_SANDBOX=true venv/Scripts/python.exe -m alembic upgrade head
ZARINPAL_SANDBOX=true PYTHONUTF8=1 venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`--reload` نگذار؛ بعد از هر ویرایش دستی ری‌استارت کن.
`ZARINPAL_SANDBOX=true` را به‌صورتِ متغیرِ محیطی بده — فایلِ `.env` را دست نزن.

### دسکتاپ/وب (از `desktop/`)

```bash
npx tsc -b --force                              # باید صفر خطا بدهد
npm run lint
node scripts/audit-pages.mjs                    # ۱۲ قاعده‌ی ساختاریِ صفحه‌ها
npm run dev                                     # Electron + Vite
WEB_ONLY=1 npx vite --port 5173 --strictPort    # فقط مرورگر
```

### موبایل (از `mobile/`)

```bash
npx expo start          # سرورِ توسعه
npm run android         # ساختِ نیتیو (gradlew محلی، نه EAS)
```

### پیش از هر کامیت

`tsc` سبز · `pytest` سبز · `audit-pages.mjs` بدونِ error.

---

## کارِ دو‌نفره

- **روی `master` مستقیم کامیت نکن.** شاخه بساز: `feat/…` · `fix/…` · `chore/…`
- پیامِ کامیت فارسی، به سبکِ conventional:
  `feat(sales): ماژولِ فروش — هجده عملیات و دوازده دفتر`
- **هر تغییرِ مهم یک ردیف در بخشِ ۱۰ «تاریخچه‌ی ارتقاها»ی `PROJECT_OVERVIEW.md`
  می‌گیرد.** این تنها راهی است که نفرِ دیگر می‌فهمد چه شد و چرا.
- شروعِ کار: `git pull --rebase origin master`. پایان: push شاخه و Pull Request.
- دیدنِ کارِ نفرِ دیگر:
  ```bash
  git fetch origin
  git log --oneline master..origin/master
  git diff master origin/master -- PROJECT_OVERVIEW.md
  ```
- **مهاجرتِ همزمان خطرناک است:** اگر دو نفر همزمان مهاجرتِ Alembic بسازند، دو
  سرِ موازی می‌شود. قبل از ساختِ مهاجرت بگو، یا `alembic heads` را چک کن.

---

## چیزی که در مخزن نیست (محلی و ماشین‌به‌ماشین فرق می‌کند)

`backend/.env` · `website/.env` · `backend/venv/` · `node_modules/` ·
`mobile/android/` · `mobile/release/` · `desktop/dist*` · `desktop/release/` · `_deploy/`

الگوی هرکدام در فایلِ `.env.example`ِ همان پوشه است.
