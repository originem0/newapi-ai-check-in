"""Tests for utils/config.py - ProviderConfig, AccountConfig, AppConfig"""

import json
import os
from unittest.mock import patch

from utils.config import (
    QUOTA_DIVISOR,
    AccountConfig,
    AppConfig,
    OAuthAccountConfig,
    ProviderConfig,
)


class TestProviderConfig:
    """ProviderConfig dataclass tests"""

    def test_default_auth_state_path_has_leading_slash(self):
        """C3 fix: auth_state_path should have a leading slash"""
        config = ProviderConfig(name="test", origin="https://example.com")
        assert config.auth_state_path == "/api/oauth/state"

    def test_from_dict_default_auth_state_path_has_leading_slash(self):
        """C3 fix: from_dict default should also have leading slash"""
        config = ProviderConfig.from_dict("test", {"origin": "https://example.com"})
        assert config.auth_state_path == "/api/oauth/state"

    def test_get_auth_state_url(self):
        config = ProviderConfig(name="test", origin="https://example.com")
        assert config.get_auth_state_url() == "https://example.com/api/oauth/state"

    def test_get_login_url(self):
        config = ProviderConfig(name="test", origin="https://example.com")
        assert config.get_login_url() == "https://example.com/login"

    def test_get_status_url(self):
        config = ProviderConfig(name="test", origin="https://example.com")
        assert config.get_status_url() == "https://example.com/api/status"

    def test_get_check_in_url_none(self):
        config = ProviderConfig(name="test", origin="https://example.com", check_in_path=None)
        assert config.get_check_in_url("user1") is None

    def test_get_check_in_url_string(self):
        config = ProviderConfig(name="test", origin="https://example.com", check_in_path="/api/user/checkin")
        assert config.get_check_in_url("user1") == "https://example.com/api/user/checkin"

    def test_get_check_in_url_callable(self):
        def custom_path(origin, user_id):
            return f"{origin}/api/checkin/{user_id}"

        config = ProviderConfig(name="test", origin="https://example.com", check_in_path=custom_path)
        assert config.get_check_in_url("user1") == "https://example.com/api/checkin/user1"

    def test_needs_waf_cookies(self):
        config = ProviderConfig(name="test", origin="https://example.com", bypass_method="waf_cookies")
        assert config.needs_waf_cookies() is True

        config2 = ProviderConfig(name="test", origin="https://example.com", bypass_method="cf_clearance")
        assert config2.needs_waf_cookies() is False

    def test_needs_cf_clearance(self):
        config = ProviderConfig(name="test", origin="https://example.com", bypass_method="cf_clearance")
        assert config.needs_cf_clearance() is True

    def test_needs_manual_check_in(self):
        config = ProviderConfig(name="test", origin="https://example.com", check_in_path="/api/user/checkin")
        assert config.needs_manual_check_in() is True

        config2 = ProviderConfig(name="test", origin="https://example.com", check_in_path=None)
        assert config2.needs_manual_check_in() is False

    def test_needs_manual_topup(self):
        config = ProviderConfig(
            name="test", origin="https://example.com", topup_path="/api/user/topup", get_cdk=lambda x: x
        )
        assert config.needs_manual_topup() is True

        config2 = ProviderConfig(name="test", origin="https://example.com", topup_path=None, get_cdk=lambda x: x)
        assert config2.needs_manual_topup() is False

    def test_get_linuxdo_auth_redirect_pattern(self):
        config = ProviderConfig(name="test", origin="https://example.com")
        assert config.get_linuxdo_auth_redirect_pattern() == "**https://example.com/oauth/**"

    def test_get_github_auth_redirect_pattern(self):
        config = ProviderConfig(name="test", origin="https://example.com")
        assert config.get_github_auth_redirect_pattern() == "**https://example.com/oauth/**"

    def test_get_topup_url(self):
        config = ProviderConfig(name="test", origin="https://example.com")
        assert config.get_topup_url() == "https://example.com/api/user/topup"

        config2 = ProviderConfig(name="test", origin="https://example.com", topup_path=None)
        assert config2.get_topup_url() is None

    def test_from_dict_basic(self):
        data = {"origin": "https://example.com"}
        config = ProviderConfig.from_dict("test", data)
        assert config.name == "test"
        assert config.origin == "https://example.com"
        assert config.login_path == "/login"
        assert config.isCustomize is False

    def test_from_dict_custom(self):
        data = {
            "origin": "https://example.com",
            "login_path": "/custom-login",
            "api_user_key": "x-api-user",
            "bypass_method": "waf_cookies",
        }
        config = ProviderConfig.from_dict("test", data, is_customize=True)
        assert config.login_path == "/custom-login"
        assert config.api_user_key == "x-api-user"
        assert config.bypass_method == "waf_cookies"
        assert config.isCustomize is True


class TestAccountConfig:
    """AccountConfig dataclass tests"""

    def test_from_dict_basic(self):
        data = {"provider": "neb", "cookies": "abc=123", "api_user": "user1"}
        config = AccountConfig.from_dict(data)
        assert config.provider == "neb"
        assert config.cookies == "abc=123"
        assert config.api_user == "user1"

    def test_from_dict_extra_fields(self):
        data = {"provider": "x666", "cookies": "abc=123", "api_user": "user1", "access_token": "mytoken123"}
        config = AccountConfig.from_dict(data)
        assert config.extra == {"access_token": "mytoken123"}
        assert config.get("access_token") == "mytoken123"

    def test_get_known_attribute(self):
        config = AccountConfig(provider="test", api_user="user1")
        assert config.get("provider") == "test"
        assert config.get("api_user") == "user1"

    def test_get_extra_field(self):
        config = AccountConfig(provider="test", extra={"access_token": "tok123"})
        assert config.get("access_token") == "tok123"

    def test_get_default(self):
        config = AccountConfig(provider="test")
        assert config.get("nonexistent", "default_val") == "default_val"

    def test_get_display_name_with_name(self):
        config = AccountConfig(provider="test", name="My Account")
        assert config.get_display_name() == "My Account"

    def test_get_display_name_without_name(self):
        config = AccountConfig(provider="neb")
        assert config.get_display_name(0) == "neb 1"
        assert config.get_display_name(2) == "neb 3"


class TestOAuthAccountConfig:
    def test_from_dict(self):
        config = OAuthAccountConfig.from_dict({"username": "user", "password": "pass"})
        assert config.username == "user"
        assert config.password == "pass"


class TestAppConfig:
    """AppConfig tests"""

    @patch.dict(os.environ, {"ACCOUNTS": "[]"}, clear=False)
    def test_load_empty_accounts(self):
        config = AppConfig.load_from_env()
        assert len(config.accounts) == 0

    @patch.dict(os.environ, {}, clear=False)
    def test_load_missing_accounts_env(self):
        # Remove ACCOUNTS if set
        os.environ.pop("ACCOUNTS", None)
        config = AppConfig.load_from_env()
        assert len(config.accounts) == 0

    def test_builtin_providers_loaded(self):
        """Verify all built-in providers are present"""
        config = AppConfig.load_from_env()
        expected_providers = [
            "anyrouter", "agentrouter", "wong", "huan666", "runawaytime",
            "x666", "kfc", "neb", "elysiver", "hotaru", "b4u",
            "lightllm", "takeapi", "thatapi", "duckcoding", "free-duckcoding",
            "taizi", "openai-test", "icat", "chengtx",
        ]
        for name in expected_providers:
            assert name in config.providers, f"Provider '{name}' missing"

    def test_hotaru_origin_is_correct(self):
        """Verify hotaru origin was fixed to hotaruapi.com"""
        config = AppConfig.load_from_env()
        assert config.providers["hotaru"].origin == "https://hotaruapi.com"

    def test_provider_auth_state_paths_have_leading_slash(self):
        """C3 fix: all built-in providers should have leading slash in auth_state_path"""
        config = AppConfig.load_from_env()
        for name, provider in config.providers.items():
            assert provider.auth_state_path.startswith("/"), (
                f"Provider '{name}' auth_state_path missing leading slash: {provider.auth_state_path}"
            )

    @patch.dict(
        os.environ,
        {
            "ACCOUNTS": json.dumps([
                {"provider": "neb", "cookies": "abc=123", "api_user": "user1"},
            ]),
        },
        clear=False,
    )
    def test_load_valid_account(self):
        config = AppConfig.load_from_env()
        assert len(config.accounts) == 1
        assert config.accounts[0].provider == "neb"

    @patch.dict(
        os.environ,
        {
            "ACCOUNTS_LINUX_DO": json.dumps([
                {"username": "user1", "password": "pass1"},
            ]),
        },
        clear=False,
    )
    def test_load_linux_do_accounts(self):
        config = AppConfig.load_from_env()
        assert len(config.linux_do_accounts) == 1
        assert config.linux_do_accounts[0].username == "user1"

    @patch.dict(
        os.environ,
        {"PROXY": '{"server": "http://proxy.example.com:8080"}'},
        clear=False,
    )
    def test_load_proxy_json(self):
        config = AppConfig.load_from_env()
        assert config.global_proxy is not None
        assert config.global_proxy["server"] == "http://proxy.example.com:8080"

    @patch.dict(
        os.environ,
        {"PROXY": "http://proxy.example.com:8080"},
        clear=False,
    )
    def test_load_proxy_string(self):
        config = AppConfig.load_from_env()
        assert config.global_proxy is not None
        assert config.global_proxy["server"] == "http://proxy.example.com:8080"


class TestQuotaDivisor:
    def test_quota_divisor_value(self):
        assert QUOTA_DIVISOR == 500000

    def test_quota_conversion(self):
        """Verify the constant produces correct dollar values"""
        raw_quota = 1000000
        assert round(raw_quota / QUOTA_DIVISOR, 2) == 2.0
