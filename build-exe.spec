# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ITK does not like to be "frozen", so it will go to the distribution as data,
# rather than precompiled python code.
itk_datas = [x for x in collect_data_files('itk', include_py_files=True) if '__pycache__' not in x[0]]

a = Analysis(['__main__.py'],
             pathex=['.'],
             binaries=[],
             datas=itk_datas + \
                 [ ('./model_weights', './model_weights'),  ('./Icons/*', './Icons'),  ('./Help/*', './Help') ],
             hiddenimports=['itkBase', 'itkConfig', 'itkLazy', 'itkTypes', 'itkExtras',
                 'vtkmodules', 'vtkmodules.all', 'vtkmodules.qt.QVTKRenderWindowInteractor',
                 'vtkmodules.util','vtkmodules.util.numpy_support'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['itk', 'matplotlib.tests', 'PyQt4', 'PySide', '_tkinter',
                       'PyQt5.QtPrintSupport', 'PyQt5.QtMultimedia', 'PyQt5.QtBluetooth'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='ConeSegmentationML',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          icon='./Icons/ConeSegmentationML256.ico',
          console=False )
