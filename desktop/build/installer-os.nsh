; Minimum Windows build is frozen per installer profile.
; Modern Electron requires Windows 10/11; the separate Electron 22 edition targets 8.1.
; PowerShell 4-compatible service guard is shared by both profiles.
;
; **شماره‌ی ساخت از رجیستری، نه `WinVer.nsh`:** آن با `GetVersionEx` می‌خواند که بی اعلامِ ویندوز ۱۰ در
; manifestِ نصاب، ویندوز ۱۰ را «۸» گزارش می‌کند — و آن‌وقت این گارد مشتریِ واقعی را بیرون می‌گذاشت.
; `CurrentBuildNumber` همیشه شماره‌ی واقعی است: ۹۲۰۰ ویندوز ۸، ۹۶۰۰ ویندوز ۸٫۱، از ۱۰۲۴۰ ویندوز ۱۰ و ۱۱.
; اگر خوانده نشد، نصب ادامه می‌یابد: بستنِ درِ رایانه‌ی سالم بدتر از پیامِ دیرتر روی رایانه‌ی قدیمی است.

!include LogicLib.nsh

!define /ifndef CUBITA_MIN_WINDOWS_BUILD 10240

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
    !ifmacrodef cubitaInstallLog
      !insertmacro cubitaInstallLog "BLOCKED unsupported Windows build=$0; no prerequisites or application installed"
      !ifdef CUBITA_WINDOWS81_COMPAT
        MessageBox MB_ICONSTOP|MB_OK "این کلاینت به ویندوز ۸٫۱ نسخهٔ ۶۴ بیتی یا جدیدتر نیاز دارد. هیچ برنامه یا پیش‌نیازی نصب نشد.$\r$\nگزارش: $CubitaInstallLog" /SD IDOK
      !else
      MessageBox MB_ICONSTOP|MB_OK "این ویندوز با نسخهٔ فعلی کوبیتا سازگار نیست. ویندوز ۱۰ یا ۱۱ نسخهٔ ۶۴ بیتی لازم است؛ نصب پیش‌نیاز، ویندوز ۸٫۱ را سازگار نمی‌کند.$\r$\nهیچ برنامه یا پیش‌نیازی نصب نشد.$\r$\nگزارش: $CubitaInstallLog" /SD IDOK
      !endif
    !else
    MessageBox MB_ICONSTOP|MB_OK "کوبیتا فقط روی ویندوز ۱۰ یا ۱۱ (۶۴ بیتی) اجرا می‌شود و این رایانه ویندوزِ قدیمی‌تری دارد (۷، ۸ یا ۸٫۱).$\r$\n$\r$\nچیزی نصب یا تغییر نکرد. کوبیتا را روی رایانه‌ای با ویندوز ۱۰ یا ۱۱ نصب کنید." /SD IDOK
    !endif
    Pop $1
    Pop $0
    SetErrorLevel 2
    Quit
  ${EndIf}
  Pop $1
  Pop $0
!macroend
