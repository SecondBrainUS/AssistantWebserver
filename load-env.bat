@echo off
REM Loads environment variables from .env.build

setlocal EnableDelayedExpansion

REM Detect file path (assumes it's in the same directory)
set ENV_FILE=.env.build

if not exist %ENV_FILE% (
    echo [ERROR] %ENV_FILE% not found.
    exit /b 1
)

for /f "usebackq tokens=1,2 delims==" %%a in ("%ENV_FILE%") do (
    set "key=%%a"
    set "value=%%b"
    REM Skip blank lines and comments
    if defined key (
        if not "!key!"=="!key:#=!" (
            REM Skip commented lines starting with #
        ) else (
            set "!key!=!value!"
            REM Optional: echo what’s being loaded
            REM echo Loaded: !key!=!value!
        )
    )
)

echo [INFO] Environment variables from %ENV_FILE% loaded into current session.
endlocal & (
    for /f "usebackq tokens=1,2 delims==" %%a in ("%ENV_FILE%") do (
        set "%%a=%%b"
    )
)
