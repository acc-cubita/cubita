# -*- mode: python ; coding: utf-8 -*-
# PyInstaller — `cubita-server.exe` (ENTERPRISE_PLAN.md، M4). اجرا از `backend/`:
#
#     ZARINPAL_SANDBOX=true venv/Scripts/python.exe -m PyInstaller --noconfirm packaging/cubita-server.spec
#
# خروجی: `dist/cubita-server/` (onedir — نه onefile: استخراجِ هر بار کند است و آنتی‌ویروس‌ها
# از exeِ خوداستخراج بیشتر بدشان می‌آید).
#
# **فایل‌های داده خودکار جمع می‌شوند، نه فهرستِ دستی.** در M0 سه فایلِ غیرِ `.py`
# (`chart_templates.json` و دو فونت) جا ماندند و بیلد هیچ خطایی نداد — فقط نسخه‌ی
# سازمانی در زمانِ اجرا می‌شکست. حالا هر فایلِ غیرِ `.py` زیرِ `app/` خودش می‌آید.
# SPECPATH را PyInstaller تعریف می‌کند (پوشه‌ی همین فایل)؛ مسیرها مطلق‌اند چون `--add-data`
# نسبت به specpath حل می‌شود نه cwd (تله‌ی ۲ِ M0).

import os
from PyInstaller.utils.hooks import collect_submodules

BACKEND = os.path.abspath(os.path.join(SPECPATH, ".."))


def app_data_files():
    out = []
    root = os.path.join(BACKEND, "app")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith((".py", ".pyc")):
                continue
            src = os.path.join(dirpath, name)
            dest = os.path.relpath(dirpath, BACKEND)
            out.append((src, dest))
    return out


datas = [
    (os.path.join(BACKEND, "alembic"), "alembic"),
    (os.path.join(BACKEND, "alembic.ini"), "."),
    *app_data_files(),
]

hiddenimports = [
    *collect_submodules("app"),
    #: passlib هندلرِ bcrypt را در زمانِ اجرا از رجیستری لود می‌کند (تله‌ی ۳ِ M0).
    *collect_submodules("passlib"),
    *collect_submodules("uvicorn"),
    #: مهاجرت‌ها با importlib بار می‌شوند و PyInstaller نمی‌بیندشان؛ ولی کد را از `alembic/`ِ
    #: دادهِ بسته می‌خوانند، پس فقط خودِ alembic لازم است.
    *collect_submodules("alembic"),
]

a = Analysis(
    [os.path.join(SPECPATH, "server_entry.py")],
    pathex=[BACKEND],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cubita-server",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="cubita-server", upx=False)
