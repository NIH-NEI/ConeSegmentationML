# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for building ConeSegmentationML.app on macOS.

Build from the project root on macOS with:
    pyinstaller --clean --noconfirm build-macos-tf2-app.spec

Notes:
- This spec is meant for macOS only.
- Do not reuse the Windows TensorFlow DLL runtime hook here.
- Build on the same CPU family you intend to distribute to, or build separate
  Intel and Apple Silicon apps. PyInstaller is not a cross-compiler.
"""

from pathlib import Path
import importlib.util
import sysconfig


from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
    copy_metadata,
)

block_cipher = None


def package_root(package_name):
    spec = importlib.util.find_spec(package_name)
    if spec is None or spec.origin is None:
        raise RuntimeError(f"Cannot find package: {package_name}")
    return Path(spec.origin).resolve().parent


def collect_package_binary_tree(package_name, suffixes=(".so", ".dylib")):
    """
    Preserve package-relative locations for native libraries inside packages.
    TensorFlow wheels contain many extension/shared-library files that may not
    all be detected by import scanning.
    """
    root = package_root(package_name)
    out = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            rel_parent = path.parent.relative_to(root.parent)
            out.append((str(path), str(rel_parent)))
    return out



def collect_site_packages_glob(prefix):
    """
    Copy all top-level site-packages entries whose names start with `prefix`
    while preserving package-relative locations. This is useful for ITK wheels,
    which are split across several top-level itk* packages and load resources
    dynamically at runtime.
    """
    site_packages = Path(sysconfig.get_paths()["purelib"]).resolve()
    datas_out = []
    binaries_out = []
    binary_suffixes = {".so", ".dylib"}

    for item in site_packages.glob(f"{prefix}*"):
        if item.name.endswith((".dist-info", ".egg-info")):
            # Metadata is handled with copy_metadata() below.
            continue

        if item.is_dir():
            for path in item.rglob("*"):
                if not path.is_file():
                    continue
                rel_parent = path.parent.relative_to(site_packages)
                pair = (str(path), str(rel_parent))
                if path.suffix.lower() in binary_suffixes:
                    binaries_out.append(pair)
                else:
                    datas_out.append(pair)
        elif item.is_file():
            pair = (str(item), ".")
            if item.suffix.lower() in binary_suffixes:
                binaries_out.append(pair)
            else:
                datas_out.append(pair)

    return datas_out, binaries_out

def safe_extend(func, package_name):
    try:
        return func(package_name)
    except Exception:
        return []


hiddenimports = []
datas = []
binaries = []

# Main scientific/ML stack.
# Keep PyQt5 out of the generic data/binary collection path; PyInstaller's Qt hooks
# should handle Qt frameworks and plugins so the macOS framework layout stays intact.
for pkg in (
    "tensorflow",
    "keras",
    "h5py",
    "numpy",
    "scipy",
    "skimage",
    "SimpleITK",
    "itk",
    "vtkmodules",
):
    hiddenimports += safe_extend(collect_submodules, pkg)
    datas += safe_extend(collect_data_files, pkg)
    binaries += safe_extend(collect_dynamic_libs, pkg)

# ITK is split across multiple itk* wheel packages and may load files dynamically.
# This mirrors the manual fix of copying site-packages/itk* into the frozen bundle.
itk_datas, itk_binaries = collect_site_packages_glob("itk")
datas += itk_datas
binaries += itk_binaries

# TensorFlow: preserve native shared objects in their package-relative paths.
binaries += collect_package_binary_tree("tensorflow")

# Runtime package metadata used by TensorFlow/Keras and friends.
for dist_name in (
    "tensorflow",
    "keras",
    "h5py",
    "numpy",
    "scipy",
    "scikit-image",
    "SimpleITK",
    "itk",
    "itk-core",
    "itk-filtering",
    "itk-numerics",
    "itk-io",
    "itk-registration",
    "itk-segmentation",
    "vtk",
):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

# Remove duplicates while preserving order.
def dedupe(seq):
    seen = set()
    out = []
    for item in seq:
        key = tuple(item) if isinstance(item, (tuple, list)) else item
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


binaries = dedupe(binaries)
datas = dedupe(datas)
hiddenimports = sorted(set(hiddenimports + [
    "itk",
    "itk.support",
    "itkConfig",
    "vtkmodules",
    "vtkmodules.all",
    "vtkmodules.qt.QVTKRenderWindowInteractor",
    "vtkmodules.util",
    "vtkmodules.util.numpy_support",
]))


a = Analysis(
    ["__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas + [
        ("./model_weights", "./model_weights"),
        ("./Icons/*", "./Icons"),
        ("./Help/*", "./Help"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "matplotlib.tests",
        "PyQt4",
        "PySide",
        "_tkinter",
        "PyQt5.QtPrintSupport",
        "PyQt5.QtMultimedia",
        "PyQt5.QtBluetooth",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ConeSegmentationML",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ConeSegmentationML",
)

app = BUNDLE(
    coll,
    name="ConeSegmentationML.app",
    icon="Icons/ConeSegmentationML256.icns",
    bundle_identifier="org.local.ConeSegmentationML",
    info_plist={
        "CFBundleName": "ConeSegmentationML",
        "CFBundleDisplayName": "ConeSegmentationML",
        "CFBundleExecutable": "ConeSegmentationML",
        "CFBundlePackageType": "APPL",
        "NSHighResolutionCapable": "True",
    },
)
