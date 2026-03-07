"""Tests for OAuth browser helpers."""

from __future__ import annotations

from utils.oauth_browser import extract_oauth_query_params


class TestExtractOauthQueryParams:
    def test_returns_none_when_no_code(self):
        assert extract_oauth_query_params('https://example.com/callback?state=abc', 'acct') is None

    def test_returns_query_params_when_code_present(self):
        params = extract_oauth_query_params('https://example.com/callback?code=123&state=abc', 'acct')
        assert params is not None
        assert params['code'] == ['123']
        assert params['state'] == ['abc']
