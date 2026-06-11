@echo off
setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

if "%BACKEND_HOST%"=="" set "BACKEND_HOST=0.0.0.0"
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"

if "%AIGC_CONDA_ENV_PATH%"=="" (
  set "AIGC_CONDA_ENV_PATH=%REPO_ROOT%\.conda\envs\aigc-backend"
)

where conda >nul 2>nul
if errorlevel 1 (
  echo 未找到 conda 命令，请先安装 Miniconda/Anaconda 并确保 conda 在 PATH 中。
  exit /b 1
)

if not exist "%AIGC_CONDA_ENV_PATH%" (
  echo 未找到 conda 环境目录：%AIGC_CONDA_ENV_PATH%
  echo 建议先在项目根目录执行：conda env create -f backend/environment.yml
  exit /b 1
)

pushd "%REPO_ROOT%"
conda run -p "%AIGC_CONDA_ENV_PATH%" uvicorn backend.app.main:app --reload --host %BACKEND_HOST% --port %BACKEND_PORT%
popd

endlocal

