
Packaging into single executable or directory.

1. Download and install Miniconda (or Anaconda).
2. Run Anaconda Prompt, cd to directory '<...>/ConeSegmentationML'.
3. Create virtual environment (do this once, next time skip to the next step):
   conda env create --file conda-environment.yml
4. Activate virtual environment:
   conda activate ConeSegmentation
5. (optional step) Make sure the VE is good for running Python code directly:
   python __main__.py
6. (optional step) Build target executable as single file:
   make_exe.bat
The resulting exe is: <...>/ConeSegmentationML/dist/ConeSegmentationML.exe
Such an exe is ready to go right away, but it takes a long time to load. A better idea maybe to build the directory:
7. Build target executable as a directory:
   make_dir.bat
The resulting exe is: <...>/ConeSegmentationML/dist/ConeSegmentationML/__main__.exe .
To distribute it to another machine, copy the entire directory <...>/ConeSegmentationML/dist/ConeSegmentationML,
then make a shortcut to __main__exe .

To delete the virtual environment, deactivate it first (if it is active):
   conda deactivate
Then type:
   conda env remove --name ConeSegmentation


Building NSIS .exe distro for Win64:

Install NSIS and add its directory (such as "C:\Program Files (x86)\NSIS") to system PATH.
Follow steps 1-4, then 7 (build target as directory), then type in the command:
   makensis build-win64-installer.nsi
The resiult is: <...>/ConeSegmentationML/dist/ConeSegmentationML-win64.exe


Building .dmg distro for Mac:

Follow steps 1 to 4, then type in the following command:
   sh make_dmg.sh
If it asks you to give permission for Terminal to access Finder, say yes.
The resiult is: <...>/ConeSegmentationML/dist/ConeSegmentationML-Darwin.dmg

