"""Tests for x666/薄荷 reward flow."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from utils.config import AppConfig, ProviderConfig
from utils.get_cdk import get_x666_cdk


class DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, *args, **kwargs):
        self.cookies = self
        self._responses = [
            DummyResponse(200, {"success": True, "can_spin": False, "today_record": None}),
        ]

    def set(self, *args, **kwargs):
        return None

    def get(self, *args, **kwargs):
        return self._responses.pop(0)

    def post(self, *args, **kwargs):
        raise AssertionError("post should not be called when can_spin is false")

    def close(self):
        return None


class DummyAccountConfig:
    def __init__(self, access_token: str | None):
        self.proxy = None
        self.extra = {}
        self._access_token = access_token

    def get_display_name(self):
        return "x666 test"

    def get(self, key: str, default=None):
        if key == "access_token":
            return self._access_token
        if key == "global_proxy":
            return None
        return default


class TestX666ConfigValidation:
    @patch.dict(
        os.environ,
        {
            "ACCOUNTS": json.dumps(
                [
                    {
                        "provider": "x666",
                        "cookies": {"session": "abc"},
                        "api_user": "user1",
                    }
                ]
            )
        },
        clear=False,
    )
    def test_x666_account_requires_access_token(self):
        config = AppConfig.load_from_env()
        assert len(config.accounts) == 0


class TestX666RewardFlow:
    @patch("utils.get_cdk.curl_requests.Session", DummySession)
    def test_x666_today_record_none_does_not_crash(self):
        account_config = DummyAccountConfig(access_token="token123")
        results = list(get_x666_cdk(account_config))
        assert results == [(True, {"code": ""})]

    def test_x666_provider_has_no_manual_checkin_endpoint(self):
        config = AppConfig.load_from_env()
        provider: ProviderConfig = config.providers["x666"]
        assert provider.check_in_path is None
