; شرطِ ویندوزِ مشترکِ هر دو نصاب (ابری و سازمانی): ویندوز ۱۰ یا جدیدتر.
;
; Electron از نسخه‌ی ۲۳ روی ویندوز ۷، ۸ و ۸٫۱ اجرا نمی‌شود (Chromium 110) و کوبیتا روی Electron 42 است؛ پس
; روی ویندوزِ قدیمی برنامه اصلاً باز نمی‌شود. بدونِ این شرط، نصابِ سازمانی روی ویندوز ۸ وسطِ کار با پیامِ
; گمراه‌کننده‌ی «بازیابی خودکار … متوقف نشد؛ دوباره نصب را اجرا کنید» می‌ایستاد (PowerShell 3/4ِ ویندوز ۸
; `::new()`ِ اسکریپتِ گارد را نمی‌شناسد) — و دوباره اجرا کردن هیچ‌وقت درستش نمی‌کرد (۱۴۰۵/۰۷/۱۸).
;
; **شماره‌ی ساخت از رجیستری، نه `WinVer.nsh`:** آن با `GetVersionEx` می‌خواند که بی اعلامِ ویندوز ۱۰ در
; manifestِ نصاب، ویندوز ۱۰ را «۸» گزارش می‌کند — و آن‌وقت این گارد مشتریِ واقعی را بیرون می‌گذاشت.
; `CurrentBuildNumber` همیشه شماره‌ی واقعی است: ۹۲۰۰ ویندوز ۸، ۹۶۰۰ ویندوز ۸٫۱، از ۱۰۲۴۰ ویندوز ۱۰ و ۱۱.
; اگر خوانده نشد، نصب ادامه می‌یابد: بستنِ درِ رایانه‌ی سالم بدتر از پیامِ دیرتر روی رایانه‌ی قدیمی است.

!include LogicLib.nsh

!define CUBITA_MIN_WINDOWS_BUILD 10240

;; RESULT = "1" اگر شماره‌ی ساختِ BUILD (رشته‌ی رجیستری) کمتر از ویندوز ۱۰ است، وگرنه "0". جدا تا آزمون‌پذیر باشد.
!macro cubitaWindowsTooOld BUILD RESULT
  StrCpy ${RESULT} "0"
  ${If} ${BUILD} != ""
    IntOp ${RESULT} ${BUILD} + 0
    ${If} ${RESULT} > 0
    ${AndIf} ${RESULT} < ${CUBITA_MIN_WINDOWS_BUILD}
      StrCpy ${RESULT} "1"
    ${Else}
      StrCpy ${RESULT} "0"
    ${EndIf}
  ${EndIf}
!macroend

!macro cubitaRequireWindows10
  Push $0
  Push $1
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\Windows NT\CurrentVersion" "CurrentBuildNumber"
  !insertmacro cubitaWindowsTooOld $0 $1
  ${If} $1 == "1"
    MessageBox MB_ICONSTOP|MB_OK "کوبیتا فقط روی ویندوز ۱۰ یا ۱۱ (۶۴ بیتی) اجرا می‌شود و این رایانه ویندوزِ قدیمی‌تری دارد (۷، ۸ یا ۸٫۱).$\r$\n$\r$\nچیزی نصب یا تغییر نکرد. کوبیتا را روی رایانه‌ای با ویندوز ۱۰ یا ۱۱ نصب کنید." /SD IDOK
    Pop $1
    Pop $0
    SetErrorLevel 2
    Quit
  ${EndIf}
  Pop $1
  Pop $0
!macroend
