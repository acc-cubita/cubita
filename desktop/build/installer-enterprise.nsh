; نصابِ «کوبیتا سازمانی» — صفحه‌ی نقش (سرور/کلاینت) و نصبِ سرور (ENTERPRISE_PLAN.md، M4).
;
; همه‌ی کارِ واقعی در `cubita-server.exe` است (پایتونِ تست‌پذیر، `backend/app/onprem/`)؛ این
; فایل فقط می‌پرسد و همان exe را صدا می‌زند. `scripts/dist-enterprise.mjs` وقتی بسته‌ی سرور
; ساخته شده باشد `!define CUBITA_HAS_SERVER` را بالای این فایل می‌گذارد؛ بی‌آن نصاب فقط کلاینت است.
;
; سه قاعده:
; - حذفِ برنامه **هرگز** پوشه‌ی داده (C:\ProgramData\Cubita) را پاک نمی‌کند — دفترِ حسابداریِ شرکت است.
; - آپدیت (`isUpdated`) سرویس‌ها را برنمی‌دارد؛ فقط API را پیش از کپیِ فایل‌ها می‌ایستاند
;   (exeِ در حالِ اجرا قفل است) و `install` دوباره بالایش می‌آورد و مهاجرت‌ها را اجرا می‌کند.
; - نصبِ بی‌صدا (/S) نقشِ قبلی را نگه می‌دارد؛ نصبِ تازه‌ی بی‌صدا کلاینت است.

!include nsDialogs.nsh
!include LogicLib.nsh

!define CUBITA_REG_KEY "Software\Cubita Enterprise"
!define CUBITA_DEFAULT_URL "http://localhost:8420"

Var CubitaRole
Var CubitaRadioServer
Var CubitaRadioClient

!macro cubitaReadRole
  ReadRegStr $CubitaRole HKLM "${CUBITA_REG_KEY}" "Role"
  ${If} $CubitaRole == ""
    StrCpy $CubitaRole "client"
  ${EndIf}
!macroend

!macro customInit
  !insertmacro cubitaReadRole
  ; آپدیتِ سرور: exeِ سرویسِ API قفل است و کپیِ فایل‌ها بدونِ توقفش شکست می‌خورد.
  ${If} $CubitaRole == "server"
    nsExec::Exec 'net stop CubitaApi'
    Pop $0
  ${EndIf}
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
    ${If} $0 == ${BST_CHECKED}
      StrCpy $CubitaRole "server"
    ${Else}
      StrCpy $CubitaRole "client"
    ${EndIf}
  FunctionEnd
!macroend
!endif

!macro customInstall
  WriteRegStr HKLM "${CUBITA_REG_KEY}" "Role" "$CubitaRole"
  !ifdef CUBITA_HAS_SERVER
  ${If} $CubitaRole == "server"
    DetailPrint "راه‌اندازیِ سرورِ کوبیتا سازمانی…"
    nsExec::ExecToLog '"$INSTDIR\resources\server\cubita-server.exe" install'
    Pop $0
    ${If} $0 != 0
      MessageBox MB_ICONSTOP|MB_OK "نصبِ سرور کامل نشد (کد $0). جزئیات در فهرستِ بالای این پنجره و در C:\ProgramData\Cubita\logs است. نصاب را دوباره اجرا کنید؛ داده‌ای از دست نمی‌رود."
      SetErrorLevel 2
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
  !endif
!macroend

!macro customUnInstall
  ${ifNot} ${isUpdated}
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
