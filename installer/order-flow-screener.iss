; Order Flow Screener (订单流微观结构量化终端) Inno Setup 标准 Windows 安装包脚本
; 严格遵循用户记忆规范：
; - 仅打包 PyInstaller --onedir 目录构建产物 (..\dist\OrderFlowScreener\*)，严禁 --onefile 单文件便携版
; - 启用 WizardStyle=modern 与 ChangesAssociations=yes
; - 绑定 256px 多尺寸高清图标 app_icon_v230.ico，生成桌面与开始菜单快捷方式及标准卸载程序
; - 支持 /VERYSILENT 静默覆盖升级

#define MyAppName "Order Flow Screener 订单流量化终端"
#define MyAppExeName "OrderFlowScreener.exe"
#define MyAppVersion "2.3.0"
#define MyAppPublisher "gouqizi2214730-source (Upstream: zadescoxp/order-flow-screener)"
#define MyAppURL "https://github.com/gouqizi2214730-source/order-flow-screener"

[Setup]
AppId={{D84F93A2-6C1E-4B98-9F53-202611210230}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\OrderFlowScreener
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=OrderFlowScreener-Setup-win64
SetupIconFile=..\app_icon_v230.ico
UninstallDisplayIcon={app}\app_icon_v230.ico
UninstallDisplayName={#MyAppName}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120,120
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
CloseApplications=force

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\OrderFlowScreener\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\app_icon_v230.ico"; DestDir: "{app}"; DestName: "app_icon_v230.ico"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon_v230.ico"; AppUserModelID: "gouqizi2214730.OrderFlowScreener.CN.v230"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{app}\app_icon_v230.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon_v230.ico"; AppUserModelID: "gouqizi2214730.OrderFlowScreener.CN.v230"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
