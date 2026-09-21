# ستادِ کوبیتا — `admin.cubita.ir`

پنلِ مدیریتِ پلتفرم. **اپِ جدایی است، نه بخشی از نرم‌افزارِ حسابداری**؛ فقط به
همان بک‌اند وصل می‌شود.

## چرا پروژه‌ی جدا

خواسته این بود که `acc.cubita.ir` هیچ مدیریتی نداشته باشد. پروژه‌ی npmِ مستقل
این را **ساختاراً** درست می‌کند: کدِ ستاد اصلاً داخلِ باندلِ مشتری نمی‌رود، و
نمی‌تواند برود. جزئیاتِ تصمیم و بدیل‌ها در `PROJECT_OVERVIEW.md` §۱۰.

## اجرا در محیطِ توسعه

```bash
# ۱) بک‌اند — با اجازه‌ی مبدأِ ۵۱۷۵
cd backend
ZARINPAL_SANDBOX=true PYTHONUTF8=1 \
  ALLOWED_ORIGINS="http://localhost:5173,http://localhost:5175,app://desktop" \
  venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# ۲) اپِ ستاد
cd admin
VITE_API_URL=http://localhost:8000 npm run dev   # → http://localhost:5175
```

⚠️ **`ALLOWED_ORIGINS` فقط در توسعه لازم است.** در production اپِ ستاد
**هم‌مبدأ** است (vhostِ `admin.cubita.ir` مسیرِ `/api/` را به همان بک‌اندِ
`127.0.0.1:8001` پراکسی می‌کند)، پس هیچ CORSی در کار نیست. محلی اما دو پورتِ
متفاوت‌اند و بدونِ این متغیر، ورود با «Failed to fetch» رد می‌شود — با پیامی که
هیچ اشاره‌ای به CORS ندارد.

### ساختِ کاربرِ ستادِ محلی

مهاجرت `0180` برای ایمیل‌های `SUPER_ADMIN_EMAILS` ردیفِ `owner` می‌سازد، ولی
رمزش همان رمزِ کاربرِ موجود است. برای یک حسابِ آزمایشی:

```python
from app.database import SessionLocal
from app.models.tenant import PlatformAdmin
from app.models.user import User
from app.security import hash_password

db = SessionLocal()
u = User(name="کارمندِ محلی", email="local-staff@staff.cubita.ir",
         hashed_password=hash_password("LocalStaffPass!2026"), active=True)
db.add(u); db.flush()
db.add(PlatformAdmin(user_id=u.id, role="owner", is_active=True))
db.commit()
```

## دروازه‌ها

```bash
npx tsc -b --force
npx oxlint src
npm test                      # vitest
node scripts/audit-admin.mjs  # قاعده‌های ساختاری (جدولِ موبایل، ارقام، …)
node scripts/check-shared.mjs # واگراییِ فایل‌های کپی‌شده از desktop/
```

## فایل‌های مشترک

چهار فایل از `desktop/src` **کپی** شده‌اند و `check-shared.mjs` بایت‌به‌بایت
می‌سنجدشان (مانیفست در خودِ اسکریپت). تغییر در یک طرف باید در طرفِ دیگر هم
اعمال شود، وگرنه CI قرمز می‌شود. اگر روزی مصرف‌کننده‌ی سومی آمد، جای این
اسکریپت یک پکیجِ مشترک است.

## ساخت برای production

```bash
VITE_API_URL=https://admin.cubita.ir npm run build
```

آدرس داخلِ باندل **بیک می‌شود** و `deploy-admin-web.sh` پیش از جابه‌جایی
grepش می‌کند. باندلی که با `acc.cubita.ir` ساخته شود، گاردِ ضدِجابه‌جاییِ
`deploy.sh` را کور می‌کند.
