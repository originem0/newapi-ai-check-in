"""Tests for utils/browser_utils.py"""

from utils.browser_utils import filter_cookies, get_random_user_agent, parse_cookies


class TestParseCookies:
    def test_parse_dict(self):
        cookies = {"name1": "value1", "name2": "value2"}
        result = parse_cookies(cookies)
        assert result == cookies

    def test_parse_string(self):
        cookies = "name1=value1; name2=value2"
        result = parse_cookies(cookies)
        assert result == {"name1": "value1", "name2": "value2"}

    def test_parse_string_with_equals_in_value(self):
        cookies = "token=abc=def; session=xyz"
        result = parse_cookies(cookies)
        assert result == {"token": "abc=def", "session": "xyz"}

    def test_parse_empty_string(self):
        result = parse_cookies("")
        assert result == {}

    def test_parse_invalid_type(self):
        result = parse_cookies(123)
        assert result == {}


class TestFilterCookies:
    def test_filter_matching_domain(self):
        cookies = [
            {"name": "session", "value": "abc123", "domain": "example.com"},
            {"name": "other", "value": "xyz", "domain": "otherdomain.com"},
        ]
        result = filter_cookies(cookies, "https://example.com")
        assert result == {"session": "abc123"}

    def test_filter_dot_prefixed_domain(self):
        cookies = [
            {"name": "session", "value": "abc123", "domain": ".example.com"},
        ]
        result = filter_cookies(cookies, "https://example.com")
        assert result == {"session": "abc123"}

    def test_filter_subdomain_matching(self):
        cookies = [
            {"name": "session", "value": "abc123", "domain": ".example.com"},
        ]
        result = filter_cookies(cookies, "https://api.example.com")
        assert result == {"session": "abc123"}

    def test_filter_empty_cookies(self):
        result = filter_cookies([], "https://example.com")
        assert result == {}

    def test_filter_no_value(self):
        cookies = [
            {"name": "session", "value": "", "domain": "example.com"},
        ]
        result = filter_cookies(cookies, "https://example.com")
        assert result == {}


class TestGetRandomUserAgent:
    def test_returns_string(self):
        ua = get_random_user_agent()
        assert isinstance(ua, str)
        assert len(ua) > 50

    def test_returns_varied(self):
        """User agent pool should have enough variety"""
        user_agents = set()
        for _ in range(100):
            user_agents.add(get_random_user_agent())
        # With 11 UAs and 100 draws, we should see at least 5 distinct ones
        assert len(user_agents) >= 5

    def test_contains_browser_info(self):
        ua = get_random_user_agent()
        assert "Mozilla" in ua
