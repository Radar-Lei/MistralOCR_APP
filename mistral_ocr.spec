# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['ocr.py'],  # 替换为你的主脚本名称
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['fitz', 'markdown', 'mistralai', 'PyQt6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Mistral OCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.icns',  # 如果你有图标
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Mistral OCR',
)
app = BUNDLE(
    coll,
    name='Mistral OCR.app',
    icon='icons/OCRicon.icns',  # 如果你有图标
    bundle_identifier='com.david.mistral-ocr',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHumanReadableCopyright': '© 2025 Lei Da (David)'
    },
)