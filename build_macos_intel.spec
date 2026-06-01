# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for macOS Intel — ArbitrageBot.app"""
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
    'strategies.binance_futures_ws',
    'risk',
    'risk.risk_manager',
    'utils.telegram',
    'utils.keys_store',
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
    [],
    exclude_binaries=True,
    name='ArbitrageBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ArbitrageBot',
)
app = BUNDLE(
    coll,
    name='ArbitrageBot.app',
    bundle_identifier='com.arbitrage.bot',
)
