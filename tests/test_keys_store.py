"""Tests for keys.json storage."""
from utils import keys_store


class TestKeysStore:
    def test_save_and_load(self, tmp_path, monkeypatch):
        path = tmp_path / 'keys.json'
        monkeypatch.setattr(keys_store, 'keys_file_path', lambda: path)
        keys = {
            'binance_api_key': '',
            'binance_secret': '',
            'mexc_api_key': 'abc',
            'mexc_secret': 'def',
        }
        keys_store.save_keys(keys)
        loaded = keys_store.load_keys()
        assert loaded['mexc_api_key'] == 'abc'
        assert keys_store.mexc_keys_present(loaded)

    def test_mexc_keys_present(self):
        assert not keys_store.mexc_keys_present({'mexc_api_key': '', 'mexc_secret': ''})
        assert keys_store.mexc_keys_present({'mexc_api_key': 'x', 'mexc_secret': 'y'})
