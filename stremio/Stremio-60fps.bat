@echo off
REM ALWAYS launch through this file. Starting the .exe directly leaves mpv
REM unable to find VapourSynth: the filter fails and no video appears -
REM you get audio only.
cd /d "%~dp0"
set "VSSCRIPT_PATH=G:\Tools\mpv-rife\vs\Lib\site-packages\vapoursynth\vsscript.dll"
set "PATH=G:\Tools\mpv-rife\vs;G:\Tools\mpv-rife\vs\Lib\site-packages\vapoursynth;%PATH%"
start "" "%~dp0stremio-shell-ng.exe" %*