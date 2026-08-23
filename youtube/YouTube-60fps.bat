@echo off
REM ---------------------------------------------------------------------
REM YouTube-60fps.bat - play a YouTube URL through mpv with interpolation
REM
REM Pass a URL as an argument, or leave it empty and it reads the URL from
REM the clipboard - copy the address in your browser, then run this.
REM
REM Edit MPV_DIR and ENGINE_DIR below to match your install.
REM ---------------------------------------------------------------------

set "ENGINE_DIR=G:\Tools\mpv-rife"
set "MPV_DIR=%ENGINE_DIR%\mpv"

set "VSSCRIPT_PATH=%ENGINE_DIR%\vs\Lib\site-packages\vapoursynth\vsscript.dll"
set "PATH=%ENGINE_DIR%\vs;%ENGINE_DIR%\vs\Lib\site-packages\vapoursynth;%PATH%"

if not "%~1"=="" (
    start "" "%MPV_DIR%\mpv.exe" %*
    exit /b
)

REM No argument: take the URL from the clipboard.
for /f "usebackq delims=" %%U in (`powershell -NoProfile -Command "Get-Clipboard -Raw"`) do (
    set "CLIP=%%U"
    goto :got
)
:got
if "%CLIP%"=="" (
    echo Clipboard is empty. Copy a video URL first, or pass one as argument.
    pause
    exit /b 1
)
echo Playing: %CLIP%
start "" "%MPV_DIR%\mpv.exe" "%CLIP%"
