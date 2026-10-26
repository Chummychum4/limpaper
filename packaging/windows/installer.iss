; Inno Setup script for the Windows installer.
; Built by .github/workflows/release.yml after PyInstaller has produced
; dist\limpaper. Locally:  iscc /DAppVersion=2.0.0 packaging\windows\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C0D4B1E-7E5B-4C8B-9F3A-2B9C8E5D1A47}
AppName=limpaper
AppVersion={#AppVersion}
AppPublisher=limpaper contributors
AppPublisherURL=https://github.com/Chummychum4/limpaper
AppSupportURL=https://github.com/Chummychum4/limpaper/issues
DefaultDirName={localappdata}\Programs\limpaper
DefaultGroupName=limpaper
DisableProgramGroupPage=yes
; Per-user install: no administrator prompt
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=limpaper-setup-windows-x64
SetupIconFile=..\..\src\limpaper\assets\icon.ico
UninstallDisplayIcon={app}\limpaper.exe
LicenseFile=..\..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Restore my wallpaper when I log in"; GroupDescription: "Startup:"

[Files]
Source: "..\..\dist\limpaper\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\limpaper"; Filename: "{app}\limpaper.exe"
Name: "{group}\limpaper (terminal)"; Filename: "{app}\limpaper-cli.exe"; Parameters: "tui"
Name: "{group}\Uninstall limpaper"; Filename: "{uninstallexe}"
Name: "{autodesktop}\limpaper"; Filename: "{app}\limpaper.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "limpaper"; ValueData: """{app}\limpaper.exe"" restore"; \
    Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\limpaper.exe"; Description: "Launch limpaper"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop the wallpaper so mpv does not keep files locked
Filename: "{app}\limpaper-cli.exe"; Parameters: "stop"; Flags: runhidden; RunOnceId: "StopWallpaper"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
