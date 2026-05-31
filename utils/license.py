"""
License verification via HTTP POST to a license server.

Result is cached locally for 24 hours. No auto-update logic is included.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import requests

from utils.logger import log_error, log_info, log_warning

CACHE_FILE = Path(__file__).resolve().parent.parent / 'license.cache'
CACHE_TTL_SECONDS = 86400


def get_hardware_id() -> str:
    """Build a stable machine identifier."""
    node = platform.node() or 'unknown'
    mac = uuid.getnode()
    raw = f"{node}:{mac}:{platform.system()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _load_cache(license_key: str) -> Optional[dict[str, Any]]:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        if data.get('license_key') != license_key:
            return None
        if time.time() - data.get('cached_at', 0) > CACHE_TTL_SECONDS:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(license_key: str, valid: bool, payload: dict[str, Any]) -> None:
    try:
        CACHE_FILE.write_text(
            json.dumps(
                {
                    'license_key': license_key,
                    'valid': valid,
                    'cached_at': time.time(),
                    'response': payload,
                },
                indent=2,
            ),
            encoding='utf-8',
        )
    except OSError as exc:
        log_warning(f"Could not write license cache: {exc}")


def verify_license(
    license_key: str,
    server_url: str,
    *,
    skip_cache: bool = False,
    timeout: float = 15.0,
) -> tuple[bool, str]:
    """
    Verify license key against remote server.

    Returns:
        (valid, message)
    """
    if not license_key:
        return False, 'LICENSE_KEY is not set'

    if not server_url:
        return False, 'LICENSE_SERVER_URL is not set'

    if not skip_cache:
        cached = _load_cache(license_key)
        if cached is not None:
            valid = bool(cached.get('valid'))
            log_info('License loaded from cache (valid within 24h)')
            return valid, 'Cached license validation'

    hwid = get_hardware_id()
    body = {'license': license_key, 'hwid': hwid}

    try:
        response = requests.post(server_url, json=body, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        log_error(f"License server request failed: {exc}")
        cached = _load_cache(license_key)
        if cached and cached.get('valid'):
            log_warning('Using cached license due to server unreachable')
            return True, 'Offline cache fallback'
        return False, f'License server unreachable: {exc}'
    except ValueError:
        return False, 'Invalid JSON response from license server'

    valid = bool(payload.get('valid'))
    _save_cache(license_key, valid, payload)

    if valid:
        log_info('License verified successfully')
        return True, payload.get('message', 'License valid')

    message = payload.get('message', 'Invalid license key')
    log_error(f"License rejected: {message}")
    return False, message


def require_valid_license_or_exit() -> None:
    """Load env vars, verify license, exit process if invalid."""
    from dotenv import load_dotenv

    load_dotenv()
    license_key = os.getenv('LICENSE_KEY', '')
    server_url = os.getenv('LICENSE_SERVER_URL', '')

    valid, message = verify_license(license_key, server_url)
    if not valid:
        print(f'License check failed: {message}', file=sys.stderr)
        sys.exit(1)
