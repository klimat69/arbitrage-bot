# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Windows — ArbitrageBot.exe"""
from pathlib import Path

ROOT = Path(SPECPATH)

HIDDEN = [
    'asyncio',
    'ccxt',
    'ccxt.pro',
    'ccxt.async_support',
    'aiohttp',
    'websockets',
    'dotenv',
    'strategies',
    'strategies.large_order_detector',
    'risk',
    'risk.risk_manager',
    'utils.telegram',
    'bots.classic_bot',
    'aiosqlite',
    'colorama',
    'requests',
    'httpx',
]

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / 'web' / 'templates'), 'web/templates')],
    hiddenimports=HIDDEN,
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
    a.binaries,
    a.datas,
    [],
    name='ArbitrageBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
