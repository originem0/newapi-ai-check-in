#!/usr/bin/env python3
"""
运行时开关
"""

from __future__ import annotations

import os


def allow_interactive_auth() -> bool:
    """是否允许需要人工介入的认证流程。"""
    return os.getenv('ALLOW_INTERACTIVE_AUTH', '').strip().lower() in {'1', 'true', 'yes', 'on'}
