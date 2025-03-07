from setuptools import setup
'''
python setup.py py2app
'''

APP = ['ocr.py']  # 替换为你的主脚本名称
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icons/OCRicon.icns',  # 如果你有应用图标
    'packages': ['fitz', 'markdown', 'mistralai'],
    'plist': {
        'CFBundleName': 'Mistral OCR',
        'CFBundleDisplayName': 'Mistral OCR',
        'CFBundleIdentifier': 'com.david.mistral-ocr',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '© 2025 Lei Da (David)'
    }
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)