# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for macOS Intel (.app)."""
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'web' / 'templates'), 'web/templates'),
    ],
    hiddenimports=[
        'ccxt',
        'ccxt.pro',
        'ccxt.async_support',
        'dotenv',
        'aiohttp',
        'aiosqlite',
        'colorama',
        'fastapi',
        'uvicorn',
        'jinja2',
        'httpx',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='arbitrage-bot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'icon.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='arbitrage-bot',
)
app = BUNDLE(
    coll,
    name='arbitrage-bot.app',
    icon=str(ROOT / 'assets' / 'icon.ico'),
    bundle_identifier='com.arbitrage.bot',
)
