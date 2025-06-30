pyinstaller --clean --noconfirm --onedir build-dir.spec
PowerShell -Command Compress-Archive -Path dist\ConeSegmentationML\* -DestinationPath dist\ConeSegmentationML-1.3.0-win64.zip -Force
