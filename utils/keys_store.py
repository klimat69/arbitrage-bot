"""Load and save API keys for ArbitrageBot (keys.json in app data dir)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_KEYS = {
    'binance_api_key': '',
    'binance_secret': '',
    'mexc_api_key': '',
    'mexc_secret': '',
}


def keys_file_path() -> Path:
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home()))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.config'
    return base / 'ArbitrageBot' / 'keys.json'


def load_keys() -> dict[str, str]:
    path = keys_file_path()
    if not path.exists():
        return dict(DEFAULT_KEYS)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        merged = dict(DEFAULT_KEYS)
        merged.update({k: str(v or '') for k, v in data.items() if k in DEFAULT_KEYS})
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_KEYS)


def save_keys(keys: dict[str, str]) -> None:
    path = keys_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: keys.get(k, '') for k in DEFAULT_KEYS}
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def mexc_keys_present(keys: dict[str, str]) -> bool:
    return bool(keys.get('mexc_api_key', '').strip() and keys.get('mexc_secret', '').strip())


def ensure_keys_interactive() -> dict[str, str]:
    """Prompt for keys on first run; Binance optional, MEXC required."""
    keys = load_keys()
    if mexc_keys_present(keys):
        return keys

    print('\n=== ArbitrageBot — API keys ===')
    print('Binance keys are optional (order book uses public WebSocket).')
    print('MEXC keys are required for futures execution.\n')

    if not keys.get('binance_api_key'):
        keys['binance_api_key'] = input('Binance API Key (Enter if none): ').strip()
    if not keys.get('binance_secret'):
        keys['binance_secret'] = input('Binance Secret (Enter if none): ').strip()
    if not keys.get('mexc_api_key'):
        keys['mexc_api_key'] = input('MEXC API Key: ').strip()
    if not keys.get('mexc_secret'):
        keys['mexc_secret'] = input('MEXC Secret: ').strip()

    if not mexc_keys_present(keys):
        print('Error: MEXC API key and secret are required.')
        sys.exit(1)

    save_keys(keys)
    print(f'Keys saved to {keys_file_path()}\n')
    return keys


def keys_for_exchange_service(keys: dict[str, str]) -> dict[str, Any]:
    """Map keys.json fields to ExchangeService credential dict."""
    return {
        'BINANCE_API_KEY': keys.get('binance_api_key', ''),
        'BINANCE_SECRET': keys.get('binance_secret', ''),
        'MEXC_API_KEY': keys.get('mexc_api_key', ''),
        'MEXC_SECRET': keys.get('mexc_secret', ''),
    }
