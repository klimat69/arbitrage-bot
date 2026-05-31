"""Tests for license verification."""
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from utils import license as license_mod


class TestLicense:
    def test_get_hardware_id_stable(self):
        first = license_mod.get_hardware_id()
        second = license_mod.get_hardware_id()
        assert first == second
        assert len(first) == 32

    def test_verify_uses_cache(self, tmp_path, monkeypatch):
        cache_file = tmp_path / 'license.cache'
        monkeypatch.setattr(license_mod, 'CACHE_FILE', cache_file)
        cache_file.write_text(
            json.dumps(
                {
                    'license_key': 'KEY-123',
                    'valid': True,
                    'cached_at': time.time(),
                    'response': {'valid': True},
                }
            ),
            encoding='utf-8',
        )
        valid, msg = license_mod.verify_license('KEY-123', 'http://example.com/verify')
        assert valid is True
        assert 'cache' in msg.lower()

    @patch('utils.license.requests.post')
    def test_verify_rejects_invalid(self, mock_post, tmp_path, monkeypatch):
        cache_file = tmp_path / 'license.cache'
        monkeypatch.setattr(license_mod, 'CACHE_FILE', cache_file)
        response = MagicMock()
        response.json.return_value = {'valid': False, 'message': 'expired'}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        valid, msg = license_mod.verify_license('BAD', 'http://license.test/verify', skip_cache=True)
        assert valid is False
        assert msg == 'expired'
