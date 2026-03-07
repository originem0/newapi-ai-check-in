#!/usr/bin/env python3
"""
CheckIn 浏览器辅助函数
"""

from __future__ import annotations

import json
import tempfile
from typing import TYPE_CHECKING

from camoufox.async_api import AsyncCamoufox

from utils.browser_utils import aliyun_captcha_check, take_screenshot
from utils.safe_logging import mask_secret

if TYPE_CHECKING:
    from utils.config import ProviderConfig


async def get_waf_cookies_with_browser(
    account_name: str,
    safe_account_name: str,
    camoufox_proxy_config: dict | None,
    provider_config: 'ProviderConfig',
) -> dict | None:
    print(
        f"ℹ️ {account_name}: Starting browser to get WAF cookies "
        f"(using proxy: {'true' if camoufox_proxy_config else 'false'})"
    )

    with tempfile.TemporaryDirectory(prefix=f'camoufox_{safe_account_name}_waf_') as tmp_dir:
        print(f'ℹ️ {account_name}: Using temporary directory: {tmp_dir}')
        async with AsyncCamoufox(
            persistent_context=True,
            user_data_dir=tmp_dir,
            headless=False,
            humanize=True,
            locale='en-US',
            geoip=True if camoufox_proxy_config else False,
            proxy=camoufox_proxy_config,
            os='macos',
        ) as browser:
            page = await browser.new_page()

            try:
                print(f'ℹ️ {account_name}: Access login page to get initial cookies')
                await page.goto(provider_config.get_login_url(), wait_until='networkidle')

                try:
                    await page.wait_for_function('document.readyState === "complete"', timeout=5000)
                except Exception:
                    await page.wait_for_timeout(3000)

                if provider_config.aliyun_captcha:
                    captcha_check = await aliyun_captcha_check(page, account_name)
                    if captcha_check:
                        await page.wait_for_timeout(3000)

                cookies = await browser.cookies()
                waf_cookies = {}
                print(f'ℹ️ {account_name}: WAF cookies')
                for cookie in cookies:
                    cookie_name = cookie.get('name')
                    cookie_value = cookie.get('value')
                    print(f'  📚 Cookie: {cookie_name} (value: {mask_secret(cookie_value)})')
                    if cookie_name in ['acw_tc', 'cdn_sec_tc', 'acw_sc__v2'] and cookie_value is not None:
                        waf_cookies[cookie_name] = cookie_value

                print(f'ℹ️ {account_name}: Got {len(waf_cookies)} WAF cookies after step 1')
                if not waf_cookies:
                    print(f'❌ {account_name}: No WAF cookies obtained')
                    return None

                print(f"✅ {account_name}: Successfully got WAF cookies: {list(waf_cookies.keys())}")
                return waf_cookies
            except Exception as e:
                print(f'❌ {account_name}: Error occurred while getting WAF cookies: {e}')
                return None
            finally:
                await page.close()


async def get_aliyun_captcha_cookies_with_browser(
    account_name: str,
    safe_account_name: str,
    camoufox_proxy_config: dict | None,
    provider_config: 'ProviderConfig',
) -> dict | None:
    print(
        f"ℹ️ {account_name}: Starting browser to get Aliyun captcha cookies "
        f"(using proxy: {'true' if camoufox_proxy_config else 'false'})"
    )

    with tempfile.TemporaryDirectory(prefix=f'camoufox_{safe_account_name}_aliyun_captcha_') as tmp_dir:
        print(f'ℹ️ {account_name}: Using temporary directory: {tmp_dir}')
        async with AsyncCamoufox(
            persistent_context=True,
            user_data_dir=tmp_dir,
            headless=False,
            humanize=True,
            locale='en-US',
            geoip=True if camoufox_proxy_config else False,
            proxy=camoufox_proxy_config,
            os='macos',
        ) as browser:
            page = await browser.new_page()

            try:
                print(f'ℹ️ {account_name}: Access login page to get initial cookies')
                await page.goto(provider_config.get_login_url(), wait_until='networkidle')

                try:
                    await page.wait_for_function('document.readyState === "complete"', timeout=5000)
                except Exception:
                    await page.wait_for_timeout(3000)

                    try:
                        await page.wait_for_function('document.readyState === "complete"', timeout=5000)
                    except Exception:
                        await page.wait_for_timeout(3000)

                    traceid_after = None
                    try:
                        traceid_after = await page.evaluate(
                            """() => {
                            const traceElement = document.getElementById('traceid');
                            if (traceElement) {
                                const text = traceElement.innerText || traceElement.textContent;
                                const match = text.match(/TraceID:\\s*([a-f0-9]+)/i);
                                return match ? match[1] : null;
                            }
                            return null;
                        }"""
                        )
                    except Exception:
                        traceid_after = None

                    if traceid_after:
                        print(
                            f'❌ {account_name}: Captcha verification failed, '
                            f'traceid still present: {traceid_after}'
                        )
                        return None

                    print(f'✅ {account_name}: Captcha verification successful, traceid cleared')

                cookies = await browser.cookies()
                aliyun_captcha_cookies = {}
                print(f'ℹ️ {account_name}: Aliyun Captcha cookies')
                for cookie in cookies:
                    cookie_name = cookie.get('name')
                    cookie_value = cookie.get('value')
                    print(f'  📚 Cookie: {cookie_name} (value: {mask_secret(cookie_value)})')
                    aliyun_captcha_cookies[cookie_name] = cookie_value

                print(
                    f'ℹ️ {account_name}: Got {len(aliyun_captcha_cookies)} '
                    'Aliyun Captcha cookies after step 1'
                )
                if not aliyun_captcha_cookies:
                    print(f'❌ {account_name}: No Aliyun Captcha cookies obtained')
                    return None

                print(
                    f"✅ {account_name}: Successfully got Aliyun Captcha cookies: "
                    f"{list(aliyun_captcha_cookies.keys())}"
                )
                return aliyun_captcha_cookies
            except Exception as e:
                print(f'❌ {account_name}: Error occurred while getting Aliyun Captcha cookies, {e}')
                return None
            finally:
                await page.close()


async def get_status_with_browser(
    account_name: str,
    safe_account_name: str,
    camoufox_proxy_config: dict | None,
    provider_config: 'ProviderConfig',
) -> dict | None:
    print(
        f"ℹ️ {account_name}: Starting browser to get status "
        f"(using proxy: {'true' if camoufox_proxy_config else 'false'})"
    )

    with tempfile.TemporaryDirectory(prefix=f'camoufox_{safe_account_name}_status_') as tmp_dir:
        print(f'ℹ️ {account_name}: Using temporary directory: {tmp_dir}')
        async with AsyncCamoufox(
            user_data_dir=tmp_dir,
            persistent_context=True,
            headless=False,
            humanize=True,
            locale='en-US',
            geoip=True if camoufox_proxy_config else False,
            proxy=camoufox_proxy_config,
            os='macos',
        ) as browser:
            page = await browser.new_page()

            try:
                print(f'ℹ️ {account_name}: Access status page to get status from localStorage')
                await page.goto(provider_config.get_login_url(), wait_until='networkidle')

                try:
                    await page.wait_for_function('document.readyState === "complete"', timeout=5000)
                except Exception:
                    await page.wait_for_timeout(3000)

                if provider_config.aliyun_captcha:
                    captcha_check = await aliyun_captcha_check(page, account_name)
                    if captcha_check:
                        await page.wait_for_timeout(3000)

                try:
                    status_str = await page.evaluate("() => localStorage.getItem('status')")
                    if status_str:
                        print(f'✅ {account_name}: Got status from localStorage')
                        return json.loads(status_str)

                    print(f'⚠️ {account_name}: No status found in localStorage')
                    return None
                except Exception as e:
                    print(f'⚠️ {account_name}: Error reading status from localStorage: {e}')
                    return None
            except Exception as e:
                print(f'❌ {account_name}: Error occurred while getting status: {e}')
                return None
            finally:
                await page.close()


async def get_auth_state_with_browser(
    account_name: str,
    safe_account_name: str,
    camoufox_proxy_config: dict | None,
    provider_config: 'ProviderConfig',
) -> dict:
    print(
        f"ℹ️ {account_name}: Starting browser to get auth state "
        f"(using proxy: {'true' if camoufox_proxy_config else 'false'})"
    )

    with tempfile.TemporaryDirectory(prefix=f'camoufox_{safe_account_name}_auth_') as tmp_dir:
        print(f'ℹ️ {account_name}: Using temporary directory: {tmp_dir}')
        async with AsyncCamoufox(
            user_data_dir=tmp_dir,
            persistent_context=True,
            headless=False,
            humanize=True,
            locale='en-US',
            geoip=True if camoufox_proxy_config else False,
            proxy=camoufox_proxy_config,
            os='macos',
        ) as browser:
            page = await browser.new_page()

            try:
                print(f'ℹ️ {account_name}: Opening login page')
                await page.goto(provider_config.get_login_url(), wait_until='networkidle')

                try:
                    await page.wait_for_function('document.readyState === "complete"', timeout=5000)
                except Exception:
                    await page.wait_for_timeout(3000)

                if provider_config.aliyun_captcha:
                    captcha_check = await aliyun_captcha_check(page, account_name)
                    if captcha_check:
                        await page.wait_for_timeout(3000)

                response = await page.evaluate(
                    f"""async () => {{
                        try{{
                            const response = await fetch('{provider_config.get_auth_state_url()}');
                            const data = await response.json();
                            return data;
                        }}catch(e){{
                            return {{
                                success: false,
                                message: e.message
                            }};
                        }}
                    }}"""
                )

                if response and 'data' in response:
                    cookies = await browser.cookies()
                    return {
                        'success': True,
                        'state': response.get('data'),
                        'cookies': cookies,
                    }

                return {'success': False, 'error': f'Failed to get state, \n{json.dumps(response, indent=2)}'}
            except Exception as e:
                print(f'❌ {account_name}: Failed to get state, {e}')
                await take_screenshot(page, 'auth_url_error', account_name)
                return {'success': False, 'error': 'Failed to get state'}
            finally:
                await page.close()


async def get_user_info_with_browser(
    account_name: str,
    safe_account_name: str,
    camoufox_proxy_config: dict | None,
    provider_config: 'ProviderConfig',
    quota_divisor: int | float,
    auth_cookies: list[dict],
) -> dict:
    print(
        f"ℹ️ {account_name}: Starting browser to get user info "
        f"(using proxy: {'true' if camoufox_proxy_config else 'false'})"
    )

    with tempfile.TemporaryDirectory(prefix=f'camoufox_{safe_account_name}_user_info_') as tmp_dir:
        print(f'ℹ️ {account_name}: Using temporary directory: {tmp_dir}')
        async with AsyncCamoufox(
            user_data_dir=tmp_dir,
            persistent_context=True,
            headless=False,
            humanize=True,
            locale='en-US',
            geoip=True if camoufox_proxy_config else False,
            proxy=camoufox_proxy_config,
            os='macos',
        ) as browser:
            page = await browser.new_page()
            browser.add_cookies(auth_cookies)

            try:
                print(f'ℹ️ {account_name}: Opening main page')
                await page.goto(provider_config.origin, wait_until='networkidle')

                try:
                    await page.wait_for_function('document.readyState === "complete"', timeout=5000)
                except Exception:
                    await page.wait_for_timeout(3000)

                if provider_config.aliyun_captcha:
                    captcha_check = await aliyun_captcha_check(page, account_name)
                    if captcha_check:
                        await page.wait_for_timeout(3000)

                response = await page.evaluate(
                    f"""async () => {{
                       const response = await fetch(
                           '{provider_config.get_user_info_url()}'
                       );
                       const data = await response.json();
                       return data;
                    }}"""
                )

                if response and 'data' in response:
                    user_data = response.get('data', {})
                    quota = round(user_data.get('quota', 0) / quota_divisor, 2)
                    used_quota = round(user_data.get('used_quota', 0) / quota_divisor, 2)
                    bonus_quota = round(user_data.get('bonus_quota', 0) / quota_divisor, 2)
                    print(f'✅ {account_name}: Current balance: ${quota}, Used: ${used_quota}, Bonus: ${bonus_quota}')
                    return {
                        'success': True,
                        'quota': quota,
                        'used_quota': used_quota,
                        'bonus_quota': bonus_quota,
                        'display': f'Current balance: ${quota}, Used: ${used_quota}, Bonus: ${bonus_quota}',
                    }

                return {'success': False, 'error': f'Failed to get user info, \n{json.dumps(response, indent=2)}'}
            except Exception as e:
                print(f'❌ {account_name}: Failed to get user info, {e}')
                await take_screenshot(page, 'user_info_error', account_name)
                return {'success': False, 'error': 'Failed to get user info'}
            finally:
                await page.close()
