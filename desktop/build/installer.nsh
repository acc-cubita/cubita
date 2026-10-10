; نصابِ ابریِ کوبیتا — تنها سفارشی‌سازی: شرطِ ویندوز ۱۰ پیش از هر کار (`installer-os.nsh`).
; نصابِ سازمانی `installer-enterprise.nsh` را دارد و همان شرط را آن‌جا صدا می‌زند.

!include "${__FILEDIR__}\installer-os.nsh"

!macro customInit
  !insertmacro cubitaRequireWindows10
!macroend
