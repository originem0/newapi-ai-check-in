"""Tests for linuxdo_read_posts.py."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from linuxdo_read_posts import LinuxDoReadPosts, ReadRuntimeState, classify_read_error, load_linuxdo_accounts


class TestLoadLinuxdoAccounts:
    def test_load_from_accounts_linux_do(self):
        accounts = json.dumps([{'username': 'u1', 'password': 'p1'}])
        old_accounts_linux_do = os.environ.get('ACCOUNTS_LINUX_DO')
        try:
            os.environ['ACCOUNTS_LINUX_DO'] = accounts
            if 'ACCOUNTS' in os.environ:
                del os.environ['ACCOUNTS']
            result = load_linuxdo_accounts()
            assert result == [{'username': 'u1', 'password': 'p1'}]
        finally:
            if old_accounts_linux_do is None:
                os.environ.pop('ACCOUNTS_LINUX_DO', None)
            else:
                os.environ['ACCOUNTS_LINUX_DO'] = old_accounts_linux_do

    def test_deduplicates_usernames(self):
        accounts = json.dumps(
            [{'username': 'u1', 'password': 'p1'}, {'username': 'u1', 'password': 'p2'}]
        )
        old_accounts_linux_do = os.environ.get('ACCOUNTS_LINUX_DO')
        try:
            os.environ['ACCOUNTS_LINUX_DO'] = accounts
            result = load_linuxdo_accounts()
            assert result == [{'username': 'u1', 'password': 'p1'}]
        finally:
            if old_accounts_linux_do is None:
                os.environ.pop('ACCOUNTS_LINUX_DO', None)
            else:
                os.environ['ACCOUNTS_LINUX_DO'] = old_accounts_linux_do


class TestTopicState:
    def test_load_and_save_topic_state(self):
        root = Path('tests') / '_tmp_linuxdo_state' / uuid.uuid4().hex
        storage_dir = root / 'storage'
        topic_dir = root / 'topics'
        storage_dir.mkdir(parents=True, exist_ok=True)
        topic_dir.mkdir(parents=True, exist_ok=True)

        try:
            reader = LinuxDoReadPosts('user', 'pass', storage_state_dir=str(storage_dir), topic_state_dir=str(topic_dir))
            state = ReadRuntimeState(last_topic_id=123, last_success_topic_id=120, invalid_streak=2, attempted_count=8)
            reader._save_topic_state(state)
            loaded = reader._load_topic_state()
            assert loaded.last_topic_id == 123
            assert loaded.last_success_topic_id == 120
            assert loaded.invalid_streak == 2
            assert loaded.attempted_count == 8
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestClassifyReadError:
    def test_connection_error(self):
        assert classify_read_error('Failed to connect to server').startswith('Provider unreachable:')

    def test_timeout_error(self):
        assert classify_read_error('Operation timed out').startswith('Network timeout:')
