#!/usr/bin/env python3
"""
通知模块
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Callable, Literal

from curl_cffi import requests as curl_requests

MessageType = Literal['text', 'html']


@dataclass
class NotificationDispatchResult:
    name: str
    success: bool
    error: str | None = None


class NotificationKit:
    def __init__(self):
        self.email_user: str = os.getenv('EMAIL_USER', '')
        self.email_pass: str = os.getenv('EMAIL_PASS', '')
        self.email_to: str = os.getenv('EMAIL_TO', '')
        self.smtp_server: str = os.getenv('CUSTOM_SMTP_SERVER', '')
        self.pushplus_token = os.getenv('PUSHPLUS_TOKEN')
        self.server_push_key = os.getenv('SERVERPUSHKEY')
        self.dingding_webhook = os.getenv('DINGDING_WEBHOOK')
        self.feishu_webhook = os.getenv('FEISHU_WEBHOOK')
        self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

    @staticmethod
    def _ensure_http_success(response, provider_name: str) -> None:
        status_code = getattr(response, 'status_code', 200)
        if isinstance(status_code, int) and status_code >= 400:
            raise RuntimeError(f'{provider_name} HTTP {status_code}: {response.text[:200]}')

    def send_email(self, title: str, content: str, msg_type: MessageType = 'text'):
        if not self.email_user or not self.email_pass or not self.email_to:
            raise ValueError('Email configuration not set')

        mime_subtype = 'plain' if msg_type == 'text' else 'html'
        msg = MIMEText(content, mime_subtype, 'utf-8')
        msg['From'] = f'newapi.ai Assistant <{self.email_user}>'
        msg['To'] = self.email_to
        msg['Subject'] = title

        smtp_server = self.smtp_server if self.smtp_server else f'smtp.{self.email_user.split("@")[1]}'
        with smtplib.SMTP_SSL(smtp_server, 465) as server:
            server.login(self.email_user, self.email_pass)
            server.send_message(msg)

    def send_pushplus(self, title: str, content: str):
        if not self.pushplus_token:
            raise ValueError('PushPlus Token not configured')

        data = {'token': self.pushplus_token, 'title': title, 'content': content, 'template': 'html'}
        response = curl_requests.post('https://www.pushplus.plus/send', json=data, timeout=30)
        self._ensure_http_success(response, 'PushPlus')

    def send_server_push(self, title: str, content: str):
        if not self.server_push_key:
            raise ValueError('Server Push key not configured')

        data = {'title': title, 'desp': content}
        response = curl_requests.post(f'https://sctapi.ftqq.com/{self.server_push_key}.send', json=data, timeout=30)
        self._ensure_http_success(response, 'Server Push')

    # backward-compatible alias
    def send_serverPush(self, title: str, content: str):
        self.send_server_push(title, content)

    def send_dingtalk(self, title: str, content: str):
        if not self.dingding_webhook:
            raise ValueError('DingTalk Webhook not configured')

        data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
        response = curl_requests.post(self.dingding_webhook, json=data, timeout=30)
        self._ensure_http_success(response, 'DingTalk')

    def send_feishu(self, title: str, content: str):
        if not self.feishu_webhook:
            raise ValueError('Feishu Webhook not configured')

        data = {
            'msg_type': 'interactive',
            'card': {
                'elements': [{'tag': 'markdown', 'content': content, 'text_align': 'left'}],
                'header': {'template': 'blue', 'title': {'content': title, 'tag': 'plain_text'}},
            },
        }
        response = curl_requests.post(self.feishu_webhook, json=data, timeout=30)
        self._ensure_http_success(response, 'Feishu')

    def send_wecom(self, title: str, content: str):
        if not self.weixin_webhook:
            raise ValueError('WeChat Work Webhook not configured')

        data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
        response = curl_requests.post(self.weixin_webhook, json=data, timeout=30)
        self._ensure_http_success(response, 'WeChat Work')

    def send_telegram(self, title: str, content: str):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            raise ValueError('Telegram Bot Token or Chat ID not configured')

        text = f'{title}\n\n{content}'
        data = {'chat_id': self.telegram_chat_id, 'text': text}
        response = curl_requests.post(
            f'https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage', json=data, timeout=30
        )
        self._ensure_http_success(response, 'Telegram')
        result = response.json()
        if not result.get('ok'):
            raise RuntimeError(f'Telegram API error: {result.get("description", "Unknown error")}')

    def push_message(
        self, title: str, content: str, msg_type: MessageType = 'text'
    ) -> list[NotificationDispatchResult]:
        notifications: list[tuple[str, Callable[[], None]]] = []
        if self.email_user and self.email_pass and self.email_to:
            notifications.append(('Email', lambda: self.send_email(title, content, msg_type)))
        if self.pushplus_token:
            notifications.append(('PushPlus', lambda: self.send_pushplus(title, content)))
        if self.server_push_key:
            notifications.append(('Server Push', lambda: self.send_server_push(title, content)))
        if self.dingding_webhook:
            notifications.append(('DingTalk', lambda: self.send_dingtalk(title, content)))
        if self.feishu_webhook:
            notifications.append(('Feishu', lambda: self.send_feishu(title, content)))
        if self.weixin_webhook:
            notifications.append(('WeChat Work', lambda: self.send_wecom(title, content)))
        if self.telegram_bot_token and self.telegram_chat_id:
            notifications.append(('Telegram', lambda: self.send_telegram(title, content)))

        if not notifications:
            print('⚠️ No notification methods configured, skipping push')
            return []

        results: list[NotificationDispatchResult] = []
        for name, func in notifications:
            try:
                func()
                results.append(NotificationDispatchResult(name=name, success=True))
                print(f'🔹 [{name}]: Message push successful!')
            except Exception as e:
                results.append(NotificationDispatchResult(name=name, success=False, error=str(e)))
                print(f'🔸 [{name}]: Message push failed! Reason: {str(e)}')

        success_count = len([result for result in results if result.success])
        print(f'📬 Notification summary: {success_count}/{len(results)} methods successful')
        return results


def get_notifier() -> NotificationKit:
    return NotificationKit()


class LazyNotifier:
    def __getattr__(self, item):
        return getattr(get_notifier(), item)


notify = LazyNotifier()
