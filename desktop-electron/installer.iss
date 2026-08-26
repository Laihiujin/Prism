; Prism Inno Setup Script
#define MyAppName "Prism"
#define MyAppPublisher "Laihiujin"
#define MyAppURL ""
#define MyAppExeName "Prism.exe"
#define APP_VERSION "1.1.0"

; These will be replaced by the batch script
#define MyAppVersion GetEnv("APP_VERSION")
#define MyAppBuildNum GetEnv("APP_BUILD_NUM")
#define MyAppVersionFull MyAppVersion + "." + MyAppBuildNum
#define SourceDir GetEnv("SOURCE_DIR")
#define OutputDir GetEnv("OUTPUT_DIR")
#if OutputDir == ""
  #define OutputDir GetEnv("OUTPUT_DIR_INNO")
#endif
#define IconFile GetEnv("ICON_FILE")
#define SkipOpt "dontcopy recursesubdirs skipifsourcedoesntexist"
#define PrismenvDir SourceDir + "\resources\prismenv"
#define PrismenvPythonHome PrismenvDir + "\_python"
#define PrismenvSite PrismenvDir + "\Lib\site-packages"
#define PrismBackendDir SourceDir + "\resources\prism_backend"
#define AppPrismenv "{app}\resources\prismenv"
#define AppPrismenvPythonHome "{app}\resources\prismenv\_python"
#define AppPrismenvSite "{app}\resources\prismenv\Lib\site-packages"
#define AppPrismBackend "{app}\resources\prism_backend"
#define ExcludeTests "*\tests\*;*\test\*"

[Setup]
AppId={{8B5F4B5E-9A2C-4D3E-8F1A-6C7D8E9F0A1B}
AppName={#MyAppName}
AppVersion={#MyAppVersionFull}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersionFull}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
OutputDir={#OutputDir}
OutputBaseFilename=Prism-Setup-v{#MyAppVersionFull}
SetupIconFile={#IconFile}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=yes
CloseApplicationsFilter=Prism.exe

[Languages]
#ifexist "compiler:Languages\ChineseSimplified.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}\resources\prism_backend\data\cookies"
Name: "{app}\resources\prism_backend\cookiesFile"
Name: "{app}\resources\prism_backend\fingerprints"
Name: "{app}\resources\prism_backend\browser_profiles"
Name: "{app}\resources\prism_backend\videoFile"
Name: "{app}\resources\prism_backend\logs"
Name: "{app}\resources\prism_backend\backups"
Name: "{app}\resources\prism_backend\db"
Name: "{app}\resources\prism_backend\social-media-copilot-api\chrome-profile"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly; Excludes: "resources\prism_backend\*;resources\prismenv\*"
Source: "{#PrismenvDir}\*"; DestDir: "{#AppPrismenv}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly skipifsourcedoesntexist; Excludes: "Lib\site-packages\*"
Source: "{#PrismenvPythonHome}\*"; DestDir: "{#AppPrismenvPythonHome}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly skipifsourcedoesntexist
Source: "{#PrismenvSite}\*"; DestDir: "{#AppPrismenvSite}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly skipifsourcedoesntexist; Excludes: "{#ExcludeTests}"
Source: "{#PrismBackendDir}\*"; DestDir: "{#AppPrismBackend}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly; Excludes: "browser_profiles\*;cookiesFile\*;fingerprints\*"
Source: "{#SourceDir}\resources\prism_backend\social-media-copilot-api\chrome-profile\*"; DestDir: "{app}\resources\prism_backend\social-media-copilot-api\chrome-profile"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\data\cookies\*"; DestDir: "{app}\resources\prism_backend\data\cookies"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\cookiesFile\*"; DestDir: "{app}\resources\prism_backend\cookiesFile"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\fingerprints\*"; DestDir: "{app}\resources\prism_backend\fingerprints"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\browser_profiles\*"; DestDir: "{app}\resources\prism_backend\browser_profiles"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\videoFile\*"; DestDir: "{app}\resources\prism_backend\videoFile"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\logs\*"; DestDir: "{app}\resources\prism_backend\logs"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\backups\*"; DestDir: "{app}\resources\prism_backend\backups"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\__pycache__\*"; DestDir: "{app}\resources\prism_backend\__pycache__"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\*.pyc"; DestDir: "{app}\resources\prism_backend"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\*.pyo"; DestDir: "{app}\resources\prism_backend"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\db\*.db*"; DestDir: "{app}\resources\prism_backend\db"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\db\*.sqlite*"; DestDir: "{app}\resources\prism_backend\db"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\prism_backend\db\frontend_accounts_snapshot.json"; DestDir: "{app}\resources\prism_backend\db"; Flags: dontcopy skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{userappdata}\Prism\data"; Check: ShouldDeleteUserData
Type: filesandordirs; Name: "{localappdata}\Prism\data"; Check: ShouldDeleteUserData

[Code]
var
  DeleteUserDataCheckBox: TNewCheckBox;
  DeleteUserData: Boolean;
  ResultCode: Integer;

procedure ForceCloseRunningApp();
begin
  Exec('taskkill', '/F /IM Prism.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeSetup(): Boolean;
begin
  ForceCloseRunningApp();
  Result := True;
end;

procedure InitializeUninstallProgressForm();
begin
  DeleteUserData := False;
  DeleteUserDataCheckBox := TNewCheckBox.Create(UninstallProgressForm);
  DeleteUserDataCheckBox.Parent := UninstallProgressForm.StatusLabel.Parent;
  DeleteUserDataCheckBox.Caption := 'Remove user data (AppData)';
  DeleteUserDataCheckBox.Left := UninstallProgressForm.StatusLabel.Left;
  DeleteUserDataCheckBox.Top := UninstallProgressForm.StatusLabel.Top + UninstallProgressForm.StatusLabel.Height + ScaleY(8);
  DeleteUserDataCheckBox.Width := UninstallProgressForm.StatusLabel.Width;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usUninstall) and (DeleteUserDataCheckBox <> nil) then
    DeleteUserData := DeleteUserDataCheckBox.Checked;
end;

function ShouldDeleteUserData(): Boolean;
begin
  Result := DeleteUserData;
end;
