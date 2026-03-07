#!/usr/bin/env python3
"""
OAuth 浏览器公共辅助函数
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from utils.get_headers import get_browser_headers, print_browser_headers
from utils.safe_logging import mask_secret


async def collect_browser_headers_if_needed(page, account_name: str, challenge_detected: bool) -> dict | None:
    """仅在检测到挑战页时返回浏览器指纹头部。"""
    if challenge_detected:
        browser_headers = await get_browser_headers(page)
        print_browser_headers(account_name, browser_headers)
        print(f'ℹ️ {account_name}: Browser headers returned (challenge detected)')
        return browser_headers

    print(f'ℹ️ {account_name}: Browser headers not returned (no challenge detected)')
    return None


async def read_api_user_from_local_storage(page, account_name: str) -> str | int | None:
    """从 localStorage.user 中读取 api user id。"""
    try:
        try:
            await page.wait_for_function('localStorage.getItem("user") !== null', timeout=10000)
        except Exception:
            await page.wait_for_timeout(5000)

        user_data = await page.evaluate("() => localStorage.getItem('user')")
        if user_data:
            user_obj = json.loads(user_data)
            api_user = user_obj.get('id')
            if api_user:
                print(f'✅ {account_name}: Got api user: {api_user}')
                return api_user
            print(f'⚠️ {account_name}: User id not found in localStorage')
            return None

        print(f'⚠️ {account_name}: User data not found in localStorage')
        return None
    except Exception as e:
        print(f'⚠️ {account_name}: Error reading user from localStorage: {e}')
        return None


def extract_oauth_query_params(page_url: str, account_name: str) -> dict[str, list[str]] | None:
    """提取 OAuth 回调中的 query 参数，并安全打印 code。"""
    parsed_url = urlparse(page_url)
    query_params = parse_qs(parsed_url.query)
    if 'code' in query_params:
        print(f"✅ {account_name}: OAuth code received: {mask_secret(query_params.get('code'))}")
        return query_params
    return None
