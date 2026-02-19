"""Tests for utils/http_utils.py"""

from utils.http_utils import proxy_resolve


class TestProxyResolve:
    def test_none_config(self):
        assert proxy_resolve(None) is None

    def test_empty_config(self):
        assert proxy_resolve({}) is None

    def test_simple_server(self):
        config = {"server": "http://proxy.example.com:8080"}
        assert proxy_resolve(config) == "http://proxy.example.com:8080"

    def test_server_with_auth(self):
        config = {
            "server": "http://proxy.example.com:8080",
            "username": "user",
            "password": "pass",
        }
        result = proxy_resolve(config)
        assert "user:pass@" in result
        assert "proxy.example.com:8080" in result

    def test_no_server_key(self):
        config = {"username": "user", "password": "pass"}
        assert proxy_resolve(config) is None

    def test_socks_proxy(self):
        config = {"server": "socks5://proxy.example.com:1080"}
        assert proxy_resolve(config) == "socks5://proxy.example.com:1080"
