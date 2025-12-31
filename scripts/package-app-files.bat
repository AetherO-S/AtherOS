@echo off
echo ========================================
echo  AETHER-OS App Files Packager
echo ========================================
echo.

:: Create temp directory
if exist "release-temp" rmdir /s /q "release-temp"
mkdir "release-temp\app"

:: Copy app files (NOT node_modules, NOT Electron)
echo Copying app files...
xcopy /E /I /Y "src" "release-temp\app\src"
xcopy /E /I /Y "plugins" "release-temp\app\plugins"
xcopy /E /I /Y "build" "release-temp\app\build"
copy "main.js" "release-temp\app\"
copy "preload.js" "release-temp\app\"
copy "package.json" "release-temp\app\"
copy "version.json" "release-temp\app\"

:: Create the zip
echo.
echo Creating aether-os-app-files.zip...
cd release-temp
powershell -Command "Compress-Archive -Path 'app\*' -DestinationPath '..\aether-os-app-files.zip' -Force"
cd ..

:: Cleanup
rmdir /s /q "release-temp"

echo.
echo ========================================
echo  Done! Created: aether-os-app-files.zip
echo ========================================
echo.
echo Upload this file to your GitHub Release!
echo.
pause
