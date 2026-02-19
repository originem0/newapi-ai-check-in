import os
import smtplib
from email.mime.text import MIMEText
from typing import Literal

from curl_cffi import requests as curl_requests


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

	def send_email(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		if not self.email_user or not self.email_pass or not self.email_to:
			raise ValueError('Email configuration not set')

		# MIMEText 需要 'plain' 或 'html'，而不是 'text'
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
		curl_requests.post('https://www.pushplus.plus/send', json=data, timeout=30)

	def send_serverPush(self, title: str, content: str):
		if not self.server_push_key:
			raise ValueError('Server Push key not configured')

		data = {'title': title, 'desp': content}
		curl_requests.post(f'https://sctapi.ftqq.com/{self.server_push_key}.send', json=data, timeout=30)

	def send_dingtalk(self, title: str, content: str):
		if not self.dingding_webhook:
			raise ValueError('DingTalk Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		curl_requests.post(self.dingding_webhook, json=data, timeout=30)

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
		curl_requests.post(self.feishu_webhook, json=data, timeout=30)

	def send_wecom(self, title: str, content: str):
		if not self.weixin_webhook:
			raise ValueError('WeChat Work Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		curl_requests.post(self.weixin_webhook, json=data, timeout=30)

	def send_telegram(self, title: str, content: str):
		if not self.telegram_bot_token or not self.telegram_chat_id:
			raise ValueError('Telegram Bot Token or Chat ID not configured')

		text = f'{title}\n\n{content}'
		# 不使用 parse_mode 避免签到内容中的特殊字符（$*_[]等）导致解析失败
		data = {'chat_id': self.telegram_chat_id, 'text': text}
		response = curl_requests.post(
			f'https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage', json=data, timeout=30
		)
		result = response.json()
		if not result.get('ok'):
			raise RuntimeError(f'Telegram API error: {result.get("description", "Unknown error")}')

	def push_message(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		# 只尝试已配置的通知方式，跳过未配置的
		notifications = []
		if self.email_user and self.email_pass and self.email_to:
			notifications.append(('Email', lambda: self.send_email(title, content, msg_type)))
		if self.pushplus_token:
			notifications.append(('PushPlus', lambda: self.send_pushplus(title, content)))
		if self.server_push_key:
			notifications.append(('Server Push', lambda: self.send_serverPush(title, content)))
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
			return

		success_count = 0
		for name, func in notifications:
			try:
				func()
				success_count += 1
				print(f'🔹 [{name}]: Message push successful!')
			except Exception as e:
				print(f'🔸 [{name}]: Message push failed! Reason: {str(e)}')

		print(f'📬 Notification summary: {success_count}/{len(notifications)} methods successful')


notify = NotificationKit()
