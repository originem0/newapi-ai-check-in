#!/usr/bin/env python3
"""
CheckIn HTTP 辅助函数
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

from utils.http_utils import classify_transport_error, response_resolve
from utils.safe_logging import mask_secret
from utils.topup import topup

if TYPE_CHECKING:
    from utils.config import AccountConfig, ProviderConfig


async def get_auth_client_id(
    account_name: str,
    provider_config: 'ProviderConfig',
    session: curl_requests.Session,
    headers: dict,
    provider: str,
) -> dict:
    try:
        response = session.get(provider_config.get_status_url(), headers=headers, timeout=30)

        if response.status_code == 200:
            data = response_resolve(response, f'get_auth_client_id_{provider}', account_name)
            if data is None:
                return {
                    'success': False,
                    'error': 'Failed to get client id: Invalid response type (saved to logs)',
                }

            if data.get('success'):
                status_data = data.get('data', {})
                oauth = status_data.get(f'{provider}_oauth', False)
                if not oauth:
                    return {
                        'success': False,
                        'error': f'{provider} OAuth is not enabled.',
                    }

                client_id = status_data.get(f'{provider}_client_id', '')
                return {
                    'success': True,
                    'client_id': client_id,
                }

            error_msg = data.get('message', 'Unknown error')
            return {
                'success': False,
                'error': f'Failed to get client id: {error_msg}',
            }

        return {
            'success': False,
            'error': f'Failed to get client id: HTTP {response.status_code}',
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to get client id, {classify_transport_error(e)}',
        }


async def get_auth_state(
    account_name: str,
    provider_config: 'ProviderConfig',
    session: curl_requests.Session,
    headers: dict,
) -> dict:
    try:
        response = session.get(
            provider_config.get_auth_state_url(),
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            json_data = response_resolve(response, 'get_auth_state', account_name)
            if json_data is None:
                return {
                    'success': False,
                    'error': 'Failed to get auth state: Invalid response type (saved to logs)',
                }

            if json_data.get('success'):
                auth_data = json_data.get('data')
                result_cookies = []
                parsed_domain = urlparse(provider_config.origin).netloc

                print(f'ℹ️ {account_name}: Got {len(response.cookies)} cookies from auth state request')
                for cookie in response.cookies.jar:
                    http_only_raw = cookie._rest.get('HttpOnly', False)
                    http_only = bool(http_only_raw) if http_only_raw is not None else False
                    same_site_raw = cookie._rest.get('SameSite', 'Lax')
                    same_site = str(same_site_raw) if same_site_raw else 'Lax'
                    secure = bool(cookie.secure) if cookie.secure is not None else False

                    print(
                        f'  📚 Cookie: {cookie.name} (Domain: {cookie.domain}, '
                        f'Path: {cookie.path}, Secure: {secure}, SameSite: {same_site})'
                    )
                    cookie_dict = {
                        'name': cookie.name,
                        'domain': cookie.domain if cookie.domain else parsed_domain,
                        'value': cookie.value,
                        'path': cookie.path if cookie.path else '/',
                        'secure': secure,
                        'httpOnly': http_only,
                        'sameSite': same_site,
                    }
                    if cookie.expires is not None:
                        cookie_dict['expires'] = float(cookie.expires)
                    result_cookies.append(cookie_dict)

                return {
                    'success': True,
                    'state': auth_data,
                    'cookies': result_cookies,
                }

            error_msg = json_data.get('message', 'Unknown error')
            return {
                'success': False,
                'error': f'Failed to get auth state: {error_msg}',
            }

        return {
            'success': False,
            'error': f'Failed to get auth state: HTTP {response.status_code}',
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to get auth state, {classify_transport_error(e)}',
        }


async def get_user_info(
    account_name: str,
    provider_config: 'ProviderConfig',
    quota_divisor: int | float,
    session: curl_requests.Session,
    headers: dict,
) -> dict:
    try:
        response = session.get(provider_config.get_user_info_url(), headers=headers, timeout=30)

        if response.status_code == 200:
            json_data = response_resolve(response, 'get_user_info', account_name)
            if json_data is None:
                return {
                    'success': False,
                    'error': 'Failed to get user info: Invalid response type (saved to logs)',
                }

            if json_data.get('success'):
                user_data = json_data.get('data', {})
                quota = round(user_data.get('quota', 0) / quota_divisor, 2)
                used_quota = round(user_data.get('used_quota', 0) / quota_divisor, 2)
                bonus_quota = round(user_data.get('bonus_quota', 0) / quota_divisor, 2)
                return {
                    'success': True,
                    'quota': quota,
                    'used_quota': used_quota,
                    'bonus_quota': bonus_quota,
                    'display': f'Current balance: ${quota}, Used: ${used_quota}, Bonus: ${bonus_quota}',
                }

            error_msg = json_data.get('message', 'Unknown error')
            return {
                'success': False,
                'error': f'Failed to get user info: {error_msg}',
            }

        return {
            'success': False,
            'error': f'Failed to get user info: HTTP {response.status_code}',
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to get user info, {classify_transport_error(e)}',
        }


def execute_check_in(
    account_name: str,
    provider_config: 'ProviderConfig',
    quota_divisor: int | float,
    session: curl_requests.Session,
    headers: dict,
    api_user: str | int,
) -> dict:
    print(f'🌐 {account_name}: Executing check-in')

    checkin_headers = headers.copy()
    checkin_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})

    check_in_url = provider_config.get_check_in_url(api_user)
    if not check_in_url:
        print(f'❌ {account_name}: No check-in URL configured')
        return {'success': False, 'error': 'No check-in URL configured'}

    response = session.post(check_in_url, headers=checkin_headers, timeout=30)
    print(f'📨 {account_name}: Response status code {response.status_code}')

    if response.status_code in [200, 400]:
        json_data = response_resolve(response, 'execute_check_in', account_name)
        if json_data is None:
            if 'success' in response.text.lower():
                print(f'✅ {account_name}: Check-in successful!')
                return {'success': True, 'message': 'Check-in successful'}

            print(f'❌ {account_name}: Check-in failed - Invalid response format')
            return {'success': False, 'error': 'Invalid response format'}

        message = json_data.get('message', json_data.get('msg', ''))
        if (
            json_data.get('ret') == 1
            or json_data.get('code') == 0
            or json_data.get('success')
            or '已经签到' in message
            or '签到成功' in message
        ):
            check_in_data = json_data.get('data', {})
            checkin_date = check_in_data.get('checkin_date', '')
            quota_awarded = check_in_data.get('quota_awarded', 0)

            if quota_awarded:
                quota_display = round(quota_awarded / quota_divisor, 2)
                print(f'✅ {account_name}: Check-in successful! Date: {checkin_date}, Quota awarded: ${quota_display}')
            else:
                print(f'✅ {account_name}: Check-in successful! {message}')

            return {
                'success': True,
                'message': message or 'Check-in successful',
                'data': check_in_data,
            }

        error_msg = json_data.get('msg', json_data.get('message', 'Unknown error'))
        print(f'❌ {account_name}: Check-in failed - {error_msg}')
        return {'success': False, 'error': error_msg}

    print(f'❌ {account_name}: Check-in failed - HTTP {response.status_code}')
    return {'success': False, 'error': f'HTTP {response.status_code}'}


async def execute_topup(
    account_name: str,
    provider_config: 'ProviderConfig',
    account_config: 'AccountConfig',
    headers: dict,
    cookies: dict,
    api_user: str | int,
    topup_interval: int = 60,
) -> dict:
    if not provider_config.get_cdk:
        print(f'ℹ️ {account_name}: No get_cdk function configured for provider {provider_config.name}')
        return {
            'success': True,
            'topup_count': 0,
            'topup_success_count': 0,
            'error': '',
        }

    topup_headers = headers.copy()
    topup_headers.update(
        {
            'Referer': f'{provider_config.origin}/console/topup',
            'Origin': provider_config.origin,
            provider_config.api_user_key: f'{api_user}',
        }
    )

    results = {
        'success': True,
        'topup_count': 0,
        'topup_success_count': 0,
        'error': '',
    }

    cdk_generator = provider_config.get_cdk(account_config)
    topup_count = 0

    async def process_cdk_result(success: bool, data: dict) -> bool:
        nonlocal topup_count

        if not success:
            error_msg = data.get('error', 'Failed to get CDK')
            results['success'] = False
            results['error'] = error_msg
            print(f'❌ {account_name}: Failed to get CDK - {error_msg}, stopping topup process')
            return False

        cdk = data.get('code', '')
        if not cdk:
            print(f'ℹ️ {account_name}: No CDK to topup (code is empty), continuing...')
            return True

        if topup_count > 0 and topup_interval > 0:
            print(f'⏳ {account_name}: Waiting {topup_interval} seconds before next topup...')
            await asyncio.sleep(topup_interval)

        topup_count += 1
        print(f'💰 {account_name}: Executing topup #{topup_count} with CDK: {mask_secret(cdk)}')

        topup_result = topup(
            provider_config=provider_config,
            account_config=account_config,
            headers=topup_headers,
            cookies=cookies,
            key=cdk,
        )
        results['topup_count'] += 1

        if topup_result.get('success'):
            results['topup_success_count'] += 1
            if not topup_result.get('already_used'):
                print(f'✅ {account_name}: Topup #{topup_count} successful')
            return True

        error_msg = topup_result.get('error', 'Topup failed')
        results['success'] = False
        results['error'] = error_msg
        print(f'❌ {account_name}: Topup #{topup_count} failed, stopping topup process')
        return False

    if inspect.isasyncgen(cdk_generator):
        async for success, data in cdk_generator:
            should_continue = await process_cdk_result(success, data)
            if not should_continue:
                break
    else:
        for success, data in cdk_generator:
            should_continue = await process_cdk_result(success, data)
            if not should_continue:
                break

    if topup_count == 0:
        print(f'ℹ️ {account_name}: No CDK available for topup')
    elif results['topup_success_count'] > 0:
        print(
            f"✅ {account_name}: Total {results['topup_success_count']}/{results['topup_count']} topup(s) successful"
        )

    return results
