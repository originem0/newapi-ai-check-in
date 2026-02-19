"""Tests for utils/notify.py"""

import os
from unittest.mock import patch

import pytest

from utils.notify import NotificationKit


@pytest.fixture
def kit_no_config():
    """NotificationKit with no environment variables set"""
    with patch.dict(os.environ, {}, clear=True):
        return NotificationKit()


@pytest.fixture
def kit_with_pushplus():
    """NotificationKit with only PushPlus configured"""
    env = {"PUSHPLUS_TOKEN": "test_token"}
    with patch.dict(os.environ, env, clear=True):
        return NotificationKit()


class TestNotificationKitInit:
    def test_no_env_vars(self, kit_no_config):
        assert kit_no_config.pushplus_token is None
        assert kit_no_config.server_push_key is None
        assert kit_no_config.email_user == ""

    def test_with_pushplus(self, kit_with_pushplus):
        assert kit_with_pushplus.pushplus_token == "test_token"


class TestPushMessage:
    def test_no_configured_methods_skips(self, kit_no_config, capsys):
        """H4 fix: should skip when no methods are configured, not try all and fail"""
        kit_no_config.push_message("Title", "Content")
        output = capsys.readouterr().out
        assert "No notification methods configured" in output

    @patch("utils.notify.curl_requests.post")
    def test_only_configured_methods_called(self, mock_post, kit_with_pushplus):
        """H4 fix: only PushPlus should be attempted, not all 7"""
        kit_with_pushplus.push_message("Title", "Content")
        # Should only be called once (PushPlus)
        assert mock_post.call_count == 1

    @patch("utils.notify.curl_requests.post")
    def test_pushplus_uses_https(self, mock_post, kit_with_pushplus):
        """H5 fix: PushPlus URL should use HTTPS"""
        kit_with_pushplus.send_pushplus("Title", "Content")
        call_args = mock_post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert url.startswith("https://"), f"PushPlus URL should use HTTPS, got: {url}"


class TestSendMethods:
    def test_send_email_raises_without_config(self, kit_no_config):
        with pytest.raises(ValueError, match="Email configuration not set"):
            kit_no_config.send_email("Title", "Content")

    def test_send_pushplus_raises_without_config(self, kit_no_config):
        with pytest.raises(ValueError, match="PushPlus Token not configured"):
            kit_no_config.send_pushplus("Title", "Content")

    def test_send_serverPush_raises_without_config(self, kit_no_config):
        with pytest.raises(ValueError, match="Server Push key not configured"):
            kit_no_config.send_serverPush("Title", "Content")

    def test_send_dingtalk_raises_without_config(self, kit_no_config):
        with pytest.raises(ValueError, match="DingTalk Webhook not configured"):
            kit_no_config.send_dingtalk("Title", "Content")

    def test_send_feishu_raises_without_config(self, kit_no_config):
        with pytest.raises(ValueError, match="Feishu Webhook not configured"):
            kit_no_config.send_feishu("Title", "Content")

    def test_send_wecom_raises_without_config(self, kit_no_config):
        with pytest.raises(ValueError, match="WeChat Work Webhook not configured"):
            kit_no_config.send_wecom("Title", "Content")

    def test_send_telegram_raises_without_config(self, kit_no_config):
        with pytest.raises(ValueError, match="Telegram Bot Token or Chat ID not configured"):
            kit_no_config.send_telegram("Title", "Content")
