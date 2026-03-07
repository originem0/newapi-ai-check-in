"""Tests for OAuth browser helpers."""

from __future__ import annotations

import asyncio

from utils.oauth_browser import extract_oauth_query_params, should_treat_redirect_timeout_as_success


class DummyPage:
    def __init__(self, url: str, api_user=None):
        self.url = url
        self._api_user = api_user

    async def wait_for_function(self, *args, **kwargs):
        return None

    async def wait_for_timeout(self, *args, **kwargs):
        return None

    async def evaluate(self, script: str):
        if self._api_user is None:
            return None
        return f'{{"id": {self._api_user}}}'


class TestExtractOauthQueryParams:
    def test_returns_none_when_no_code(self):
        assert extract_oauth_query_params('https://example.com/callback?state=abc', 'acct') is None

    def test_returns_query_params_when_code_present(self):
        params = extract_oauth_query_params('https://example.com/callback?code=123&state=abc', 'acct')
        assert params is not None
        assert params['code'] == ['123']
        assert params['state'] == ['abc']


class TestShouldTreatRedirectTimeoutAsSuccess:
    def test_true_when_already_on_provider_origin(self):
        page = DummyPage('https://example.com/console/token')
        assert asyncio.run(should_treat_redirect_timeout_as_success(page, 'https://example.com'))

    def test_true_when_api_user_exists(self):
        page = DummyPage('https://other.example.com/intermediate', api_user=123)
        assert asyncio.run(should_treat_redirect_timeout_as_success(page, 'https://example.com'))
