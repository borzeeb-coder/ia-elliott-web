@echo off
title Installation ELLIOTT Web
color 0B
cls
echo.
echo  ============================================
echo   Installation ELLIOTT Web
echo  ============================================
echo.

set DESKTOP=%USERPROFILE%\Desktop
set IA_DIR=C:\Users\borze\ia-elliott-web

echo [1/3] Copie des fichiers...
if exist "%DESKTOP%\ELLIOTT_Web" rmdir /S /Q "%DESKTOP%\ELLIOTT_Web"
xcopy "%IA_DIR%\*" "%DESKTOP%\ELLIOTT_Web\" /E /I /Q /Y

echo [2/3] Creation du raccourci...
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\shortcut_web.vbs"
echo sLinkFile = "%DESKTOP%\ELLIOTT Web.lnk" >> "%TEMP%\shortcut_web.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\shortcut_web.vbs"
echo oLink.TargetPath = "%DESKTOP%\ELLIOTT_Web\lancer_serveur.bat" >> "%TEMP%\shortcut_web.vbs"
echo oLink.WorkingDirectory = "%DESKTOP%\ELLIOTT_Web" >> "%TEMP%\shortcut_web.vbs"
echo oLink.Description = "ELLIOTT - Assistant Web" >> "%TEMP%\shortcut_web.vbs"
echo oLink.WindowStyle = 7 >> "%TEMP%\shortcut_web.vbs"
cscript //nologo "%TEMP%\shortcut_web.vbs"
del "%TEMP%\shortcut_web.vbs"

echo [3/3] Termine!
echo.
echo  ============================================
echo   ELLIOTT Web installe!
echo  ============================================
echo.
echo  Double-cliquez sur "ELLIOTT Web" pour lancer.
echo  Puis ouvrez http://localhost:5000 dans votre navigateur.
echo.
pause
