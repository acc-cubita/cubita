; نصابِ «کوبیتا سازمانی» — صفحه‌ی نقش (سرور/کلاینت) و نصبِ سرور (ENTERPRISE_PLAN.md، M4).
;
; همه‌ی کارِ واقعی در `cubita-server.exe` است (پایتونِ تست‌پذیر، `backend/app/onprem/`)؛ این
; فایل فقط می‌پرسد و همان exe را صدا می‌زند. `scripts/dist-enterprise.mjs` وقتی بسته‌ی سرور
; ساخته شده باشد `!define CUBITA_HAS_SERVER` را بالای این فایل می‌گذارد؛ بی‌آن نصاب فقط کلاینت است.
;
; سه قاعده:
; - حذفِ برنامه **هرگز** پوشه‌ی داده (C:\ProgramData\Cubita) را پاک نمی‌کند — دفترِ حسابداریِ شرکت است.
; - آپدیت (`isUpdated`) سرویس‌ها را برنمی‌دارد؛ API و PostgreSQL را پیش از کپی تمیز می‌بندد
;   (exeِ در حالِ اجرا قفل است) و `install` دوباره بالایش می‌آورد و مهاجرت‌ها را اجرا می‌کند.
; - نصبِ بی‌صدا (/S) نقشِ قبلی را نگه می‌دارد؛ نصبِ تازه‌ی بی‌صدا کلاینت است.

!include nsDialogs.nsh
!include LogicLib.nsh
; شرطِ ویندوز ۱۰ — مشترک با نصابِ ابری؛ `dist-enterprise.mjs` کنارِ همین فایل کپی‌اش می‌کند.
!include "${__FILEDIR__}\installer-os.nsh"

!define /ifndef CUBITA_REG_KEY "Software\Cubita Enterprise"
!define CUBITA_DEFAULT_URL "http://localhost:8420"
!define /ifndef CUBITA_INSTALLER_PAYLOAD_DIR "${__FILEDIR__}"
!define /ifndef CUBITA_INSTALLER_GUARD "${__FILEDIR__}\installer-service-guard.ps1"

Var CubitaRole
Var CubitaRadioServer
Var CubitaRadioClient
Var CubitaNetworkRestartTask
Var CubitaApiRestart
Var CubitaPgRestart
Var CubitaExistingRole
Var CubitaExistingDirectory
Var CubitaFilesTouched
Var CubitaRecoveryPaused
Var CubitaRecoveryWasBlocked
Var CubitaInstallLog

!macro cubitaInstallLog MESSAGE
  Push $8
  FileOpen $8 "$CubitaInstallLog" a
  FileWrite $8 "${MESSAGE}$\r$\n"
  FileClose $8
  Pop $8
!macroend

!ifmacrondef cubitaPrerequisites
!macro cubitaPrerequisites
  InitPluginsDir
  File /oname=$PLUGINSDIR\cubita-prerequisites.ps1 "${CUBITA_INSTALLER_PAYLOAD_DIR}\installer-prerequisites.ps1"
  !ifdef CUBITA_LEGACY_X86
    File /oname=$PLUGINSDIR\vc_redist.x86.exe "${CUBITA_INSTALLER_PAYLOAD_DIR}\prerequisites\vc_redist.x86.exe"
  !else
    File /oname=$PLUGINSDIR\vc_redist.x64.exe "${CUBITA_INSTALLER_PAYLOAD_DIR}\prerequisites\vc_redist.x64.exe"
  !endif
  File /oname=$PLUGINSDIR\runtime.json "${CUBITA_INSTALLER_PAYLOAD_DIR}\prerequisites\runtime.json"
  !ifdef CUBITA_HAS_SERVER
  File /oname=$PLUGINSDIR\dotnet48.exe "${CUBITA_INSTALLER_PAYLOAD_DIR}\prerequisites\dotnet48.exe"
  File /oname=$PLUGINSDIR\dotnet.json "${CUBITA_INSTALLER_PAYLOAD_DIR}\prerequisites\dotnet.json"
  !endif
  !ifdef CUBITA_WINDOWS_LEGACY
    File /oname=$PLUGINSDIR\cubita-bootstrap.ps1 "${CUBITA_INSTALLER_PAYLOAD_DIR}\installer-legacy-bootstrap.ps1"
    File /oname=$PLUGINSDIR\wmf-x64.msu "${CUBITA_INSTALLER_PAYLOAD_DIR}\prerequisites\wmf-x64.msu"
    File /oname=$PLUGINSDIR\wmf-x86.msu "${CUBITA_INSTALLER_PAYLOAD_DIR}\prerequisites\wmf-x86.msu"
    !insertmacro cubitaInstallLog "Windows7 bootstrap begin"
    nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\cubita-bootstrap.ps1" -PayloadDirectory "$PLUGINSDIR" -LogPath "$CubitaInstallLog" -DotNetSha256 "${CUBITA_LEGACY_DOTNET_SHA256}" -WmfX64Sha256 "${CUBITA_LEGACY_WMF64_SHA256}" -WmfX86Sha256 "${CUBITA_LEGACY_WMF32_SHA256}"'
    Pop $0
    !insertmacro cubitaInstallLog "Windows7 bootstrap exit=$0"
    ${If} $0 == "3010"
      MessageBox MB_ICONINFORMATION|MB_OK "پیش‌نیاز ویندوز ۷ نصب شد. ویندوز را راه‌اندازی مجدد کنید و همین نصاب را دوباره اجرا کنید؛ فایل‌ها و سرویس‌های کوبیتا هنوز تغییر نکرده‌اند.$\r$\nگزارش: $CubitaInstallLog" /SD IDOK
      SetErrorLevel 3010
      Quit
    ${ElseIf} $0 != "0"
      MessageBox MB_ICONSTOP|MB_OK "آماده‌سازی پیش‌نیاز ویندوز ۷ کامل نشد (کد $0). فایل‌های کوبیتا هنوز تغییر نکرده‌اند.$\r$\nگزارش دقیق: $CubitaInstallLog" /SD IDOK
      SetErrorLevel 2
      Quit
    ${EndIf}
  !endif
  DetailPrint "بررسی و نصب پیش‌نیازهای کوبیتا…"
  !insertmacro cubitaInstallLog "prerequisites begin"
    !ifdef CUBITA_WINDOWS_LEGACY
    !ifdef CUBITA_LEGACY_X86
      !define CUBITA_PREREQUISITE_ARCH "x86"
    !else
      !define CUBITA_PREREQUISITE_ARCH "x64"
    !endif
    nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\cubita-prerequisites.ps1" -PayloadDirectory "$PLUGINSDIR" -LogPath "$CubitaInstallLog" -Role "$CubitaRole" -Architecture "${CUBITA_PREREQUISITE_ARCH}" -MinimumPowerShell 3 -MinimumFrameworkRelease 378389'
    !undef CUBITA_PREREQUISITE_ARCH
  !else
nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\cubita-prerequisites.ps1" -PayloadDirectory "$PLUGINSDIR" -LogPath "$CubitaInstallLog" -Role "$CubitaRole"'
  !endif
  Pop $0
  !insertmacro cubitaInstallLog "prerequisites exit=$0"
  ${If} $0 == "3010"
    MessageBox MB_ICONINFORMATION|MB_OK "پیش‌نیاز نصب شد و به راه‌اندازی مجدد ویندوز نیاز دارد. رایانه را راه‌اندازی مجدد کنید و سپس همین نصاب را اجرا کنید؛ فایل‌های کوبیتا هنوز تغییر نکرده‌اند.$\r$\nگزارش: $CubitaInstallLog" /SD IDOK
    SetErrorLevel 3010
    Quit
  ${ElseIf} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "نصب پیش‌نیاز کامل نشد (کد $0). فایل‌های کوبیتا هنوز تغییر نکرده‌اند. برای بررسی، این گزارش را ارسال کنید:$\r$\n$CubitaInstallLog" /SD IDOK
    SetErrorLevel 2
    Quit
  ${EndIf}
!macroend
!endif

!macro cubitaRunGuard ACTION RESULT
  InitPluginsDir
  File /oname=$PLUGINSDIR\cubita-installer-guard.ps1 "${CUBITA_INSTALLER_GUARD}"
  !insertmacro cubitaInstallLog "guard action=${ACTION} begin"
    !ifdef CUBITA_LEGACY_X86
nsExec::ExecToLog /TIMEOUT=75000 '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\cubita-installer-guard.ps1" -Action "${ACTION}" -AppPath "$INSTDIR\${APP_EXECUTABLE_FILENAME}" -LogPath "$CubitaInstallLog" -Architecture "x86"'
  !else
nsExec::ExecToLog /TIMEOUT=75000 '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\cubita-installer-guard.ps1" -Action "${ACTION}" -AppPath "$INSTDIR\${APP_EXECUTABLE_FILENAME}" -LogPath "$CubitaInstallLog"'
  !endif
  Pop ${RESULT}
  !insertmacro cubitaInstallLog "guard action=${ACTION} exit=${RESULT}"
!macroend

!macro customHeader
  !ifndef BUILD_UNINSTALLER
    Function CubitaRestorePreparing
      ; فقط پیش از حذف/کپی می‌توان نسخهٔ قبلی را با اطمینان دوباره اجرا کرد.
      ${If} $CubitaFilesTouched != "1"
        ${If} $CubitaPgRestart == "7"
          !insertmacro cubitaRunGuard "start-pg" $0
          ${If} $0 == "0"
            StrCpy $CubitaPgRestart "0"
          ${Else}
            MessageBox MB_ICONSTOP|MB_OK "راه‌اندازی دوبارهٔ دیتابیس انجام نشد. در Services، سرویس CubitaPostgres را بررسی کنید؛ پوشهٔ داده را حذف نکنید." /SD IDOK
            SetErrorLevel 2
          ${EndIf}
        ${EndIf}
        ${If} $CubitaApiRestart == "7"
          !insertmacro cubitaRunGuard "start-api" $0
          ${If} $0 == "0"
            StrCpy $CubitaApiRestart "0"
          ${Else}
            MessageBox MB_ICONSTOP|MB_OK "راه‌اندازی دوبارهٔ سرور انجام نشد. در Services، سرویس CubitaApi را بررسی و راه‌اندازی کنید." /SD IDOK
            SetErrorLevel 2
          ${EndIf}
        ${EndIf}
        ${If} $CubitaNetworkRestartTask == "7"
          !insertmacro cubitaRunGuard "resume-network" $0
          ${If} $0 == "0"
            StrCpy $CubitaNetworkRestartTask "0"
          ${Else}
            MessageBox MB_ICONSTOP|MB_OK "نگهداری شبکه دوباره فعال نشد؛ پس از بررسی سرور، تنظیم شبکه را در برنامه تأیید کنید." /SD IDOK
            SetErrorLevel 2
          ${EndIf}
        ${EndIf}
        ${If} $CubitaRecoveryPaused == "1"
        ${AndIf} $CubitaRecoveryWasBlocked == "0"
          !insertmacro cubitaRunGuard "maintenance-end" $0
          ${If} $0 != "0"
            SetErrorLevel 2
          ${EndIf}
        ${EndIf}
        StrCpy $CubitaRecoveryPaused "0"
      ${ElseIf} $CubitaApiRestart == "7"
      ${OrIf} $CubitaPgRestart == "7"
      ${OrIf} $CubitaNetworkRestartTask == "7"
      ${OrIf} $CubitaRecoveryPaused == "1"
        ; نسخهٔ نیمه‌کپی‌شده یا مهاجرت ناموفق را کورکورانه شروع نکن.
        MessageBox MB_ICONSTOP|MB_OK "نصب سرور کامل نشد و سرویس ممکن است خاموش باشد. نصاب را با نقش و مسیر قبلی دوباره کامل کنید؛ پوشهٔ داده و صف را حذف نکنید." /SD IDOK
        StrCpy $CubitaApiRestart "0"
        StrCpy $CubitaPgRestart "0"
        StrCpy $CubitaNetworkRestartTask "0"
        StrCpy $CubitaRecoveryPaused "0"
        SetErrorLevel 2
      ${EndIf}
    FunctionEnd

    Function .onInstFailed
      Call CubitaRestorePreparing
    FunctionEnd

    Function .onGUIEnd
      Call CubitaRestorePreparing
    FunctionEnd
  !endif
!macroend

!macro cubitaReadRole
  ReadRegStr $CubitaRole HKLM "${CUBITA_REG_KEY}" "Role"
  ${If} $CubitaRole == ""
    StrCpy $CubitaRole "client"
  ${EndIf}
!macroend

!macro customInit
  System::Call 'kernel32::GetCurrentProcessId() i .r0'
  System::Call 'kernel32::GetTickCount() i .r1'
  SetShellVarContext all
  CreateDirectory "$APPDATA\Cubita\logs"
  StrCpy $CubitaInstallLog "$APPDATA\Cubita\logs\install-$0-$1.log"
  ClearErrors
  FileOpen $2 "$CubitaInstallLog" w
  ${If} ${Errors}
    StrCpy $CubitaInstallLog "$TEMP\Cubita-install-$0-$1.log"
    FileOpen $2 "$CubitaInstallLog" w
  ${EndIf}
  FileWrite $2 "Cubita Enterprise installer; session=$0-$1$\r$\n"
  FileClose $2
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\Windows NT\CurrentVersion" "CurrentBuildNumber"
  !ifdef CUBITA_LEGACY_X86
    !insertmacro cubitaInstallLog "OS build=$0; minimum=${CUBITA_MIN_WINDOWS_BUILD}; architecture=x86"
  !else
    !insertmacro cubitaInstallLog "OS build=$0; minimum=${CUBITA_MIN_WINDOWS_BUILD}; architecture=x64"
  !endif
  ; پیش از هر چیز: روی ویندوز ۷/۸/۸٫۱ برنامه اجرا نمی‌شود، پس نه نقش پرسیده می‌شود نه سرویسی لمس.
  !insertmacro cubitaRequireWindows10
  !insertmacro cubitaReadRole
  StrCpy $CubitaExistingRole $CubitaRole
  ReadRegStr $CubitaExistingDirectory HKLM "${INSTALL_REGISTRY_KEY}" "InstallLocation"
  StrCpy $CubitaApiRestart "0"
  StrCpy $CubitaPgRestart "0"
  StrCpy $CubitaNetworkRestartTask "0"
  StrCpy $CubitaFilesTouched "0"
  StrCpy $CubitaRecoveryPaused "0"
  StrCpy $CubitaRecoveryWasBlocked "0"
  ; بازکردن/بستن جادوگر هیچ سرویس یا task را تغییر نمی‌دهد.
  !ifndef CUBITA_HAS_SERVER
    ${If} $CubitaExistingRole == "server"
      MessageBox MB_ICONSTOP|MB_OK "این فایل فقط کلاینت است؛ سرور موجود را با نصاب کامل سازمانی به‌روز کنید." /SD IDOK
      SetErrorLevel 2
      Quit
    ${EndIf}
  !endif
!macroend

!macro customCheckAppRunning
  ; این hook در section نصب است؛ در آغاز جادوگر اجرا نمی‌شود.
  !ifndef BUILD_UNINSTALLER
    !insertmacro cubitaPrerequisites
  !endif
  !ifndef BUILD_UNINSTALLER
  !ifdef CUBITA_WINDOWS_LEGACY
    ${If} $CubitaExistingRole == "server"
      !insertmacro cubitaRunGuard "architecture-check" $0
      ${If} $0 != "0"
        MessageBox MB_ICONSTOP|MB_OK "معماری این نصاب با سرور قبلی سازگار نیست یا فایل سرور قابل بررسی نبود. نصاب هم‌معماری را اجرا کنید؛ فایل‌ها و سرویس‌ها هنوز تغییر نکرده‌اند.$\r$\nگزارش: $CubitaInstallLog" /SD IDOK
        SetErrorLevel 2
        Quit
      ${EndIf}
    ${EndIf}
  !endif
  !endif
  !insertmacro cubitaRunGuard "app-running" $0
  ${If} $0 == "7"
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "پیش از نصب، کارها را ذخیره کنید. برای بستن برنامه و ادامهٔ نصب تأیید کنید." /SD IDOK IDOK +2
    Quit
    !insertmacro cubitaRunGuard "close-app" $0
  ${EndIf}
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "بررسی یا بستن برنامه انجام نشد؛ برنامه را ببندید و نصاب را دوباره اجرا کنید." /SD IDOK
    SetErrorLevel 2
    Quit
  ${EndIf}
  !ifndef BUILD_UNINSTALLER
    ; pg_ctl registerِ نصب قبلی به مسیر قبلی گره خورده؛ ارتقا نباید آن را جابه‌جا کند.
    ${If} $CubitaExistingRole == "server"
    ${AndIf} $CubitaExistingDirectory != ""
    ${AndIf} $INSTDIR != $CubitaExistingDirectory
      MessageBox MB_ICONSTOP|MB_OK "ارتقای سرور باید در مسیر قبلی باشد: $CubitaExistingDirectory. تغییر مسیر و انتقال دفتر نیاز به راه‌اندازی جداگانه دارد." /SD IDOK
      SetErrorLevel 2
      Quit
    ${EndIf}
    ; Block recovery BEFORE the state snapshot: a start between snapshot/stop
    ; would leave a formerly stopped service running while files are copied.
    !insertmacro cubitaRunGuard "maintenance-begin" $CubitaRecoveryWasBlocked
    ${If} $CubitaRecoveryWasBlocked != "0"
    ${AndIf} $CubitaRecoveryWasBlocked != "7"
      MessageBox MB_ICONSTOP|MB_OK "آماده‌سازی نصب متوقف شد (مرحله maintenance-begin، کد $CubitaRecoveryWasBlocked). فایل‌های برنامه جایگزین نشده‌اند. جزئیات علت در گزارش نصب است؛ آن را برای پشتیبانی ارسال کنید:$\r$\n$CubitaInstallLog" /SD IDOK
      SetErrorLevel 2
      Quit
    ${EndIf}
    StrCpy $CubitaRecoveryPaused "1"
    !insertmacro cubitaRunGuard "api-state" $CubitaApiRestart
    !insertmacro cubitaRunGuard "pg-state" $CubitaPgRestart
    !insertmacro cubitaRunGuard "network-state" $CubitaNetworkRestartTask
    ${If} $CubitaApiRestart != "0"
    ${AndIf} $CubitaApiRestart != "7"
    ${AndIf} $CubitaApiRestart != "8"
      StrCpy $CubitaApiRestart "0"
      StrCpy $CubitaPgRestart "0"
      StrCpy $CubitaNetworkRestartTask "0"
      MessageBox MB_ICONSTOP|MB_OK "وضعیت سرویس سرور خوانده نشد؛ پیش از نصب آن را بررسی کنید." /SD IDOK
      SetErrorLevel 2
      Call CubitaRestorePreparing
      Quit
    ${EndIf}
    ${If} $CubitaPgRestart != "0"
    ${AndIf} $CubitaPgRestart != "7"
    ${AndIf} $CubitaPgRestart != "8"
      StrCpy $CubitaApiRestart "0"
      StrCpy $CubitaPgRestart "0"
      StrCpy $CubitaNetworkRestartTask "0"
      MessageBox MB_ICONSTOP|MB_OK "وضعیت دیتابیس خوانده نشد؛ نصب شروع نشده است. سرویس CubitaPostgres را بررسی کنید." /SD IDOK
      SetErrorLevel 2
      Call CubitaRestorePreparing
      Quit
    ${EndIf}
    ${If} $CubitaNetworkRestartTask != "0"
    ${AndIf} $CubitaNetworkRestartTask != "7"
    ${AndIf} $CubitaNetworkRestartTask != "8"
      StrCpy $CubitaApiRestart "0"
      StrCpy $CubitaPgRestart "0"
      StrCpy $CubitaNetworkRestartTask "0"
      MessageBox MB_ICONSTOP|MB_OK "وضعیت نگهداری شبکه خوانده نشد؛ نصب شروع نشده است." /SD IDOK
      SetErrorLevel 2
      Call CubitaRestorePreparing
      Quit
    ${EndIf}
    ${If} $CubitaRole != "server"
      ${If} $CubitaApiRestart != "0"
      ${OrIf} $CubitaPgRestart != "0"
        StrCpy $CubitaApiRestart "0"
        StrCpy $CubitaPgRestart "0"
        StrCpy $CubitaNetworkRestartTask "0"
        MessageBox MB_ICONSTOP|MB_OK "سرویس سرور روی این رایانه نصب است؛ نقش کلاینت مناسب نیست. نصاب کامل را با نقش سرور و مسیر قبلی اجرا کنید." /SD IDOK
        SetErrorLevel 2
        Call CubitaRestorePreparing
        Quit
      ${EndIf}
    ${EndIf}
    !ifndef CUBITA_HAS_SERVER
      ${If} $CubitaNetworkRestartTask != "0"
        StrCpy $CubitaNetworkRestartTask "0"
        MessageBox MB_ICONSTOP|MB_OK "این رایانه نگهداری شبکه دارد؛ برای حفظ ابزار شبکه، نصاب کامل سازمانی را دریافت کنید، نه فایل فقط‌کلاینت." /SD IDOK
        SetErrorLevel 2
        Call CubitaRestorePreparing
        Quit
      ${EndIf}
    !endif
    ; snapshot پیش از هر توقف است؛ شکست آماده‌سازی، وضعیت قبلی را بازیابی می‌کند.
    !insertmacro cubitaRunGuard "pause-network" $0
    ${If} $0 == "0"
    ${AndIf} $CubitaApiRestart == "7"
      !insertmacro cubitaRunGuard "stop-api" $0
    ${EndIf}
    ; PostgreSQL هم باید تمیز بسته شود: DLLهای بسته قفل‌اند و uninstaller قدیمی
    ; همهٔ پردازه‌های زیر INSTDIR را می‌کشد. اینجا سرویس را می‌بندیم، نه پردازه را.
    ${If} $0 == "0"
    ${AndIf} $CubitaPgRestart == "7"
      !insertmacro cubitaRunGuard "stop-pg" $0
    ${EndIf}
    ${If} $0 != "0"
      Call CubitaRestorePreparing
      MessageBox MB_ICONSTOP|MB_OK "آماده‌سازی سرویس‌ها انجام نشد؛ هیچ فایل برنامه‌ای جایگزین نشد. وضعیت سرویس و مجوز مدیر را بررسی کنید." /SD IDOK
      SetErrorLevel 2
      Quit
    ${EndIf}
    StrCpy $CubitaFilesTouched "1"
  !endif
!macroend

!ifdef CUBITA_HAS_SERVER
!macro customPageAfterChangeDir
  Page custom CubitaRolePageCreate CubitaRolePageLeave

  Function CubitaRolePageCreate
    !insertmacro MUI_HEADER_TEXT "نقشِ این رایانه" "کوبیتا سازمانی روی یک رایانه سرور است و بقیه به آن وصل می‌شوند."
    nsDialogs::Create 1018
    Pop $0
    ${NSD_CreateLabel} 0 0 100% 36u "این رایانه چه نقشی دارد؟ اگر مطمئن نیستید، «کلاینت» را انتخاب کنید؛ سرور فقط روی یک رایانه‌ی همیشه‌روشن در شرکت نصب می‌شود."
    Pop $0
    ${NSD_CreateRadioButton} 0 44u 100% 14u "سرور — دیتابیس و دفترِ شرکت روی همین رایانه نگه داشته می‌شود"
    Pop $CubitaRadioServer
    ${NSD_CreateRadioButton} 0 62u 100% 14u "کلاینت — این رایانه به سرورِ شرکت وصل می‌شود"
    Pop $CubitaRadioClient
    ${If} $CubitaRole == "server"
      ${NSD_Check} $CubitaRadioServer
    ${Else}
      ${NSD_Check} $CubitaRadioClient
    ${EndIf}
    ${NSD_CreateLabel} 0 86u 100% 30u "نصبِ سرور چند دقیقه طول می‌کشد: PostgreSQL، دو سرویسِ ویندوز و یک قاعده‌ی فایروال (فقط شبکه‌ی خصوصی) ساخته می‌شود."
    Pop $0
    nsDialogs::Show
  FunctionEnd

  Function CubitaRolePageLeave
    ${NSD_GetState} $CubitaRadioServer $0
    ${If} $CubitaExistingRole == "server"
    ${AndIf} $0 != ${BST_CHECKED}
      MessageBox MB_ICONSTOP|MB_OK "این رایانه سرور است؛ برای ارتقا نقش سرور را نگه دارید. تغییر نقش و انتقال دفتر، کار جداگانه است."
      Abort
    ${EndIf}
    ${If} $0 == ${BST_CHECKED}
      StrCpy $CubitaRole "server"
    ${Else}
      StrCpy $CubitaRole "client"
    ${EndIf}
  FunctionEnd
!macroend
!endif

!macro cubitaServerCommand ACTION
  InitPluginsDir
  File /oname=$PLUGINSDIR\cubita-server-command.ps1 "${CUBITA_INSTALLER_PAYLOAD_DIR}\installer-server-command.ps1"
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\cubita-server-command.ps1" -ServerPath "$INSTDIR\resources\server\cubita-server.exe" -Action "${ACTION}" -LogPath "$CubitaInstallLog"'
!macroend

!macro customInstall
  !insertmacro cubitaInstallLog "application files copied; role=$CubitaRole; directory=$INSTDIR"
  !ifdef CUBITA_HAS_SERVER
  ${If} $CubitaRole == "server"
    DetailPrint "راه‌اندازیِ سرورِ کوبیتا سازمانی…"
    !insertmacro cubitaServerCommand "install"
    Pop $0
    ${If} $0 != 0
      MessageBox MB_ICONSTOP|MB_OK "نصبِ سرور کامل نشد (کد $0). سرویس سرور ممکن است خاموش باشد؛ گزارش دقیق: $CubitaInstallLog. نصب را با نقش و مسیر قبلی کامل کنید؛ پوشهٔ داده را حذف نکنید." /SD IDOK
      StrCpy $CubitaApiRestart "0"
      StrCpy $CubitaPgRestart "0"
      SetErrorLevel 2
      Abort
    ${Else}
      ; کلاینتِ همین رایانه به سرورِ خودش وصل باشد — جادوگرِ اتصال لازم نیست.
      SetShellVarContext current
      ${IfNot} ${FileExists} "$APPDATA\Cubita Enterprise\server-settings.json"
        CreateDirectory "$APPDATA\Cubita Enterprise"
        FileOpen $1 "$APPDATA\Cubita Enterprise\server-settings.json" w
        FileWrite $1 '{"url": "${CUBITA_DEFAULT_URL}"}'
        FileClose $1
      ${EndIf}
      SetShellVarContext all
    ${EndIf}
  ${EndIf}
  StrCpy $CubitaApiRestart "0"
  StrCpy $CubitaPgRestart "0"
  ; مسیر exeِ task پس از جابه‌جایی/آپدیت هم دوباره به نصبِ معتبر گره بخورد.
  !insertmacro cubitaServerCommand "network-resume"
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "بازثبت نگهداری شبکه انجام نشد؛ تنظیم شبکه را در برنامه بررسی کنید." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  StrCpy $CubitaNetworkRestartTask "0"
  !endif
  WriteRegStr HKLM "${CUBITA_REG_KEY}" "Role" "$CubitaRole"
  !insertmacro cubitaRunGuard "maintenance-end" $0
  ${If} $0 != "0"
    SetErrorLevel 2
    Abort
  ${EndIf}
  StrCpy $CubitaRecoveryPaused "0"
!macroend

!macro customUnInstall
  ${ifNot} ${isUpdated}
    !insertmacro cubitaRunGuard "maintenance-begin" $1
    ${If} $1 != "0"
    ${AndIf} $1 != "7"
      MessageBox MB_ICONSTOP|MB_OK "بازیابی خودکار متوقف نشد؛ حذف را دوباره اجرا کنید." /SD IDOK
      SetErrorLevel 2
      Abort
    ${EndIf}
    !insertmacro cubitaRunGuard "pause-network" $1
    ${If} ${FileExists} "$INSTDIR\resources\server\cubita-server.exe"
      nsExec::ExecToLog '"$INSTDIR\resources\server\cubita-server.exe" network-disable'
      Pop $1
    ${EndIf}
    ReadRegStr $0 HKLM "${CUBITA_REG_KEY}" "Role"
    ${If} $0 == "server"
    ${AndIf} ${FileExists} "$INSTDIR\resources\server\cubita-server.exe"
      DetailPrint "برداشتنِ سرویس‌ها (داده‌ها در C:\ProgramData\Cubita می‌مانند)…"
      nsExec::ExecToLog '"$INSTDIR\resources\server\cubita-server.exe" uninstall-services'
      Pop $1
    ${EndIf}
    DeleteRegKey HKLM "${CUBITA_REG_KEY}"
  ${endIf}
!macroend
