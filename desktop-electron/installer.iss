; SynapseAutomation Inno Setup Script
#define MyAppName "SynapseAutomation"
#define MyAppPublisher "Laihiujin"
#define MyAppURL ""
#define MyAppExeName "SynapseAutomation.exe"
#define APP_VERSION "1.1.0"

; These will be replaced by the batch script
#define MyAppVersion GetEnv("APP_VERSION")
#define MyAppBuildNum GetEnv("APP_BUILD_NUM")
#define SourceDir GetEnv("SOURCE_DIR")
#define OutputDir GetEnv("OUTPUT_DIR")
#if OutputDir == ""
  #define OutputDir GetEnv("OUTPUT_DIR_INNO")
#endif
#define IconFile GetEnv("ICON_FILE")
#define SkipOpt "dontcopy recursesubdirs skipifsourcedoesntexist"
#define SynenvDir SourceDir + "\resources\synenv"
#define SynenvSite SynenvDir + "\Lib\site-packages"
#define SynBackendDir SourceDir + "\resources\syn_backend"
#define AppSynenv "{app}\resources\synenv"
#define AppSynenvSite "{app}\resources\synenv\Lib\site-packages"
#define AppSynBackend "{app}\resources\syn_backend"
#define ExcludeTests "*\tests\*;*\test\*"

[Setup]
AppId={{8B5F4B5E-9A2C-4D3E-8F1A-6C7D8E9F0A1B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
OutputDir={#OutputDir}
OutputBaseFilename=SynapseAutomation-Setup-v{#MyAppBuildNum}
SetupIconFile={#IconFile}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
#ifexist "compiler:Languages\ChineseSimplified.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}\resources\syn_backend\data\cookies"
Name: "{app}\resources\syn_backend\cookiesFile"
Name: "{app}\resources\syn_backend\fingerprints"
Name: "{app}\resources\syn_backend\browser_profiles"
Name: "{app}\resources\syn_backend\videoFile"
Name: "{app}\resources\syn_backend\logs"
Name: "{app}\resources\syn_backend\backups"
Name: "{app}\resources\syn_backend\db"
Name: "{app}\resources\syn_backend\social-media-copilot-api\chrome-profile"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly; Excludes: "resources\syn_backend\*;resources\synenv\*"
Source: "{#SynenvDir}\*"; DestDir: "{#AppSynenv}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly skipifsourcedoesntexist; Excludes: "Lib\site-packages\*"
Source: "{#SynenvSite}\*"; DestDir: "{#AppSynenvSite}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly skipifsourcedoesntexist; Excludes: "{#ExcludeTests}"
Source: "{#SynBackendDir}\*"; DestDir: "{#AppSynBackend}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritereadonly; Excludes: "browser_profiles\*;cookiesFile\*;fingerprints\*"
Source: "{#SourceDir}\resources\syn_backend\social-media-copilot-api\chrome-profile\*"; DestDir: "{app}\resources\syn_backend\social-media-copilot-api\chrome-profile"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\data\cookies\*"; DestDir: "{app}\resources\syn_backend\data\cookies"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\cookiesFile\*"; DestDir: "{app}\resources\syn_backend\cookiesFile"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\fingerprints\*"; DestDir: "{app}\resources\syn_backend\fingerprints"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\browser_profiles\*"; DestDir: "{app}\resources\syn_backend\browser_profiles"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\videoFile\*"; DestDir: "{app}\resources\syn_backend\videoFile"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\logs\*"; DestDir: "{app}\resources\syn_backend\logs"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\backups\*"; DestDir: "{app}\resources\syn_backend\backups"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\__pycache__\*"; DestDir: "{app}\resources\syn_backend\__pycache__"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\*.pyc"; DestDir: "{app}\resources\syn_backend"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\*.pyo"; DestDir: "{app}\resources\syn_backend"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\db\*.db*"; DestDir: "{app}\resources\syn_backend\db"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\db\*.sqlite*"; DestDir: "{app}\resources\syn_backend\db"; Flags: {#SkipOpt}
Source: "{#SourceDir}\resources\syn_backend\db\frontend_accounts_snapshot.json"; DestDir: "{app}\resources\syn_backend\db"; Flags: dontcopy skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{userappdata}\SynapseAutomation\data"; Check: ShouldDeleteUserData
Type: filesandordirs; Name: "{localappdata}\SynapseAutomation\data"; Check: ShouldDeleteUserData

[Code]
var
  DeleteUserDataCheckBox: TNewCheckBox;
  DeleteUserData: Boolean;

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
