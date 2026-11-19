@echo off
rem Builds Kunal's renderer.cpp into renderer.exe on Windows with MSYS2 (UCRT64).
rem One-time setup, in the "MSYS2 UCRT64" terminal:
rem     pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-glfw mingw-w64-ucrt-x86_64-glew
rem Then double-click this file, or run it from this folder.
setlocal
set MSYS=C:\msys64\ucrt64\bin
if not exist "%MSYS%\g++.exe" (
    echo MSYS2 UCRT64 g++ not found at %MSYS%
    exit /b 1
)
set PATH=%MSYS%;%PATH%
cd /d "%~dp0"
g++ -O2 -std=c++11 -DGLEW_STATIC renderer.cpp -o renderer.exe -static -lglew32 -lglfw3 -lopengl32 -lgdi32
if errorlevel 1 (
    echo Static build failed, trying the DLL build...
    g++ -O2 -std=c++11 renderer.cpp -o renderer.exe -lglew32 -lglfw3 -lopengl32 -lgdi32 || exit /b 1
    copy /y "%MSYS%\glfw3.dll" . >nul
    copy /y "%MSYS%\glew32.dll" . >nul
    copy /y "%MSYS%\libstdc++-6.dll" . >nul
    copy /y "%MSYS%\libgcc_s_seh-1.dll" . >nul
    copy /y "%MSYS%\libwinpthread-1.dll" . >nul
)
echo Built renderer.exe
