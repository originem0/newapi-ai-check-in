#!/usr/bin/env python3
"""
Wait-for-secrets implementation for GitHub Actions
Based on https://github.com/step-security/wait-for-secrets
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from curl_cffi import requests as curl_requests


class WaitForSecrets:
    def get_oidc_token(self) -> Optional[str]:
        request_token = os.getenv('ACTIONS_ID_TOKEN_REQUEST_TOKEN')
        request_url = os.getenv('ACTIONS_ID_TOKEN_REQUEST_URL')

        if not request_token or not request_url:
            print('⚠️ Not running in GitHub Actions environment (OIDC tokens not available)')
            return None

        try:
            headers = {
                'Authorization': f'Bearer {request_token}',
                'Accept': 'application/json; api-version=2.0',
                'Content-Type': 'application/json',
            }

            audience_url = f'{request_url}&audience=api://ActionsOIDCGateway/Certify'
            response = curl_requests.get(audience_url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                token = data.get('value')
                if token:
                    return token
                print('❌ OIDC token not found in response')
                return None
            print(f'❌ Failed to get OIDC token: HTTP {response.status_code}')
            return None

        except Exception as e:
            print(f'❌ Error getting OIDC token: {e}')
            return None

    def parse_data_from_environment(self) -> Optional[list[str]]:
        repository = os.getenv('GITHUB_REPOSITORY')
        run_id = os.getenv('GITHUB_RUN_ID')

        if not repository or not run_id:
            print('⚠️ Not running in GitHub Actions environment')
            return None

        if '/' in repository:
            owner, repo = repository.split('/', 1)
        else:
            owner, repo = '', ''

        return [owner, repo, run_id]

    def generate_secret_url(self, owner: str, repo: str, run_id: str) -> str:
        return f'https://app.stepsecurity.io/secrets/{owner}/{repo}/{run_id}'

    async def get(self, secrets_metadata: dict, timeout: int = 5, notification: dict | None = None) -> Optional[dict]:
        notification = notification or {}

        try:
            environment_data = self.parse_data_from_environment()
            if not environment_data:
                return None

            owner, repo, run_id = environment_data
            secret_url = self.generate_secret_url(owner, repo, run_id)

            token = self.get_oidc_token()
            if not token:
                return None

            api_url = 'https://prod.api.stepsecurity.io/v1/secrets'
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

            secrets_metadata_payload = []
            for secret_name, secret_info in secrets_metadata.items():
                secrets_metadata_payload.append(f'{secret_name}:')
                secrets_metadata_payload.append(f"name: {secret_info.get('name', secret_name)}")
                secrets_metadata_payload.append(f"description: {secret_info.get('description', '')}")

            put_response = curl_requests.put(api_url, headers=headers, json=secrets_metadata_payload, timeout=30)
            if put_response.status_code != 200:
                print(f'❌ Failed to register secret request: HTTP {put_response.status_code}, {put_response.text}')
                return None

            print('✅ Secret request registered')

            try:
                from utils.notify import get_notifier

                notifier = get_notifier()
                notify_title = notification.get('title', 'Secret Required:')
                notify_content = notification.get('content', notification.get('message', ''))
                if notify_content:
                    notify_content += '\n'
                notify_content += f'🔗 Please visit this URL to input secrets in {timeout} minute(s):\n{secret_url}'
                notifier.push_message(notify_title, notify_content, msg_type='text')
                print('✅ Notification sent with secret URL')
            except Exception as e:
                print(f'⚠️ Failed to send notification: {e}')

            start_time = time.time()
            timeout_in_seconds = timeout * 60
            secrets_data = None

            print(f'⏳ Polling for secrets (timeout: {timeout} minute(s))...')
            print(f'  🔗 Visit this URL to input secrets: {secret_url}')

            while True:
                elapsed = time.time() - start_time
                if elapsed >= timeout_in_seconds:
                    print(f'⏱️ Timeout after {timeout} minute(s) waiting for secrets')
                    print(f'🔗 Secret URL was: {secret_url}')
                    break

                try:
                    token = self.get_oidc_token()
                    if not token:
                        break

                    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                    get_response = curl_requests.get(api_url, headers=headers, timeout=30)

                    if get_response.status_code == 200:
                        data = get_response.json()
                        if data.get('areSecretsSet', False):
                            secrets_array = data.get('secrets', [])
                            if secrets_array:
                                secrets_data = {}
                                for secret in secrets_array:
                                    name = secret.get('Name')
                                    value = secret.get('Value')
                                    if name and value:
                                        secrets_data[name] = value
                                print(f"✅ Secrets received for keys: {list(secrets_data.keys())}")
                                break
                        else:
                            print(f'  🔗 Visit this URL to input secrets: {secret_url}')
                            await asyncio.sleep(9)
                    else:
                        try:
                            body = get_response.text
                            if body != 'Token used before issued':
                                print(f'Response: {body}')
                                break
                        except Exception:
                            print(f'⚠️ Unexpected response: HTTP {get_response.status_code}')

                except Exception as e:
                    print(f'⚠️ Polling error: {e}')

                await asyncio.sleep(1)

            try:
                token = self.get_oidc_token()
                if not token:
                    raise RuntimeError('Failed to get OIDC token for clearing secrets')

                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                delete_response = curl_requests.delete(api_url, headers=headers, timeout=30)

                if delete_response.status_code == 200:
                    print('✅ Secret cleared from datastore')
                else:
                    print(f'⚠️ Failed to clear secret: HTTP {delete_response.status_code}, {delete_response.text}')

            except Exception as e:
                print(f'⚠️ Error clearing secret: {e}')

            return secrets_data

        except Exception as e:
            print(f'❌ Error in wait_for_secrets: {e}')
            return None
