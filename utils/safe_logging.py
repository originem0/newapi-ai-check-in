#!/usr/bin/env python3
"""
安全日志与脱敏工具
"""

from __future__ import annotations

import hashlib
import os
from typing import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_FIELD_MARKERS = (
    'token',
    'secret',
    'cookie',
    'session',
    'password',
    'otp',
    'code',
    'key',
    'authorization',
)


def should_write_debug_artifacts() -> bool:
    """是否允许写入调试产物。默认关闭。"""
    return os.getenv('DEBUG_ARTIFACTS', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def mask_secret(value: object, visible: int = 0) -> str:
    """对敏感值脱敏。"""
    if value is None:
        return '<none>'

    text = str(value)
    if not text:
        return '<empty>'

    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]
    suffix = text[-visible:] if visible > 0 else ''
    if suffix:
        return f'<redacted:{digest}>...{suffix}'
    return f'<redacted:{digest}>'


def sanitize_mapping(data: Mapping[str, object]) -> dict[str, object]:
    """按字段名规则对映射中的敏感值脱敏。"""
    sanitized: dict[str, object] = {}
    for key, value in data.items():
        lowered = key.lower()
        if any(marker in lowered for marker in SENSITIVE_FIELD_MARKERS):
            sanitized[key] = mask_secret(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_url(url: str) -> str:
    """脱敏 URL 中的 query 参数。"""
    if not url:
        return url

    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    if not query_items:
        return url

    sanitized_items: list[tuple[str, str]] = []
    for key, value in query_items:
        lowered = key.lower()
        if any(marker in lowered for marker in SENSITIVE_FIELD_MARKERS):
            sanitized_items.append((key, mask_secret(value)))
        else:
            sanitized_items.append((key, value))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sanitized_items), parts.fragment))

