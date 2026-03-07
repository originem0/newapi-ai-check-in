#!/usr/bin/env python3
"""
CheckIn 运行时辅助函数
"""

from __future__ import annotations

from utils.browser_utils import get_random_user_agent


def build_common_headers(account_name: str, browser_headers: dict | None) -> dict:
    """构建整个流程复用的公用请求头。"""
    if browser_headers:
        common_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en,en-US;q=0.9,zh;q=0.8,en-CN;q=0.7,zh-CN;q=0.6',
            'Cache-Control': 'no-store',
            'Pragma': 'no-cache',
            'User-Agent': browser_headers.get('User-Agent', get_random_user_agent()),
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }

        if 'sec-ch-ua' in browser_headers:
            common_headers.update(
                {
                    'sec-ch-ua': browser_headers.get('sec-ch-ua', ''),
                    'sec-ch-ua-mobile': browser_headers.get('sec-ch-ua-mobile', '?0'),
                    'sec-ch-ua-platform': browser_headers.get('sec-ch-ua-platform', ''),
                    'sec-ch-ua-platform-version': browser_headers.get('sec-ch-ua-platform-version', ''),
                    'sec-ch-ua-arch': browser_headers.get('sec-ch-ua-arch', ''),
                    'sec-ch-ua-bitness': browser_headers.get('sec-ch-ua-bitness', ''),
                    'sec-ch-ua-full-version': browser_headers.get('sec-ch-ua-full-version', ''),
                    'sec-ch-ua-full-version-list': browser_headers.get('sec-ch-ua-full-version-list', ''),
                    'sec-ch-ua-model': browser_headers.get('sec-ch-ua-model', '""'),
                }
            )
            print(f'ℹ️ {account_name}: Using browser fingerprint headers (with Client Hints)')
        else:
            print(f'ℹ️ {account_name}: Using browser fingerprint headers (Firefox, no Client Hints)')

        return common_headers

    random_ua = get_random_user_agent()
    print(f'ℹ️ {account_name}: Using random User-Agent (generated once)')
    return {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en,en-US;q=0.9,zh;q=0.8,en-CN;q=0.7,zh-CN;q=0.6',
        'Cache-Control': 'no-store',
        'Pragma': 'no-cache',
        'User-Agent': random_ua,
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
    }
