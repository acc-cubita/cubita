; Execute the production lifecycle with a fake guard only. No installed files,
; registry keys, real services, network settings or databases are changed.
Unicode true
RequestExecutionLevel user
SilentInstall silent
!include FileFunc.nsh
!define CUBITA_HAS_SERVER
!define APP_EXECUTABLE_FILENAME "Cubita Enterprise.exe"
!define INSTALL_REGISTRY_KEY "Software\CubitaInstallerQa\UnusedReadOnly"
!define CUBITA_REG_KEY "Software\CubitaInstallerQa\UnusedReadOnly"
!include "..\..\build\installer-enterprise.nsh"
!insertmacro customHeader
Name "Cubita installer QA - MOCK SERVICES ONLY"
OutFile "${QA_OUTPUT}\lifecycle-fixture.exe"
InstallDir "${QA_OUTPUT}"
Var Scenario

Function .onInit
  !insertmacro customInit
  ${GetParameters} $0
  ${GetOptions} $0 "/scenario=" $Scenario
  StrCpy $INSTDIR "$EXEDIR\$Scenario"
  CreateDirectory $INSTDIR
  ${If} $Scenario == "init-cancel"
    Quit
  ${EndIf}
  StrCpy $CubitaExistingRole "server"
  StrCpy $CubitaRole "server"
  StrCpy $CubitaExistingDirectory "$INSTDIR"
  ${If} $Scenario == "client-over-services"
  ${OrIf} $Scenario == "client-over-stopped-services"
    StrCpy $CubitaExistingRole "client"
    StrCpy $CubitaRole "client"
  ${EndIf}
  ${If} $Scenario == "wrong-directory"
    StrCpy $CubitaExistingDirectory "$EXEDIR\previous-directory"
  ${EndIf}
FunctionEnd

Section
  !insertmacro customCheckAppRunning
  ${If} $Scenario == "copy-failure"
    SetErrorLevel 2
    Abort
  ${EndIf}
  ; Simulate successful provision/health without invoking a server executable.
  StrCpy $CubitaApiRestart "0"
  StrCpy $CubitaPgRestart "0"
  StrCpy $CubitaNetworkRestartTask "0"
SectionEnd
