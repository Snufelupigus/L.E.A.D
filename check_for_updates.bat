@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if not exist ".git" (
    echo ERROR: This folder is not a git repository.
    exit /b 10
)

where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: Git is not installed or is not available on PATH.
    exit /b 11
)

for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%i"
if not defined BRANCH set "BRANCH=main"
if /I "%BRANCH%"=="HEAD" set "BRANCH=main"

git diff --quiet --ignore-submodules --exit-code
if errorlevel 1 (
    echo ERROR: Local tracked changes were detected. Commit or stash them before updating.
    exit /b 12
)

git diff --cached --quiet --ignore-submodules --exit-code
if errorlevel 1 (
    echo ERROR: Staged changes were detected. Commit or stash them before updating.
    exit /b 12
)

echo Checking origin/%BRANCH% for updates...
echo Ignored runtime folders such as Databases and backups are not modified by this updater.

git fetch origin
if errorlevel 1 (
    echo ERROR: git fetch failed.
    exit /b 13
)

for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "LOCAL_HEAD=%%i"
for /f "delims=" %%i in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE_HEAD=%%i"

if not defined REMOTE_HEAD (
    echo ERROR: Remote branch origin/%BRANCH% was not found.
    exit /b 14
)

if /I "%LOCAL_HEAD%"=="%REMOTE_HEAD%" (
    echo UP_TO_DATE: Already running the latest version from origin/%BRANCH%.
    exit /b 0
)

echo Applying updates from origin/%BRANCH%...
git pull --ff-only origin %BRANCH%
if errorlevel 1 (
    echo ERROR: git pull failed.
    exit /b 15
)

echo UPDATED: Repository updated successfully. Restart the application to load the new version.
exit /b 0
