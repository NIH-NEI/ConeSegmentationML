# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
import importlib.util
import site
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
    # For tensorflow/__init__.py -> tensorflow package directory
    return Path(spec.origin).resolve().parent


def collect_package_binary_tree(package_name, suffixes=(".dll", ".pyd")):
    """
    Collect package DLL/PYD files while preserving their package-relative
    destination paths. This is more explicit than collect_dynamic_libs(), and
    helps TensorFlow because Windows needs DLLs beside or beneath tensorflow/*.
    """
    root = package_root(package_name)
    out = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            rel_parent = path.parent.relative_to(root.parent)
            out.append((str(path), str(rel_parent)))
    return out




def collect_site_packages_glob(prefix, binary_suffixes=(".dll", ".pyd", ".so", ".dylib")):
    """
    Copy all top-level site-packages entries whose names start with `prefix`,
    preserving the same destination name under _internal/. This is useful for
    ITK's split wheels (itk, itk_core, itk_filtering, itk_io, itkConfig, etc.),
    where modules/data/native extension files are discovered lazily at runtime.

    Returns (datas, binaries).
    """
    roots = []
    for getter in (site.getsitepackages,):
        try:
            roots.extend(getter())
        except Exception:
            pass
    for key in ("purelib", "platlib"):
        try:
            roots.append(sysconfig.get_paths()[key])
        except Exception:
            pass

    data_items = []
    binary_items = []
    seen_roots = []
    for root in roots:
        if not root:
            continue
        root_path = Path(root).resolve()
        if root_path in seen_roots or not root_path.exists():
            continue
        seen_roots.append(root_path)

        for item in root_path.glob(f"{prefix}*"):
            name = item.name
            # Skip dist-info as whole-directory data; metadata is handled separately.
            # Keeping it here is usually harmless, but it bloats the bundle.
            if name.endswith((".dist-info", ".egg-info")):
                continue

            if item.is_dir():
                data_items.append((str(item), name))
                for f in item.rglob("*"):
                    if f.is_file() and f.suffix.lower() in binary_suffixes:
                        rel_parent = f.parent.relative_to(root_path)
                        binary_items.append((str(f), str(rel_parent)))
            elif item.is_file():
                if item.suffix.lower() in binary_suffixes:
                    binary_items.append((str(item), "."))
                else:
                    data_items.append((str(item), "."))

    return data_items, binary_items

def safe_extend(func, package_name):
    try:
        return func(package_name)
    except Exception:
        return []


hiddenimports = []
datas = []
binaries = []

# Core dynamic packages.
for pkg in ("tensorflow", "keras", "h5py", "numpy", "scipy", "skimage", "SimpleITK"):
    hiddenimports += safe_extend(collect_submodules, pkg)
    datas += safe_extend(collect_data_files, pkg)
    binaries += safe_extend(collect_dynamic_libs, pkg)
    datas += safe_extend(copy_metadata, pkg)

# ITK is split across several wheels/directories and uses lazy runtime loading.
# If manual copying of Lib/site-packages/itk* to _internal fixes the app, this
# block automates exactly that, while also registering native binaries.
itk_datas, itk_binaries = collect_site_packages_glob("itk")
datas += itk_datas
binaries += itk_binaries

for pkg in ("itk", "itkConfig", "itkExtras"):
    hiddenimports += safe_extend(collect_submodules, pkg)
    datas += safe_extend(collect_data_files, pkg)
    binaries += safe_extend(collect_dynamic_libs, pkg)

# Metadata for split ITK wheels. Missing ones are ignored because installed
# packages vary depending on which itk-* extras are present.
for dist_name in (
    "itk", "itk-core", "itk-filtering", "itk-numerics", "itk-io",
    "itk-registration", "itk-segmentation",
):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

# Critical TensorFlow step: preserve TensorFlow's own .dll/.pyd tree.
# This should include _pywrap_tensorflow_common.dll if it exists in the wheel.
binaries += collect_package_binary_tree("tensorflow")

# Keras 3 / TF often relies on package metadata for runtime backend discovery.
for dist_name in ("tensorflow", "tensorflow-intel", "keras", "h5py", "numpy", "scipy", "scikit-image", "SimpleITK"):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass


# Also copy TensorFlow's common DLL to top-level frozen library locations.
# TensorFlow sometimes requests this DLL by bare filename rather than full path.
try:
    tf_root = package_root("tensorflow")
    common_dll = tf_root / "python" / "_pywrap_tensorflow_common.dll"
    if common_dll.exists():
        binaries += [(str(common_dll), ".")]
except Exception:
    pass

# Remove duplicate binary/data tuples while preserving order.
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
hiddenimports = sorted(set(hiddenimports))


a = Analysis(
    ["__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas + [
        ("./model_weights", "./model_weights"),
        ("./Icons/*", "./Icons"),
        ("./Help/*", "./Help"),
    ],
    hiddenimports=hiddenimports + [
        "itk",
        "itkConfig",
        "itkExtras",
        "vtkmodules",
        "vtkmodules.all",
        "vtkmodules.qt.QVTKRenderWindowInteractor",
        "vtkmodules.util",
        "vtkmodules.util.numpy_support",
    ],
    hookspath=[],
    runtime_hooks=["pyi_rth_tensorflow_path_root.py"],
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="__main__",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    icon="Icons\\ConeSegmentationML256.ico",
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
