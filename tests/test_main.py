"""Tests for main.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from main import generate_balance_hash, main
from utils.run_models import AccountRunResult, AuthAttemptResult, UserState


class TestGenerateBalanceHash:
    def test_empty_balances(self):
        result = generate_balance_hash({})
        assert isinstance(result, str)
        assert len(result) == 16

    def test_deterministic(self):
        balances = {
            'account_1': {
                'linux.do': {'quota': 10.5, 'used': 2.0, 'bonus': 0.5},
            }
        }
        hash1 = generate_balance_hash(balances)
        hash2 = generate_balance_hash(balances)
        assert hash1 == hash2

    def test_used_or_bonus_changes_affect_hash(self):
        b1 = {'account_1': {'linux.do': {'quota': 10.5, 'used': 2.0, 'bonus': 0.5}}}
        b2 = {'account_1': {'linux.do': {'quota': 10.5, 'used': 3.0, 'bonus': 0.5}}}
        b3 = {'account_1': {'linux.do': {'quota': 10.5, 'used': 2.0, 'bonus': 1.5}}}
        assert generate_balance_hash(b1) != generate_balance_hash(b2)
        assert generate_balance_hash(b1) != generate_balance_hash(b3)

    def test_none_balances(self):
        result = generate_balance_hash(None)
        assert isinstance(result, str)


class TestMainExitCode:
    def test_returns_1_when_no_accounts_loaded(self):
        fake_app_config = MagicMock()
        fake_app_config.providers = {}
        fake_app_config.accounts = []

        with patch('main.AppConfig.load_from_env', return_value=fake_app_config):
            exit_code = asyncio.run(main())

        assert exit_code == 1

    def test_returns_0_when_one_account_succeeds(self):
        fake_account = MagicMock()
        fake_account.provider = 'neb'
        fake_account.get_display_name.return_value = 'neb 1'

        fake_provider = MagicMock()
        fake_provider.name = 'neb'

        fake_app_config = MagicMock()
        fake_app_config.providers = {'neb': fake_provider}
        fake_app_config.accounts = [fake_account]
        fake_app_config.global_proxy = None
        fake_app_config.get_provider.return_value = fake_provider

        run_result = AccountRunResult(
            account_name='neb 1',
            provider_name='neb',
            attempts=[
                AuthAttemptResult(
                    auth_method='cookies',
                    success=True,
                    user_state=UserState(quota=1.0, used_quota=0.2, bonus_quota=0.1, display='balance'),
                )
            ],
        )

        fake_checkin = MagicMock()
        fake_checkin.execute = AsyncMock(return_value=run_result)

        fake_notifier = MagicMock()
        fake_notifier.push_message.return_value = []

        with (
            patch('main.AppConfig.load_from_env', return_value=fake_app_config),
            patch('main.CheckIn', return_value=fake_checkin),
            patch('main.get_notifier', return_value=fake_notifier),
            patch('main.load_balance_hash', return_value=None),
            patch('main.save_balance_hash'),
        ):
            exit_code = asyncio.run(main())

        assert exit_code == 0

    def test_failed_attempt_does_not_count_as_account_success(self):
        fake_account = MagicMock()
        fake_account.provider = 'neb'
        fake_account.get_display_name.return_value = 'neb 1'

        fake_provider = MagicMock()
        fake_provider.name = 'neb'

        fake_app_config = MagicMock()
        fake_app_config.providers = {'neb': fake_provider}
        fake_app_config.accounts = [fake_account]
        fake_app_config.global_proxy = None
        fake_app_config.get_provider.return_value = fake_provider

        run_result = AccountRunResult(
            account_name='neb 1',
            provider_name='neb',
            attempts=[AuthAttemptResult(auth_method='cookies', success=False, error='bad cookies')],
        )

        fake_checkin = MagicMock()
        fake_checkin.execute = AsyncMock(return_value=run_result)
        fake_notifier = MagicMock()
        fake_notifier.push_message.return_value = []

        with (
            patch('main.AppConfig.load_from_env', return_value=fake_app_config),
            patch('main.CheckIn', return_value=fake_checkin),
            patch('main.get_notifier', return_value=fake_notifier),
            patch('main.load_balance_hash', return_value=None),
        ):
            exit_code = asyncio.run(main())

        assert exit_code == 1
