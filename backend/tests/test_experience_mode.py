"""حالتِ تجربه‌ی کاربر — ذخیره، اعتبار، و مرزهایی که نباید رد کند.

این ترجیح **فقط نمایش** است. دو ناوردا که این پرونده قفلشان می‌کند:

* عوض‌کردنش هیچ مجوزی نمی‌دهد و هیچ داده‌ی مالی‌ای نمی‌سازد.
* روی **کاربر** می‌نشیند و نه عضویت، پس با سوییچِ کسب‌وکار عوض نمی‌شود —
  برخلافِ `dashboard_cards` که عمداً عضویت‌محور است.
"""
from app.models.user import EXPERIENCE_MODES, User


def test_default_is_simple(db, user, client):
    """پیش‌فرض باید رفتارِ امروز باشد؛ هر کاربرِ موجود فرمِ کلاسیک را می‌بیند."""
    assert user.experience_mode == "simple"
    assert client.get("/api/auth/me").json()["experience_mode"] == "simple"


def test_switch_to_accountant(db, user, client):
    res = client.patch("/api/auth/me", json={"experience_mode": "accountant"})

    assert res.status_code == 200
    assert res.json()["experience_mode"] == "accountant"
    db.refresh(user)
    assert user.experience_mode == "accountant"


def test_switch_back(db, user, client):
    client.patch("/api/auth/me", json={"experience_mode": "accountant"})
    res = client.patch("/api/auth/me", json={"experience_mode": "simple"})

    assert res.json()["experience_mode"] == "simple"
    db.refresh(user)
    assert user.experience_mode == "simple"


def test_unknown_mode_is_rejected(db, user, client):
    """۴۲۲ از اسکیما، نه ۵۰۰ از `CheckConstraint` — خطا باید پیش از دیتابیس بگیرد."""
    res = client.patch("/api/auth/me", json={"experience_mode": "wizard"})

    assert res.status_code == 422
    db.refresh(user)
    assert user.experience_mode == "simple"


def test_no_password_needed(db, user, client):
    """برخلافِ ایمیل، رمزِ فعلی نمی‌خواهد: نه هویت است نه مجوز."""
    res = client.patch("/api/auth/me", json={"experience_mode": "accountant"})
    assert res.status_code == 200


def test_other_fields_untouched(db, user, client):
    """ویرایشِ حالت نباید نام یا ایمیل را تکان دهد."""
    before_name, before_email = user.name, user.email
    client.patch("/api/auth/me", json={"experience_mode": "accountant"})
    db.refresh(user)
    assert (user.name, user.email) == (before_name, before_email)


def test_mode_does_not_change_permissions(db, user, client):
    """**مهم‌ترین تستِ این پرونده.** حالت فقط نمایش است.

    اگر روزی کسی حالت را به دسترسی گره بزند، این‌جا قرمز می‌شود.
    """
    before = client.get("/api/auth/me").json()
    client.patch("/api/auth/me", json={"experience_mode": "accountant"})
    after = client.get("/api/auth/me").json()

    assert after["permissions"] == before["permissions"]
    assert after["enabled_modules"] == before["enabled_modules"]
    assert after["allowed_modules"] == before["allowed_modules"]
    assert after["role_key"] == before["role_key"]


def test_mode_lives_on_user_not_membership(db, user):
    """ستون روی `users` است — اگر کسی جابه‌جایش کند، این تست می‌شکند.

    دلیلش در مهاجرتِ ۰۱۸۲ است: هیچ شناسه‌ی مستأجری در این ترجیح نیست، پس
    کاربری که در دو کسب‌وکار عضو است یک حالتِ واحد دارد.
    """
    assert "experience_mode" in User.__table__.c
    from app.models.tenant import Membership

    assert "experience_mode" not in Membership.__table__.c


def test_registry_matches_schema(db, user, client):
    """هر مقدارِ `EXPERIENCE_MODES` باید واقعاً پذیرفته شود.

    وگرنه افزودنِ حالتِ سوم به مدل، بی‌صدا یک مقدارِ رد‌شونده می‌ساخت.
    """
    for mode in EXPERIENCE_MODES:
        assert client.patch("/api/auth/me", json={"experience_mode": mode}).status_code == 200
