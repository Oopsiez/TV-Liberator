; One-click installer: no prerequisites, no Python, no Tizen Studio.
#define MyAppName "TV Liberator"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Oopsiez
DefaultDirName={autopf}\TV Liberator
DefaultGroupName=TV Liberator
OutputDir=..\..\dist
OutputBaseFilename=TV-Liberator-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
; The network guard binds UDP 53, so the app needs elevation.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
WizardStyle=modern
; sdb.exe is a background server the app starts; it keeps running after the
; app closes and is only visible on Task Manager's Details tab. Close it (and
; a running panel) ourselves instead of telling the user files are in use.
CloseApplications=force
RestartApplications=no

[Code]
procedure KillLeftovers;
var
  rc: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM sdb.exe',
       '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM "TV Liberator.exe"',
       '', SW_HIDE, ewWaitUntilTerminated, rc);
  Sleep(500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  KillLeftovers;
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  KillLeftovers;
  Result := True;
end;

[Files]
Source: "..\..\dist\TV Liberator\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\TV Liberator"; Filename: "{app}\TV Liberator.exe"
Name: "{autodesktop}\TV Liberator"; Filename: "{app}\TV Liberator.exe"

[Run]
; Let the guard and SDB through the Windows firewall so the TVs can reach them.
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""TV Liberator DNS"" dir=in action=allow protocol=UDP localport=53"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""TV Liberator Panel"" dir=in action=allow protocol=TCP localport=8777"; Flags: runhidden
Filename: "{app}\TV Liberator.exe"; Description: "Launch TV Liberator"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""TV Liberator DNS"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""TV Liberator Panel"""; Flags: runhidden
