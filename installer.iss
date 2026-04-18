; Inno Setup Script for Tender ERP Windows Installer
; ====================================================
; Prerequisites:
;   1. Build the app with: pyinstaller --noconfirm tender_erp_win.spec
;   2. Install Inno Setup: https://jrsoftware.org/isinfo.php
;   3. Compile this script: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;
; Output: Output\TenderERP-Setup.exe

[Setup]
AppName=Tender ERP
AppVersion=2.1.0
AppVerName=Tender ERP 2.1.0
AppPublisher=Tender ERP
AppPublisherURL=https://github.com/pandeyaadi2001-create/Tender-ERP
DefaultDirName={autopf}\TenderERP
DefaultGroupName=Tender ERP
OutputDir=Output
OutputBaseFilename=TenderERP-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=Tender ERP
DisableProgramGroupPage=yes
LicenseFile=
; Uncomment and set if you have an icon:
; SetupIconFile=assets\icon.ico

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Copy entire PyInstaller output directory
Source: "dist\TenderERP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tender ERP"; Filename: "{app}\TenderERP.exe"
Name: "{group}\Uninstall Tender ERP"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Tender ERP"; Filename: "{app}\TenderERP.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TenderERP.exe"; Description: "Launch Tender ERP"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
