#!/usr/bin/env python3
"""
Linux.do 读帖自动化任务

目标：
- 尝试恢复或建立 Linux.do 登录态
- 访问一批 topic 页面并进行页面层阅读行为
- 输出“页面行为结果”和“严格业务验证结果”

说明：
- 当前没有稳定的服务端接口可证明“读帖任务完成”
- 因此页面行为成功时，默认记为 verification_status=uncertain
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

from camoufox.async_api import AsyncCamoufox
from dotenv import load_dotenv

from utils.browser_utils import save_page_content_to_file, take_screenshot
from utils.notify import get_notifier
from utils.runtime_flags import allow_interactive_auth

DEFAULT_STORAGE_STATE_DIR = 'storage-states'
TOPIC_STATE_DIR = 'linuxdo_reads'
DEFAULT_BASE_TOPIC_ID_START = 1_000_000
DEFAULT_BASE_TOPIC_ID_END = 1_100_000
DEFAULT_MAX_POSTS = 100
DEFAULT_MAX_TOPIC_ATTEMPTS = 60
DEFAULT_MAX_RUNTIME_SECONDS = 900


TopicStatus = Literal['valid', 'invalid', 'error', 'challenge', 'unknown']
VerificationStatus = Literal['verified', 'uncertain', 'failed']
OverallStatus = Literal['success', 'partial_success', 'uncertain', 'failed', 'infra_failed']


@dataclass
class TopicVisitResult:
    topic_id: int
    url: str
    status: TopicStatus
    pages_read: int = 0
    error: str | None = None


@dataclass
class ReadRuntimeState:
    last_topic_id: int = 0
    last_success_topic_id: int = 0
    invalid_streak: int = 0
    attempted_count: int = 0
    last_run_at: str = ''


@dataclass
class ReadAccountResult:
    username: str
    overall_status: OverallStatus
    verification_status: VerificationStatus
    login_restored: bool = False
    login_performed: bool = False
    challenge_detected: bool = False
    topics_attempted: int = 0
    valid_topics: int = 0
    pages_read: int = 0
    last_topic_id: int = 0
    error: str | None = None
    topic_visits: list[TopicVisitResult] = field(default_factory=list)
    duration_seconds: int = 0


def classify_read_error(error: Exception | str) -> str:
    message = str(error)
    lowered = message.lower()
    if 'could not connect to server' in lowered or 'failed to connect' in lowered:
        return f'Provider unreachable: {message}'
    if 'timeout' in lowered or 'timed out' in lowered:
        return f'Network timeout: {message}'
    if 'challenge' in lowered:
        return f'Challenge error: {message}'
    return message


def get_int_env(name: str, default: int) -> int:
    """读取整数环境变量；空字符串或非法值时回退默认值。"""
    raw = os.getenv(name)
    if raw is None:
        return default

    raw = raw.strip()
    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        print(f'⚠️ Invalid integer for {name}: {raw!r}, using default {default}')
        return default


def load_linuxdo_accounts() -> list[dict]:
    """从 ACCOUNTS_LINUX_DO 或 ACCOUNTS 加载 Linux.do 账号。"""
    accounts_str = os.getenv('ACCOUNTS_LINUX_DO') or os.getenv('ACCOUNTS')
    if not accounts_str:
        print('❌ ACCOUNTS_LINUX_DO/ACCOUNTS environment variable not found')
        return []

    try:
        accounts_data = json.loads(accounts_str)
        if not isinstance(accounts_data, list):
            print('❌ Account configuration must be a JSON array')
            return []

        linuxdo_accounts = []
        seen_usernames = set()

        for i, account in enumerate(accounts_data):
            if not isinstance(account, dict):
                print(f'⚠️ Account[{i}] must be a dictionary, skipping')
                continue

            username = account.get('username')
            password = account.get('password')

            if not username or not password:
                print(f'⚠️ Account[{i}] missing username or password, skipping')
                continue

            if username in seen_usernames:
                print(f'ℹ️ Skipping duplicate account: {username}')
                continue

            seen_usernames.add(username)
            linuxdo_accounts.append({'username': username, 'password': password})

        return linuxdo_accounts
    except json.JSONDecodeError as e:
        print(f'❌ Failed to parse account configuration: {e}')
        return []
    except Exception as e:
        print(f'❌ Error loading account configuration: {e}')
        return []


class LinuxDoReadPosts:
    def __init__(
        self,
        username: str,
        password: str,
        storage_state_dir: str = DEFAULT_STORAGE_STATE_DIR,
        topic_state_dir: str = TOPIC_STATE_DIR,
    ):
        self.username = username
        self.password = password
        self.storage_state_dir = storage_state_dir
        self.topic_state_dir = topic_state_dir
        self.username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()[:8]

        os.makedirs(self.storage_state_dir, exist_ok=True)
        os.makedirs(self.topic_state_dir, exist_ok=True)

        self.storage_state_path = os.path.join(self.storage_state_dir, f'linuxdo_{self.username_hash}_storage_state.json')
        self.topic_state_path = os.path.join(self.topic_state_dir, f'{self.username_hash}_topic_state.json')

    def _load_topic_state(self) -> ReadRuntimeState:
        try:
            if os.path.exists(self.topic_state_path):
                with open(self.topic_state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return ReadRuntimeState(**data)

            # 兼容旧版 txt 缓存
            legacy_topic_id_path = os.path.join(self.topic_state_dir, f'{self.username_hash}_topic_id.txt')
            if os.path.exists(legacy_topic_id_path):
                with open(legacy_topic_id_path, 'r', encoding='utf-8') as f:
                    raw = f.read().strip()
                if raw.isdigit():
                    topic_id = int(raw)
                    print(f'ℹ️ {self.username}: Migrating legacy topic cache from txt to json state')
                    state = ReadRuntimeState(last_topic_id=topic_id, last_success_topic_id=topic_id)
                    self._save_topic_state(state)
                    return state
        except Exception as e:
            print(f'⚠️ {self.username}: Failed to load topic state: {e}')
        return ReadRuntimeState()

    def _save_topic_state(self, state: ReadRuntimeState) -> None:
        state.last_run_at = datetime.now().isoformat()
        try:
            with open(self.topic_state_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(state), f, ensure_ascii=False, indent=2)
            print(f'ℹ️ {self.username}: Topic state saved')
        except Exception as e:
            print(f'⚠️ {self.username}: Failed to save topic state: {e}')

    def _next_topic_id(self, state: ReadRuntimeState, base_topic_id: int) -> int:
        current_topic_id = max(base_topic_id, state.last_topic_id)
        if state.invalid_streak >= 5:
            return current_topic_id + random.randint(50, 100)
        return current_topic_id + random.randint(1, 5)

    async def _is_logged_in(self, page) -> bool:
        try:
            print(f'ℹ️ {self.username}: Checking login status...')
            await page.goto('https://linux.do/', wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)

            current_url = page.url
            print(f'ℹ️ {self.username}: Current URL: {current_url}')
            if current_url.startswith('https://linux.do/login'):
                return False
            if 'linux.do/challenge' in current_url:
                return False

            has_forum_session = await page.context.cookies()
            if any(cookie.get('name') == '_forum_session' for cookie in has_forum_session):
                return True

            maybe_user_menu = await page.query_selector('header .d-header-icons, .user-menu, .header-dropdown-toggle')
            return maybe_user_menu is not None
        except Exception as e:
            print(f'⚠️ {self.username}: Error checking login status: {e}')
            return False

    async def _do_login(self, page) -> tuple[bool, bool]:
        """返回 (login_success, challenge_detected)。"""
        challenge_detected = False
        try:
            print(f'ℹ️ {self.username}: Starting login process...')
            if not page.url.startswith('https://linux.do/login'):
                await page.goto('https://linux.do/login', wait_until='domcontentloaded')

            await page.wait_for_selector('#login-account-name', timeout=20000)
            await page.fill('#login-account-name', self.username)
            await page.fill('#login-account-password', self.password)
            await page.click('#login-button')
            await page.wait_for_timeout(5000)

            current_url = page.url
            print(f'ℹ️ {self.username}: URL after login: {current_url}')

            if 'linux.do/challenge' in current_url:
                challenge_detected = True
                if not allow_interactive_auth():
                    print(f'❌ {self.username}: Interactive challenge required in unattended mode')
                    return False, challenge_detected
                print(f'⚠️ {self.username}: Challenge detected, waiting for manual resolution...')
                await page.wait_for_timeout(30000)

            await save_page_content_to_file(page, 'login_result', self.username)
            if await self._is_logged_in(page):
                print(f'✅ {self.username}: Login successful')
                return True, challenge_detected

            print(f'❌ {self.username}: Login failed, still not authenticated')
            await take_screenshot(page, 'login_failed', self.username)
            return False, challenge_detected
        except Exception as e:
            print(f'❌ {self.username}: Error during login: {e}')
            await take_screenshot(page, 'login_error', self.username)
            return False, challenge_detected

    async def _scroll_to_read(self, page) -> int:
        """返回估算的已阅读页数增量。页面行为层，不作为业务验证。"""
        page_reads = 0
        last_snapshot = ''
        stagnant_count = 0

        for _ in range(25):
            timeline_element = await page.query_selector('.timeline-replies')
            if not timeline_element:
                break

            inner_text = (await timeline_element.inner_text()).strip()
            if inner_text == last_snapshot:
                stagnant_count += 1
            else:
                stagnant_count = 0
                last_snapshot = inner_text

            try:
                parts = [part.strip() for part in inner_text.split('/')]
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    current_page = int(parts[0])
                    total_pages = int(parts[1])
                    page_reads = max(page_reads, total_pages - current_page)
                    if current_page >= total_pages:
                        break
            except Exception:
                pass

            if stagnant_count >= 2:
                break

            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await page.wait_for_timeout(random.randint(1000, 2000))

        return page_reads

    async def _visit_topic(self, page, topic_id: int) -> TopicVisitResult:
        topic_url = f'https://linux.do/t/topic/{topic_id}'
        try:
            print(f'ℹ️ {self.username}: Opening topic {topic_id}...')
            await page.goto(topic_url, wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)

            if 'linux.do/challenge' in page.url:
                return TopicVisitResult(topic_id=topic_id, url=topic_url, status='challenge', error='Challenge page hit')

            timeline_element = await page.query_selector('.timeline-replies')
            if not timeline_element:
                return TopicVisitResult(topic_id=topic_id, url=topic_url, status='invalid', error='timeline-replies not found')

            inner_text = (await timeline_element.inner_text()).strip()
            parts = [part.strip() for part in inner_text.split('/')]
            if not (len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()):
                return TopicVisitResult(topic_id=topic_id, url=topic_url, status='unknown', error=f'unparsable timeline: {inner_text}')

            pages_read = await self._scroll_to_read(page)
            await page.wait_for_timeout(random.randint(500, 1200))
            return TopicVisitResult(topic_id=topic_id, url=topic_url, status='valid', pages_read=max(1, pages_read))
        except Exception as e:
            return TopicVisitResult(topic_id=topic_id, url=topic_url, status='error', error=classify_read_error(e))

    async def _read_posts(
        self,
        page,
        base_topic_id: int,
        max_posts: int,
        max_topic_attempts: int,
        max_runtime_seconds: int,
    ) -> tuple[ReadRuntimeState, list[TopicVisitResult]]:
        state = self._load_topic_state()
        state.last_topic_id = max(base_topic_id, state.last_topic_id)
        print(
            f'ℹ️ {self.username}: Starting from topic ID {state.last_topic_id} '
            f'(base: {base_topic_id}, last_success: {state.last_success_topic_id})'
        )

        results: list[TopicVisitResult] = []
        read_pages = 0
        started_at = time.time()

        while read_pages < max_posts and state.attempted_count < max_topic_attempts:
            if time.time() - started_at >= max_runtime_seconds:
                print(f'⚠️ {self.username}: Reached runtime limit')
                break

            next_topic_id = self._next_topic_id(state, base_topic_id)
            state.last_topic_id = next_topic_id
            state.attempted_count += 1

            visit_result = await self._visit_topic(page, next_topic_id)
            results.append(visit_result)

            if visit_result.status == 'valid':
                state.invalid_streak = 0
                state.last_success_topic_id = next_topic_id
                read_pages += visit_result.pages_read
            else:
                state.invalid_streak += 1

        self._save_topic_state(state)
        return state, results

    async def run(
        self,
        max_posts: int = DEFAULT_MAX_POSTS,
        max_topic_attempts: int = DEFAULT_MAX_TOPIC_ATTEMPTS,
        max_runtime_seconds: int = DEFAULT_MAX_RUNTIME_SECONDS,
    ) -> ReadAccountResult:
        print(f'ℹ️ {self.username}: Starting Linux.do read posts task')

        base_topic_id = get_int_env(
            'LINUXDO_BASE_TOPIC_ID',
            random.randint(DEFAULT_BASE_TOPIC_ID_START, DEFAULT_BASE_TOPIC_ID_END),
        )

        result = ReadAccountResult(
            username=self.username,
            overall_status='failed',
            verification_status='failed',
        )

        start_time = time.time()

        async with AsyncCamoufox(headless=False, humanize=True, locale='en-US') as browser:
            storage_state = self.storage_state_path if os.path.exists(self.storage_state_path) else None
            if storage_state:
                print(f'ℹ️ {self.username}: Restoring storage state from cache')
            else:
                print(f'ℹ️ {self.username}: No cache file found, starting fresh')

            context = await browser.new_context(storage_state=storage_state)
            page = await context.new_page()

            try:
                restored = await self._is_logged_in(page)
                result.login_restored = restored

                if not restored:
                    login_success, challenge_detected = await self._do_login(page)
                    result.login_performed = True
                    result.challenge_detected = challenge_detected
                    if not login_success:
                        result.overall_status = 'failed'
                        result.verification_status = 'failed'
                        result.error = 'Login failed'
                        return result

                    await context.storage_state(path=self.storage_state_path)
                    print(f'✅ {self.username}: Storage state saved to cache file')

                state, topic_visits = await self._read_posts(
                    page=page,
                    base_topic_id=base_topic_id,
                    max_posts=max_posts,
                    max_topic_attempts=max_topic_attempts,
                    max_runtime_seconds=max_runtime_seconds,
                )

                result.topic_visits = topic_visits
                result.topics_attempted = len(topic_visits)
                result.valid_topics = len([visit for visit in topic_visits if visit.status == 'valid'])
                result.pages_read = sum(visit.pages_read for visit in topic_visits)
                result.last_topic_id = state.last_topic_id

                if any(visit.status == 'error' and visit.error and visit.error.startswith('Provider unreachable') for visit in topic_visits):
                    result.overall_status = 'infra_failed'
                    result.verification_status = 'failed'
                    result.error = 'Provider unreachable during topic traversal'
                elif result.valid_topics == 0:
                    result.overall_status = 'failed'
                    result.verification_status = 'failed'
                    result.error = 'No valid topics were read'
                else:
                    result.overall_status = 'uncertain'
                    result.verification_status = 'uncertain'

                return result
            except Exception as e:
                result.overall_status = 'infra_failed'
                result.verification_status = 'failed'
                result.error = classify_read_error(e)
                await take_screenshot(page, 'error', self.username)
                return result
            finally:
                result.duration_seconds = int(time.time() - start_time)
                await page.close()
                await context.close()


def format_duration(duration_seconds: int) -> str:
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


async def main() -> int:
    load_dotenv(override=True)

    print('🚀 Linux.do read posts script started')
    print(f'🕒 Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    accounts = load_linuxdo_accounts()
    if not accounts:
        print('❌ No Linux.do accounts found')
        return 1

    print(f'ℹ️ Found {len(accounts)} Linux.do account(s)')
    notifier = get_notifier()
    results: list[ReadAccountResult] = []

    for account in accounts:
        print(f"\n{'=' * 50}")
        print(f"📌 Processing: {account['username']}")
        print(f"{'=' * 50}")

        reader = LinuxDoReadPosts(username=account['username'], password=account['password'])
        result = await reader.run(
            max_posts=get_int_env('LINUXDO_MAX_POSTS', DEFAULT_MAX_POSTS),
            max_topic_attempts=get_int_env('LINUXDO_MAX_TOPIC_ATTEMPTS', DEFAULT_MAX_TOPIC_ATTEMPTS),
            max_runtime_seconds=get_int_env('LINUXDO_MAX_RUNTIME_SECONDS', DEFAULT_MAX_RUNTIME_SECONDS),
        )
        results.append(result)
        print(
            f"Result: overall_status={result.overall_status}, verification_status={result.verification_status}, "
            f"valid_topics={result.valid_topics}, pages_read={result.pages_read}, duration={format_duration(result.duration_seconds)}"
        )

    notification_lines = [
        f'🕒 Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
    ]

    uncertain_count = 0
    failed_count = 0
    infra_failed_count = 0
    total_pages = 0

    for result in results:
        duration = format_duration(result.duration_seconds)
        total_pages += result.pages_read

        if result.overall_status == 'infra_failed':
            infra_failed_count += 1
        elif result.overall_status == 'failed':
            failed_count += 1
        else:
            uncertain_count += 1

        if result.overall_status in {'uncertain', 'success', 'partial_success'}:
            notification_lines.append(
                f"⚠️ {result.username}: page actions completed but business result is {result.verification_status} "
                f"({duration})\n"
                f"   topics attempted={result.topics_attempted}, valid={result.valid_topics}, "
                f"pages_read={result.pages_read}, last_topic_id={result.last_topic_id}"
            )
        else:
            notification_lines.append(f"❌ {result.username}: {result.error or 'Unknown error'} ({duration})")

    notification_lines.append('')
    notification_lines.append(f'📊 Total estimated pages read: {total_pages}')
    notification_lines.append(
        f'📊 uncertain={uncertain_count}, failed={failed_count}, infra_failed={infra_failed_count}'
    )

    notify_content = '\n'.join(notification_lines)
    notifier.push_message('Linux.do Read Posts', notify_content, msg_type='text')

    # 严格业务验证模式下，没有 verified 结果，因此只要没有硬失败就返回 0
    return 0 if uncertain_count > 0 and failed_count == 0 and infra_failed_count == 0 else 1


def run_main():
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print('\n⚠️ Program interrupted by user')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ Error occurred during program execution: {e}')
        sys.exit(1)


if __name__ == '__main__':
    run_main()
