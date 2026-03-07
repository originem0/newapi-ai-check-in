#!/usr/bin/env python3
"""
CheckIn 类
"""

import hashlib
import os
from urllib.parse import urlencode

from curl_cffi import requests as curl_requests

from utils.browser_utils import parse_cookies
from utils.checkin_browser import (
    get_aliyun_captcha_cookies_with_browser as browser_get_aliyun_captcha_cookies_with_browser,
)
from utils.checkin_browser import (
    get_auth_state_with_browser as browser_get_auth_state_with_browser,
)
from utils.checkin_browser import (
    get_status_with_browser as browser_get_status_with_browser,
)
from utils.checkin_browser import (
    get_user_info_with_browser as browser_get_user_info_with_browser,
)
from utils.checkin_browser import (
    get_waf_cookies_with_browser as browser_get_waf_cookies_with_browser,
)
from utils.checkin_http import (
    execute_check_in as http_execute_check_in,
)
from utils.checkin_http import (
    execute_topup as http_execute_topup,
)
from utils.checkin_http import (
    get_auth_client_id as http_get_auth_client_id,
)
from utils.checkin_http import (
    get_auth_state as http_get_auth_state,
)
from utils.checkin_http import (
    get_user_info as http_get_user_info,
)
from utils.checkin_runtime import build_common_headers
from utils.config import QUOTA_DIVISOR, AccountConfig, ProviderConfig
from utils.get_cf_clearance import get_cf_clearance
from utils.get_headers import get_curl_cffi_impersonate
from utils.http_utils import proxy_resolve, response_resolve
from utils.run_models import AccountRunResult, AuthAttemptResult, UserState
from utils.safe_logging import mask_secret, sanitize_url


class CheckIn:
    """newapi.ai 签到管理类"""

    def __init__(
        self,
        account_name: str,
        account_config: AccountConfig,
        provider_config: ProviderConfig,
        global_proxy: dict | None = None,
        storage_state_dir: str = "storage-states",
    ):
        """初始化签到管理器

        Args:
                account_info: account 用户配置
                proxy_config: 全局代理配置(可选)
        """
        self.account_name = account_name
        self.safe_account_name = "".join(c if c.isalnum() else "_" for c in account_name)
        self.account_config = account_config
        self.provider_config = provider_config

        # 将全局代理存入 account_config.extra，供 get_cdk 和 check_in_status 等函数使用
        if global_proxy:
            self.account_config.extra["global_proxy"] = global_proxy

        # 代理优先级: 账号配置 > 全局配置
        self.camoufox_proxy_config = account_config.proxy if account_config.proxy else global_proxy
        # curl_cffi proxy 转换
        self.http_proxy_config = proxy_resolve(self.camoufox_proxy_config)

        # storage-states 目录
        self.storage_state_dir = storage_state_dir

        os.makedirs(self.storage_state_dir, exist_ok=True)

    async def get_waf_cookies_with_browser(self) -> dict | None:
        """使用 Camoufox 获取 WAF cookies（隐私模式）"""
        return await browser_get_waf_cookies_with_browser(
            account_name=self.account_name,
            safe_account_name=self.safe_account_name,
            camoufox_proxy_config=self.camoufox_proxy_config,
            provider_config=self.provider_config,
        )

    async def get_aliyun_captcha_cookies_with_browser(self) -> dict | None:
        """使用 Camoufox 获取阿里云验证 cookies"""
        return await browser_get_aliyun_captcha_cookies_with_browser(
            account_name=self.account_name,
            safe_account_name=self.safe_account_name,
            camoufox_proxy_config=self.camoufox_proxy_config,
            provider_config=self.provider_config,
        )

    async def get_status_with_browser(self) -> dict | None:
        """使用 Camoufox 获取状态信息并缓存
        Returns:
            状态数据字典
        """
        return await browser_get_status_with_browser(
            account_name=self.account_name,
            safe_account_name=self.safe_account_name,
            camoufox_proxy_config=self.camoufox_proxy_config,
            provider_config=self.provider_config,
        )

    async def get_auth_client_id(self, session: curl_requests.Session, headers: dict, provider: str) -> dict:
        """获取状态信息

        Args:
            session: curl_cffi Session 客户端
            headers: 请求头
            provider: 提供商类型 (github/linuxdo)

        Returns:
            包含 success 和 client_id 或 error 的字典
        """
        return await http_get_auth_client_id(
            account_name=self.account_name,
            provider_config=self.provider_config,
            session=session,
            headers=headers,
            provider=provider,
        )

    async def get_auth_state_with_browser(self) -> dict:
        """使用 Camoufox 获取认证 URL 和 cookies

        Args:
            status: 要存储到 localStorage 的状态数据
            wait_for_url: 要等待的 URL 模式

        Returns:
            包含 success、url、cookies 或 error 的字典
        """
        return await browser_get_auth_state_with_browser(
            account_name=self.account_name,
            safe_account_name=self.safe_account_name,
            camoufox_proxy_config=self.camoufox_proxy_config,
            provider_config=self.provider_config,
        )

    async def get_auth_state(
        self,
        session: curl_requests.Session,
        headers: dict,
    ) -> dict:
        """获取认证状态
        
        使用 curl_cffi Session 发送请求。Session 可在创建时设置全局 impersonate。
        
        Args:
            session: curl_cffi Session 客户端（已包含 cookies，可能已设置 impersonate）
            headers: 请求头
        """
        return await http_get_auth_state(
            account_name=self.account_name,
            provider_config=self.provider_config,
            session=session,
            headers=headers,
        )

    async def get_user_info_with_browser(self, auth_cookies: list[dict]) -> dict:
        """使用 Camoufox 获取用户信息

        Returns:
            包含 success、quota、used_quota 或 error 的字典
        """
        return await browser_get_user_info_with_browser(
            account_name=self.account_name,
            safe_account_name=self.safe_account_name,
            camoufox_proxy_config=self.camoufox_proxy_config,
            provider_config=self.provider_config,
            quota_divisor=QUOTA_DIVISOR,
            auth_cookies=auth_cookies,
        )

    async def get_user_info(self, session: curl_requests.Session, headers: dict) -> dict:
        """获取用户信息"""
        return await http_get_user_info(
            account_name=self.account_name,
            provider_config=self.provider_config,
            quota_divisor=QUOTA_DIVISOR,
            session=session,
            headers=headers,
        )

    def execute_check_in(
        self,
        session: curl_requests.Session,
        headers: dict,
        api_user: str | int,
    ) -> dict:
        """执行签到请求
        
        Returns:
            包含 success, message, data 等信息的字典
        """
        return http_execute_check_in(
            account_name=self.account_name,
            provider_config=self.provider_config,
            quota_divisor=QUOTA_DIVISOR,
            session=session,
            headers=headers,
            api_user=api_user,
        )

    async def execute_topup(
        self,
        headers: dict,
        cookies: dict,
        api_user: str | int,
        topup_interval: int = 60,
    ) -> dict:
        """执行完整的 CDK 获取和充值流程

        直接调用 get_cdk 生成器函数，每次 yield 一个 CDK 字符串并执行 topup
        每次 topup 之间保持间隔时间，如果 topup 失败则停止
        
        支持同步生成器和异步生成器两种类型的 get_cdk 函数

        Args:
            headers: 请求头
            cookies: cookies 字典
            api_user: API 用户 ID（通过参数传递，因为登录方式可能不同）
            topup_interval: 多次 topup 之间的间隔时间（秒），默认 60 秒

        Returns:
            包含 success, topup_count, errors 等信息的字典
        """
        return await http_execute_topup(
            account_name=self.account_name,
            provider_config=self.provider_config,
            account_config=self.account_config,
            headers=headers,
            cookies=cookies,
            api_user=api_user,
            topup_interval=topup_interval,
        )

    async def check_in_with_cookies(
        self,
        cookies: dict,
        common_headers: dict,
        api_user: str | int,
        impersonate: str = "firefox135",
    ) -> tuple[bool, dict]:
        """使用已有 cookies 执行签到操作
        
        Args:
            cookies: cookies 字典
            common_headers: 公用请求头（包含 User-Agent 和可能的 Client Hints）
            api_user: API 用户 ID
        """
        print(
            f"ℹ️ {self.account_name}: Executing check-in with existing cookies (using proxy: {'true' if self.http_proxy_config else 'false'})"
        )

        session = curl_requests.Session(impersonate=impersonate, proxy=self.http_proxy_config, timeout=30)
        
        try:
            # 打印 cookies 的键和值
            print(f"ℹ️ {self.account_name}: Cookies to be used:")
            for key, value in cookies.items():
                print(f"  📚 {key}: {mask_secret(value)}")
            session.cookies.update(cookies)

            # 使用传入的公用请求头，并添加动态头部
            headers = common_headers.copy()
            headers[self.provider_config.api_user_key] = f"{api_user}"
            headers["Referer"] = self.provider_config.get_login_url()
            headers["Origin"] = self.provider_config.origin

            # 检查是否需要手动签到
            if self.provider_config.needs_manual_check_in():
                # 如果配置了签到状态查询，先检查是否已签到
                check_in_status_func = self.provider_config.get_check_in_status_func()
                if check_in_status_func:
                    checked_in_today = check_in_status_func(
                        provider_config=self.provider_config,
                        account_config=self.account_config,
                        cookies=cookies,
                        headers=headers,
                    )
                    if checked_in_today:
                        print(f"ℹ️ {self.account_name}: Already checked in today, skipping check-in")
                    else:
                        # 未签到，执行签到
                        check_in_result = self.execute_check_in(session, headers, api_user)
                        if not check_in_result.get("success"):
                            return False, {"error": check_in_result.get("error", "Check-in failed")}
                        # 签到成功后再次查询状态（显示最新状态）
                        check_in_status_func(
                            provider_config=self.provider_config,
                            account_config=self.account_config,
                            cookies=cookies,
                            headers=headers,
                        )
                else:
                    # 没有配置签到状态查询函数，直接执行签到
                    check_in_result = self.execute_check_in(session, headers, api_user)
                    if not check_in_result.get("success"):
                        return False, {"error": check_in_result.get("error", "Check-in failed")}
            else:
                if self.provider_config.name == "x666":
                    print(f"ℹ️ {self.account_name}: X666 has no separate check-in endpoint, continuing with draw flow")
                else:
                    print(f"ℹ️ {self.account_name}: Check-in completed automatically (triggered by user info request)")

            # 如果需要手动 topup（配置了 topup_path 和 get_cdk），执行 topup
            if self.provider_config.needs_manual_topup():
                print(f"ℹ️ {self.account_name}: Provider requires manual topup, executing...")
                topup_result = await self.execute_topup(headers, cookies, api_user)
                if topup_result.get("topup_count", 0) > 0:
                    print(
                        f"ℹ️ {self.account_name}: Topup completed - "
                        f"{topup_result.get('topup_success_count', 0)}/{topup_result.get('topup_count', 0)} successful"
                    )
                if not topup_result.get("success"):
                    error_msg = topup_result.get("error") or "Topup failed"
                    print(f"❌ {self.account_name}: Topup failed, stopping check-in process")
                    return False, {"error": error_msg}

            user_info = await self.get_user_info(session, headers)
            if user_info and user_info.get("success"):
                success_msg = user_info.get("display", "User info retrieved successfully")
                print(f"✅ {self.account_name}: {success_msg}")
                return True, user_info
            elif user_info:
                error_msg = user_info.get("error", "Unknown error")
                print(f"❌ {self.account_name}: {error_msg}")
                return False, {"error": "Failed to get user info"}
            else:
                return False, {"error": "No user info available"}

        except Exception as e:
            print(f"❌ {self.account_name}: Error occurred during check-in process - {e}")
            return False, {"error": "Error occurred during check-in process"}
        finally:
            session.close()

    async def check_in_with_github(
        self,
        username: str,
        password: str,
        bypass_cookies: dict,
        common_headers: dict,
    ) -> tuple[bool, dict]:
        """使用 GitHub 账号执行签到操作
        
        Args:
            username: GitHub 用户名
            password: GitHub 密码
            bypass_cookies: bypass cookies
            common_headers: 公用请求头（包含 User-Agent 和可能的 Client Hints）
        """
        from sign_in_with_github import GitHubSignIn

        return await self._check_in_with_oauth(
            username=username,
            password=password,
            bypass_cookies=bypass_cookies,
            common_headers=common_headers,
            provider_label='GitHub',
            client_id_attr='github_client_id',
            sign_in_cls=GitHubSignIn,
            callback_context='github_oauth_callback',
            callback_base_url=self.provider_config.get_github_auth_url(),
        )

    @staticmethod
    def _set_auth_state_cookies(session: curl_requests.Session, auth_cookies_list: list[dict]) -> None:
        """将浏览器态 cookies 注入到 curl_cffi session。"""
        for cookie_dict in auth_cookies_list:
            session.cookies.set(cookie_dict['name'], cookie_dict['value'])

    @staticmethod
    def _merge_oauth_headers(common_headers: dict, oauth_browser_headers: dict | None) -> dict:
        """合并 OAuth 返回的浏览器指纹头部。"""
        updated_headers = common_headers.copy()
        if oauth_browser_headers:
            updated_headers.update(oauth_browser_headers)
        return updated_headers

    async def _handle_oauth_callback_via_http(
        self,
        session: curl_requests.Session,
        callback_url: str,
        callback_context: str,
        auth_state_cookies: list[dict],
        common_headers: dict,
        oauth_browser_headers: dict | None,
        bypass_cookies: dict,
        impersonate: str,
    ) -> tuple[bool, dict]:
        """通过 provider OAuth 回调接口换取 cookies + api_user。"""
        print(f"ℹ️ {self.account_name}: Callback URL: {sanitize_url(callback_url)}")

        self._set_auth_state_cookies(session, auth_state_cookies)
        updated_headers = self._merge_oauth_headers(common_headers, oauth_browser_headers)
        if oauth_browser_headers:
            print(f"ℹ️ {self.account_name}: Updating headers with OAuth browser fingerprint")

        response = session.get(callback_url, headers=updated_headers, timeout=30)
        if response.status_code != 200:
            print(f"❌ {self.account_name}: OAuth callback HTTP {response.status_code}")
            return False, {"error": f"OAuth callback HTTP {response.status_code}"}

        json_data = response_resolve(response, callback_context, self.account_name)
        if not json_data or not json_data.get('success'):
            error_msg = json_data.get('message', 'Unknown error') if json_data else 'Invalid response'
            print(f"❌ {self.account_name}: OAuth callback failed: {error_msg}")
            return False, {"error": f"OAuth callback failed: {error_msg}"}

        user_data = json_data.get('data', {})
        api_user = user_data.get('id')
        if not api_user:
            print(f"❌ {self.account_name}: No user ID in callback response")
            return False, {"error": "No user ID in OAuth callback response"}

        print(f"✅ {self.account_name}: Got api_user from callback: {api_user}")
        user_cookies = {cookie.name: cookie.value for cookie in response.cookies.jar}
        print(f"ℹ️ {self.account_name}: Extracted {len(user_cookies)} user cookies")
        merged_cookies = {**bypass_cookies, **user_cookies}
        return await self.check_in_with_cookies(merged_cookies, updated_headers, api_user, impersonate)

    async def _resolve_bypass_artifacts(self) -> tuple[dict, dict | None]:
        """处理 WAF / Cloudflare 前置 cookies 与浏览器指纹。"""
        bypass_cookies: dict = {}
        browser_headers = None

        if self.provider_config.needs_waf_cookies():
            waf_cookies = await self.get_waf_cookies_with_browser()
            if waf_cookies:
                bypass_cookies = waf_cookies
                print(f'✅ {self.account_name}: WAF cookies obtained')
            else:
                print(f'⚠️ {self.account_name}: Unable to get WAF cookies, continuing with empty cookies')
            return bypass_cookies, browser_headers

        if self.provider_config.needs_cf_clearance():
            try:
                cf_result = await get_cf_clearance(
                    url=self.provider_config.get_login_url(),
                    account_name=self.account_name,
                    proxy_config=self.camoufox_proxy_config,
                )

                if cf_result[0]:
                    bypass_cookies = cf_result[0]
                    print(f'✅ {self.account_name}: Cloudflare cookies obtained')
                else:
                    print(f'⚠️ {self.account_name}: Unable to get Cloudflare cookies, continuing with empty cookies')

                if cf_result[1]:
                    browser_headers = cf_result[1]
                    print(f'✅ {self.account_name}: Cloudflare fingerprint headers obtained')
            except Exception as e:
                print(f'❌ {self.account_name}: Error occurred while getting cf_clearance cookie: {e}')
                print(f'⚠️ {self.account_name}: Continuing with empty cookies')
            return bypass_cookies, browser_headers

        print(f'ℹ️ {self.account_name}: Bypass not required, using user cookies directly')
        return bypass_cookies, browser_headers

    async def _run_cookies_attempt(
        self, cookies_data, bypass_cookies: dict, common_headers: dict, attempts: list[AuthAttemptResult]
    ) -> None:
        """执行 cookies 认证尝试。"""
        if not cookies_data:
            return

        print(f'\nℹ️ {self.account_name}: Trying cookies authentication')
        try:
            user_cookies = parse_cookies(cookies_data)
            if not user_cookies:
                print(f'❌ {self.account_name}: Invalid cookies format')
                attempts.append(self._build_attempt_result('cookies', False, {'error': 'Invalid cookies format'}))
                return

            api_user = self.account_config.api_user
            if not api_user:
                print(f'❌ {self.account_name}: API user identifier not found for cookies')
                attempts.append(
                    self._build_attempt_result('cookies', False, {'error': 'API user identifier not found'})
                )
                return

            all_cookies = {**bypass_cookies, **user_cookies}
            success, user_info = await self.check_in_with_cookies(all_cookies, common_headers, api_user)
            if success:
                print(f'✅ {self.account_name}: Cookies authentication successful')
                attempts.append(self._build_attempt_result('cookies', True, user_info))
            else:
                print(f'❌ {self.account_name}: Cookies authentication failed')
                attempts.append(self._build_attempt_result('cookies', False, user_info))
        except Exception as e:
            print(f'❌ {self.account_name}: Cookies authentication error: {e}')
            attempts.append(self._build_attempt_result('cookies', False, {'error': str(e)}))

    async def _run_oauth_attempts(
        self,
        auth_name: str,
        accounts,
        bypass_cookies: dict,
        common_headers: dict,
        attempts: list[AuthAttemptResult],
        runner,
    ) -> None:
        """执行多个 OAuth 账号尝试。"""
        if not accounts:
            return

        for idx, oauth_account in enumerate(accounts):
            account_label = f'{auth_name}[{idx}]' if len(accounts) > 1 else auth_name
            print(f'\nℹ️ {self.account_name}: Trying {auth_name} authentication ({oauth_account.username})')
            try:
                username = oauth_account.username
                password = oauth_account.password
                if not username or not password:
                    print(f'❌ {self.account_name}: Incomplete {auth_name} account information')
                    attempts.append(
                        self._build_attempt_result(
                            account_label, False, {'error': f'Incomplete {auth_name} account information'}
                        )
                    )
                    continue

                success, user_info = await runner(username, password, bypass_cookies, common_headers)
                if success:
                    print(f'✅ {self.account_name}: {auth_name} authentication successful ({oauth_account.username})')
                    attempts.append(self._build_attempt_result(account_label, True, user_info))
                else:
                    print(f'❌ {self.account_name}: {auth_name} authentication failed ({oauth_account.username})')
                    attempts.append(self._build_attempt_result(account_label, False, user_info))
            except Exception as e:
                print(f'❌ {self.account_name}: {auth_name} authentication error ({oauth_account.username}): {e}')
                attempts.append(self._build_attempt_result(account_label, False, {'error': str(e)}))

    async def check_in_with_linuxdo(
        self,
        username: str,
        password: str,
        bypass_cookies: dict,
        common_headers: dict,
    ) -> tuple[bool, dict]:
        """使用 Linux.do 账号执行签到操作

        Args:
            username: Linux.do 用户名
            password: Linux.do 密码
            bypass_cookies: bypass cookies
            common_headers: 公用请求头（包含 User-Agent 和可能的 Client Hints）
        """
        from sign_in_with_linuxdo import LinuxDoSignIn

        return await self._check_in_with_oauth(
            username=username,
            password=password,
            bypass_cookies=bypass_cookies,
            common_headers=common_headers,
            provider_label='Linux.do',
            client_id_attr='linuxdo_client_id',
            sign_in_cls=LinuxDoSignIn,
            callback_context='linuxdo_oauth_callback',
            callback_base_url=self.provider_config.get_linuxdo_auth_url(),
        )

    @staticmethod
    def _build_attempt_result(auth_method: str, success: bool, payload: dict | None) -> AuthAttemptResult:
        payload = payload or {}
        user_state = None
        error = None

        if success and payload.get('success'):
            try:
                user_state = UserState.from_payload(payload)
            except Exception:
                error = 'Invalid user state payload'
                success = False
        elif not success:
            error = payload.get('error', 'Unknown error')

        return AuthAttemptResult(
            auth_method=auth_method,
            success=success and user_state is not None,
            error=error,
            user_state=user_state,
            meta={'raw': payload},
        )

    def _create_oauth_session_and_headers(
        self, common_headers: dict, bypass_cookies: dict
    ) -> tuple[curl_requests.Session, str, dict]:
        """构建 OAuth 使用的 session、impersonate 和基础 headers。"""
        user_agent = common_headers.get('User-Agent', '')
        impersonate = get_curl_cffi_impersonate(user_agent)

        session = curl_requests.Session(impersonate=impersonate, proxy=self.http_proxy_config, timeout=30)
        session.cookies.update(bypass_cookies)

        headers = common_headers.copy()
        headers[self.provider_config.api_user_key] = '-1'
        headers['Referer'] = self.provider_config.get_login_url()
        headers['Origin'] = self.provider_config.origin

        if impersonate:
            print(f'ℹ️ {self.account_name}: Using curl_cffi Session with impersonate={impersonate}')

        return session, impersonate, headers

    async def _finalize_oauth_result(
        self,
        success: bool,
        result_data: dict,
        oauth_browser_headers: dict | None,
        bypass_cookies: dict,
        common_headers: dict,
        session: curl_requests.Session,
        auth_state_result: dict,
        callback_context: str,
        callback_base_url: str,
        impersonate: str,
    ) -> tuple[bool, dict]:
        """统一处理 OAuth 浏览器登录后的 cookies/api_user 或 callback code 分支。"""
        if success and 'cookies' in result_data and 'api_user' in result_data:
            user_cookies = result_data['cookies']
            api_user = result_data['api_user']
            updated_headers = common_headers.copy()
            if oauth_browser_headers:
                print(f'ℹ️ {self.account_name}: Updating headers with OAuth browser fingerprint')
                updated_headers.update(oauth_browser_headers)

            merged_cookies = {**bypass_cookies, **user_cookies}
            return await self.check_in_with_cookies(merged_cookies, updated_headers, api_user, impersonate)

        if success and 'code' in result_data and 'state' in result_data:
            print(f'ℹ️ {self.account_name}: Received OAuth code, calling callback API')
            callback_url = f'{callback_base_url}?{urlencode(result_data, doseq=True)}'
            try:
                return await self._handle_oauth_callback_via_http(
                    session=session,
                    callback_url=callback_url,
                    callback_context=callback_context,
                    auth_state_cookies=auth_state_result.get('cookies', []),
                    common_headers=common_headers,
                    oauth_browser_headers=oauth_browser_headers,
                    bypass_cookies=bypass_cookies,
                    impersonate=impersonate,
                )
            except Exception as callback_err:
                print(f'❌ {self.account_name}: Error calling OAuth callback: {callback_err}')
                return False, {'error': f'OAuth callback error: {callback_err}'}

        return False, result_data

    async def _check_in_with_oauth(
        self,
        username: str,
        password: str,
        bypass_cookies: dict,
        common_headers: dict,
        provider_label: str,
        client_id_attr: str,
        sign_in_cls,
        callback_context: str,
        callback_base_url: str,
    ) -> tuple[bool, dict]:
        """统一的 OAuth provider 执行流程。"""
        print(
            f"ℹ️ {self.account_name}: Executing check-in with {provider_label} account "
            f"(using proxy: {'true' if self.http_proxy_config else 'false'})"
        )

        session, impersonate, headers = self._create_oauth_session_and_headers(common_headers, bypass_cookies)

        try:
            configured_client_id = getattr(self.provider_config, client_id_attr)
            if configured_client_id:
                client_id_result = {'success': True, 'client_id': configured_client_id}
                print(f'ℹ️ {self.account_name}: Using {provider_label} client ID from config')
            else:
                provider_key = 'github' if provider_label == 'GitHub' else 'linuxdo'
                client_id_result = await self.get_auth_client_id(session, headers, provider_key)
                if client_id_result and client_id_result.get('success'):
                    print(f"ℹ️ {self.account_name}: Got client ID for {provider_label}: {client_id_result['client_id']}")
                else:
                    error_msg = client_id_result.get('error', 'Unknown error')
                    print(f'❌ {self.account_name}: {error_msg}')
                    return False, {'error': f'Failed to get {provider_label} client ID'}

            auth_state_result = await self.get_auth_state(session=session, headers=headers)
            if auth_state_result and auth_state_result.get('success'):
                print(f"ℹ️ {self.account_name}: Got auth state for {provider_label}: {auth_state_result['state']}")
            else:
                error_msg = auth_state_result.get('error', 'Unknown error')
                print(f'❌ {self.account_name}: {error_msg}')
                return False, {'error': f'Failed to get {provider_label} auth state'}

            username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()[:8]
            cache_prefix = 'github' if provider_label == 'GitHub' else 'linuxdo'
            cache_file_path = f'{self.storage_state_dir}/{cache_prefix}_{username_hash}_storage_state.json'

            oauth_signin = sign_in_cls(
                account_name=self.account_name,
                provider_config=self.provider_config,
                username=username,
                password=password,
            )

            success, result_data, oauth_browser_headers = await oauth_signin.signin(
                client_id=client_id_result['client_id'],
                auth_state=auth_state_result.get('state'),
                auth_cookies=auth_state_result.get('cookies', []),
                cache_file_path=cache_file_path,
            )

            return await self._finalize_oauth_result(
                success=success,
                result_data=result_data,
                oauth_browser_headers=oauth_browser_headers,
                bypass_cookies=bypass_cookies,
                common_headers=common_headers,
                session=session,
                auth_state_result=auth_state_result,
                callback_context=callback_context,
                callback_base_url=callback_base_url,
                impersonate=impersonate,
            )
        except Exception as e:
            print(f'❌ {self.account_name}: Error occurred during check-in process - {e}')
            return False, {'error': f'{provider_label} check-in process error'}
        finally:
            session.close()

    async def execute(self) -> AccountRunResult:
        """为单个账号执行奖励流程，支持多种认证方式"""
        print(f"\n\n⏳ Starting to process {self.account_name}")

        bypass_cookies, browser_headers = await self._resolve_bypass_artifacts()

        # 生成公用请求头（只生成一次 User-Agent，整个签到流程保持一致）
        # 注意：Referer 和 Origin 不在这里设置，由各个签到方法根据实际请求动态设置
        common_headers = build_common_headers(self.account_name, browser_headers)

        # 解析账号配置
        cookies_data = self.account_config.cookies
        github_accounts = self.account_config.github  # 现在是 List[OAuthAccountConfig] 类型
        linuxdo_accounts = self.account_config.linux_do  # 现在是 List[OAuthAccountConfig] 类型
        attempts: list[AuthAttemptResult] = []
        run_result = AccountRunResult(account_name=self.account_name, provider_name=self.provider_config.name)

        await self._run_cookies_attempt(cookies_data, bypass_cookies, common_headers, attempts)
        await self._run_oauth_attempts(
            'github', github_accounts, bypass_cookies, common_headers, attempts, self.check_in_with_github
        )
        await self._run_oauth_attempts(
            'linux.do', linuxdo_accounts, bypass_cookies, common_headers, attempts, self.check_in_with_linuxdo
        )

        if not attempts:
            print(f"❌ {self.account_name}: No valid authentication method found in configuration")
            run_result.system_error = 'No valid authentication method found in configuration'
            return run_result

        # 输出最终结果
        print(f"\n📋 {self.account_name} authentication results:")
        successful_count = 0
        for attempt in attempts:
            status = '✅' if attempt.success else '❌'
            print(f"  {status} {attempt.auth_method} authentication")
            if attempt.success:
                successful_count += 1

        print(f"\n🎯 {self.account_name}: {successful_count}/{len(attempts)} authentication methods successful")

        run_result.attempts = attempts
        return run_result

   
