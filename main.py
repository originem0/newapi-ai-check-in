#!/usr/bin/env python3
"""
自动化奖励脚本入口
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(override=True)

from checkin import CheckIn
from utils.balance_hash import load_balance_hash, save_balance_hash
from utils.config import AppConfig
from utils.notify import get_notifier
from utils.run_models import AccountRunResult

BALANCE_HASH_FILE = 'balance_hash.txt'


def generate_balance_hash(balances: dict | None) -> str:
    """生成完整余额状态的 hash。"""
    simple_balances: dict[str, list[dict[str, float | str]]] = {}
    if balances:
        for account_key, account_balances in balances.items():
            snapshot_items = []
            for auth_method in sorted(account_balances):
                balance_info = account_balances[auth_method]
                snapshot_items.append(
                    {
                        'auth_method': auth_method,
                        'quota': float(balance_info['quota']),
                        'used': float(balance_info['used']),
                        'bonus': float(balance_info.get('bonus', 0)),
                    }
                )
            simple_balances[account_key] = snapshot_items

    balance_json = json.dumps(simple_balances, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(balance_json.encode('utf-8')).hexdigest()[:16]


def _build_account_summary(run_result: AccountRunResult) -> tuple[str, dict[str, dict[str, float]], bool]:
    balances: dict[str, dict[str, float]] = {}
    lines = [f'📣 {run_result.account_name} Summary:']

    for attempt in run_result.attempts:
        status = '✅ SUCCESS' if attempt.success else '❌ FAILED'
        lines.append(f'  {status} with {attempt.auth_method} authentication')
        if attempt.success and attempt.user_state:
            lines.append(f'    💰 {attempt.user_state.display}')
            balances[attempt.auth_method] = {
                'quota': attempt.user_state.quota,
                'used': attempt.user_state.used_quota,
                'bonus': attempt.user_state.bonus_quota,
            }
        else:
            error = attempt.error or 'Unknown error'
            lines.append(f'    🔺 {error}')

    if run_result.system_error:
        lines.append(f'    🔺 System error: {run_result.system_error}')

    success_count = len(run_result.successful_attempts)
    total_attempts = len(run_result.attempts)
    lines.append(f'\n📊 Authentication attempts: {success_count}/{total_attempts} successful')
    return '\n'.join(lines), balances, len(run_result.failed_attempts) > 0 or bool(run_result.system_error)


def _build_run_summary(results: list[AccountRunResult]) -> tuple[int, int, int]:
    total_accounts = len(results)
    successful_accounts = len([result for result in results if result.account_success])
    failed_accounts = total_accounts - successful_accounts
    return total_accounts, successful_accounts, failed_accounts


async def main() -> int:
    print('🚀 newapi.ai multi-account automation script started (using Camoufox)')
    print(f'🕒 Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    app_config = AppConfig.load_from_env()
    print(f'⚙️ Loaded {len(app_config.providers)} provider(s)')

    if not app_config.accounts:
        print('❌ Unable to load account configuration, program exits')
        return 1

    print(f'⚙️ Found {len(app_config.accounts)} account(s)')

    last_balance_hash = load_balance_hash(BALANCE_HASH_FILE)
    notifier = get_notifier()

    run_results: list[AccountRunResult] = []
    notification_content: list[str] = []
    current_balances: dict[str, dict[str, dict[str, float]]] = {}
    need_notify = False

    for i, account_config in enumerate(app_config.accounts):
        account_key = f'account_{i + 1}'
        account_name = account_config.get_display_name(i)
        if notification_content:
            notification_content.append('\n-------------------------------')

        provider_config = app_config.get_provider(account_config.provider)
        if not provider_config:
            print(f"❌ {account_name}: Provider '{account_config.provider}' configuration not found")
            run_result = AccountRunResult(
                account_name=account_name,
                provider_name=account_config.provider,
                system_error=f"Provider '{account_config.provider}' configuration not found",
            )
        else:
            print(f"🌀 Processing {account_name} using provider '{account_config.provider}'")
            try:
                checkin = CheckIn(account_name, account_config, provider_config, global_proxy=app_config.global_proxy)
                run_result = await checkin.execute()
            except Exception as e:
                print(f'❌ {account_name} processing exception: {e}')
                run_result = AccountRunResult(
                    account_name=account_name,
                    provider_name=account_config.provider,
                    system_error=str(e),
                )

        run_results.append(run_result)
        account_summary, account_balances, account_needs_notify = _build_account_summary(run_result)
        notification_content.append(account_summary)
        if run_result.account_success:
            current_balances[account_key] = account_balances
        if account_needs_notify or not run_result.account_success:
            need_notify = True

    total_accounts, successful_accounts, failed_accounts = _build_run_summary(run_results)

    current_balance_hash = generate_balance_hash(current_balances) if current_balances else None
    print(f'\n\nℹ️ Current balance hash: {current_balance_hash}, Last balance hash: {last_balance_hash}')
    if current_balance_hash:
        if last_balance_hash is None:
            need_notify = True
            print('🔔 First run detected, will send notification with current balances')
        elif current_balance_hash != last_balance_hash:
            need_notify = True
            print('🔔 Balance changes detected, will send notification')
        else:
            print('ℹ️ No balance changes detected')
        save_balance_hash(BALANCE_HASH_FILE, current_balance_hash)

    if need_notify and notification_content:
        summary = [
            '-------------------------------',
            '📢 Automation result statistics:',
            f'🔵 Account success: {successful_accounts}/{total_accounts}',
            f'🔴 Account failed: {failed_accounts}/{total_accounts}',
        ]

        if total_accounts == 0:
            summary.append('⚠️ No runnable accounts were found')
        elif failed_accounts == 0:
            summary.append('✅ All accounts succeeded')
        elif successful_accounts > 0:
            summary.append('⚠️ Some accounts succeeded')
        else:
            summary.append('❌ All accounts failed')

        time_info = f'🕓 Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        notify_content = '\n\n'.join([time_info, '\n'.join(notification_content), '\n'.join(summary)])

        print(notify_content)
        notifier.push_message('Automation Run Alert', notify_content, msg_type='text')
        print('🔔 Notification sent due to failures or balance changes')
    else:
        print('ℹ️ All accounts succeeded and no balance changes detected, notification skipped')

    return 0 if successful_accounts > 0 else 1


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
