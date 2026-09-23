"""کسب‌وکارِ آزمایشیِ E2E را روی پایگاه‌داده‌ی **دورریختنی** می‌سازد.

از پوشه‌ی `backend` و با پایتونِ همان‌جا اجرا می‌شود (CI و اجرای محلی):

    cd backend && E2E_EMAIL=… E2E_PASSWORD=… python ../desktop/e2e/provision.py

این‌جا و نه در `backend/scripts/`: آن پوشه با کدِ سرور به تولید می‌رود، و این
اسکریپت مالِ تست است.

**گارد:** روی پایگاه‌داده‌ی `hesabdari` اجرا نمی‌شود — آن پایگاه‌داده‌ی توسعه‌ی
واقعی است و داده‌ی کاربر در آن است، نه زمینِ آزمایش.
"""
import os
import sys

#: پایتون پوشه‌ی **خودِ اسکریپت** را در مسیر می‌گذارد، نه پوشه‌ی جاری؛ اسکریپت از
#: `backend` اجرا می‌شود و `app` آن‌جاست.
sys.path.insert(0, os.getcwd())

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.provisioning import signup_new_business  # noqa: E402

db_name = get_settings().database_url.rsplit("/", 1)[-1].split("?", 1)[0]
if db_name == "hesabdari":
    sys.exit("E2E روی پایگاه‌داده‌ی hesabdari اجرا نمی‌شود — یک پایگاه‌داده‌ی دورریختنی بدهید.")

db = SessionLocal()
signup_new_business(
    db,
    business_name="آزمون E2E",
    owner_name="حسابدار آزمون",
    email=os.environ["E2E_EMAIL"],
    password=os.environ["E2E_PASSWORD"],
    trial=False,
)
db.commit()
print(f"E2E: کسب‌وکارِ آزمایشی روی «{db_name}» ساخته شد")
