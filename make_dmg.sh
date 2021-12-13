rm -rf build/
rm -rf dist/
pyinstaller --clean --noconfirm build-app-dir.spec
rm -rf dist/ConeSegmentationML/
hdiutil create "ConeSegmentationML-Darwin0.dmg" -format UDRW -ov -volname "ConeSegmentationML" -fs HFS+ -srcfolder "dist/" -attach
ln -s /Applications /Volumes/ConeSegmentationML/Applications
mkdir /Volumes/ConeSegmentationML/.background
cp MacOS/DMGbackground.tif /Volumes/ConeSegmentationML/.background/background.tif
osascript MacOS/DMGSetup.scpt ConeSegmentationML
hdiutil detach /Volumes/ConeSegmentationML
python MacOS/licenseDMG.py ConeSegmentationML-Darwin0.dmg Help/License.txt
rm ConeSegmentationML-Darwin.dmg
hdiutil convert ConeSegmentationML-Darwin0.dmg -format UDZO -o dist/ConeSegmentationML-Darwin.dmg
rm ConeSegmentationML-Darwin0.dmg
