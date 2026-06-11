Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$BackendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "0.0.0.0" }
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$EnvPath = if ($env:AIGC_CONDA_ENV_PATH) { $env:AIGC_CONDA_ENV_PATH } else { (Join-Path $RepoRoot ".conda\envs\aigc-backend") }

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Host "未找到 conda 命令，请先安装 Miniconda/Anaconda 并确保 conda 在 PATH 中。"
    exit 1
}

if (-not (Test-Path $EnvPath)) {
    Write-Host "未找到 conda 环境目录：$EnvPath"
    Write-Host "建议先在项目根目录执行：conda env create -f backend/environment.yml"
    exit 1
}

Push-Location $RepoRoot
try {
    conda run -p $EnvPath uvicorn backend.app.main:app --reload --host $BackendHost --port $BackendPort
} finally {
    Pop-Location
}

