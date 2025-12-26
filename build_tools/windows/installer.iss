; TermiVoxed Windows Installer Script
; Inno Setup Script for creating Windows installer
;
; Author: Santhosh T
; Copyright: 2025 LXUSBrain Technologies
;
; Build Instructions:
; 1. Install Inno Setup from https://jrsoftware.org/isdl.php
; 2. Build with PyInstaller first: pyinstaller --clean build_tools/windows/termivoxed.spec
; 3. Run this script with Inno Setup Compiler

#define MyAppName "TermiVoxed"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "LXUSBrain Technologies"
#define MyAppURL "https://termivoxed.com"
#define MyAppExeName "TermiVoxed.exe"
#define MyAppDescription "AI Voice-Over Dubbing Tool"

[Setup]
; Application identity
AppId={{B8F92D7E-5A3C-4D8F-9E2A-1B7C4D6E8F0A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/support
AppUpdatesURL={#MyAppURL}/download
AppCopyright=Copyright (C) 2025 {#MyAppPublisher}

; Default installation directory
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output settings
OutputDir=..\..\dist\installer
OutputBaseFilename=TermiVoxed-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Installer appearance
WizardStyle=modern
WizardResizable=yes
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; UAC settings
;RequestExecutionLevel=asInvoker

; Version info
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppDescription}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; License and info pages
LicenseFile=..\..\LICENSE
InfoBeforeFile=..\..\INSTALL_README.txt
InfoAfterFile=..\..\INSTALL_COMPLETE.txt

; Allow user to select installation type
AllowNoIcons=yes

; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add TermiVoxed to system PATH"; GroupDescription: "System Integration:"; Flags: checkedonce
Name: "associatefiles"; Description: "Associate .tvx project files with TermiVoxed"; GroupDescription: "File Associations:"; Flags: checkedonce

[Files]
; Main application files (from PyInstaller output)
Source: "..\..\dist\TermiVoxed\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; FFmpeg binaries (required dependency)
Source: "..\..\bin\ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\bin\ffprobe.exe"; DestDir: "{app}\bin"; Flags: ignoreversion skipifsourcedoesntexist

; Additional resources
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{#MyAppDescription}"

[Registry]
; File association for .tvx files
Root: HKCU; Subkey: "Software\Classes\.tvx"; ValueType: string; ValueName: ""; ValueData: "TermiVoxed.Project"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCU; Subkey: "Software\Classes\TermiVoxed.Project"; ValueType: string; ValueName: ""; ValueData: "TermiVoxed Project"; Flags: uninsdeletekey; Tasks: associatefiles
Root: HKCU; Subkey: "Software\Classes\TermiVoxed.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: associatefiles
Root: HKCU; Subkey: "Software\Classes\TermiVoxed.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: associatefiles

; Add app to PATH
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

; Application settings registry
Root: HKCU; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Clean up any running processes
Filename: "taskkill"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
; Clean up user data directories (optional - commented out to preserve user data)
; Type: filesandordirs; Name: "{userappdata}\{#MyAppName}"

[Code]
// Check if path needs to be added to PATH environment variable
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  // Look for the path with separator before and after
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

// Check for FFmpeg installation
function CheckFFmpeg(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c ffmpeg -version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if not Result or (ResultCode <> 0) then
  begin
    Result := FileExists(ExpandConstant('{app}\bin\ffmpeg.exe'));
  end
  else
    Result := True;
end;

// Initialize setup
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Check Windows version (Windows 10 or later required)
  if not IsWindows10OrNewer() then
  begin
    MsgBox('TermiVoxed requires Windows 10 or later.', mbError, MB_OK);
    Result := False;
  end;
end;

// Windows 10+ check
function IsWindows10OrNewer(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  Result := Version.Major >= 10;
end;

// Called at end of installation
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Check if FFmpeg is available
    if not CheckFFmpeg() then
    begin
      MsgBox('FFmpeg was not detected on your system. ' +
             'TermiVoxed requires FFmpeg for video processing. ' +
             'Please download FFmpeg from https://ffmpeg.org/download.html ' +
             'and add it to your system PATH, or copy ffmpeg.exe and ffprobe.exe ' +
             'to the bin folder in the installation directory.',
             mbInformation, MB_OK);
    end;
  end;
end;

// Handle uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    // Ask about removing user data
    if MsgBox('Do you want to remove all user data and settings?'#13#10#13#10 +
              'This will delete all projects, exports, and configuration files.',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\{#MyAppName}'), True, True, True);
    end;
  end;
end;
