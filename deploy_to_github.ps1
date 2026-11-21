# ==============================================================================
# Order Flow Screener (订单流微观结构量化终端 v2.3.0) 全中文 Windows Setup.exe 一键发布脚本
# 适用账号: gouqizi2214730-source | 上游源仓库: zadescoxp/order-flow-screener
# ==============================================================================
$ErrorActionPreference = "Stop"

$GitHubUser = "gouqizi2214730-source"
$UpstreamRepo = "zadescoxp/order-flow-screener"
$TargetRepo = "$GitHubUser/order-flow-screener"
$WorkDir = Join-Path $env:TEMP "order-flow-screener-cn-deploy"
$BundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== [1/5] 检查 GitHub CLI (gh) 与 Git 环境 ===" -ForegroundColor Cyan
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "未检测到 GitHub CLI (gh)，请先运行: winget install GitHub.cli 并执行 gh auth login"
    exit 1
}

Write-Host "=== [2/5] 自动 Fork 上游仓库 $UpstreamRepo 至 $TargetRepo ===" -ForegroundColor Cyan
if (Test-Path $WorkDir) {
    Remove-Item -Recurse -Force $WorkDir
}
gh repo fork $UpstreamRepo --clone=false --default-branch-only 2>$null || $true
Start-Sleep -Seconds 3
git clone "https://github.com/$TargetRepo.git" $WorkDir

Write-Host "=== [3/5] 注入全中文 PySide6 桌面端、大模型/数据源中心、自动更新器与 Inno Setup 工程 ===" -ForegroundColor Cyan
$FilesToCopy = @(
    "launcher.py",
    "gui_app.py",
    "order_flow_engine.py",
    "data_sources.py",
    "llm_providers.py",
    "local_api_server.py",
    "updater.py",
    "requirements-desktop.txt",
    "README_CN.md"
)
foreach ($f in $FilesToCopy) {
    $src = Join-Path $BundleRoot $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $WorkDir $f) -Force
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $WorkDir "scripts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $WorkDir "installer") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $WorkDir ".github\workflows") | Out-Null

Copy-Item -Path (Join-Path $BundleRoot "scripts\generate_icon.py") -Destination (Join-Path $WorkDir "scripts\generate_icon.py") -Force
Copy-Item -Path (Join-Path $BundleRoot "installer\order-flow-screener.iss") -Destination (Join-Path $WorkDir "installer\order-flow-screener.iss") -Force
Copy-Item -Path (Join-Path $BundleRoot ".github\workflows\release-exe.yml") -Destination (Join-Path $WorkDir ".github\workflows\release-exe.yml") -Force

Write-Host "=== [4/5] 提交并推送到 https://github.com/$TargetRepo ===" -ForegroundColor Cyan
Push-Location $WorkDir
git add -A
git commit -m "feat(desktop-cn): add localized Chinese PySide6 GUI, local/cloud LLM API center, 12 data sources, auto-updater & Inno Setup workflow"
git push origin HEAD:main

Write-Host "=== [5/5] 启用并触发 GitHub Actions 云端打包发布 OrderFlowScreener-Setup-win64.exe ===" -ForegroundColor Cyan
gh workflow enable "release-exe.yml" -R $TargetRepo 2>$null || $true
gh workflow run "release-exe.yml" -R $TargetRepo -f release_tag="v2.3.0"
Pop-Location

Write-Host "`n✅ 已成功推送并触发云端自动打包！请访问以下地址下载安装包：" -ForegroundColor Green
Write-Host "   Actions 构建进度: https://github.com/$TargetRepo/actions" -ForegroundColor Yellow
Write-Host "   Releases 下载页 : https://github.com/$TargetRepo/releases" -ForegroundColor Yellow
