pyinstaller --clean --noconfirm build-dir.spec
PowerShell -Command Compress-Archive -Path dist\ConeSegmentationML\* -DestinationPath dist\ConeSegmentationML-1.3.2-win64.zip -Force
