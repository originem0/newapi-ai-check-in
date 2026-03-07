#!/usr/bin/env python3
"""
运行结果模型
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserState:
    quota: float
    used_quota: float
    bonus_quota: float
    display: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> 'UserState':
        return cls(
            quota=float(payload['quota']),
            used_quota=float(payload['used_quota']),
            bonus_quota=float(payload['bonus_quota']),
            display=str(payload['display']),
        )


@dataclass
class AuthAttemptResult:
    auth_method: str
    success: bool
    error: str | None = None
    user_state: UserState | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountRunResult:
    account_name: str
    provider_name: str
    attempts: list[AuthAttemptResult] = field(default_factory=list)
    system_error: str | None = None

    @property
    def account_success(self) -> bool:
        return any(attempt.success for attempt in self.attempts)

    @property
    def successful_attempts(self) -> list[AuthAttemptResult]:
        return [attempt for attempt in self.attempts if attempt.success]

    @property
    def failed_attempts(self) -> list[AuthAttemptResult]:
        return [attempt for attempt in self.attempts if not attempt.success]
