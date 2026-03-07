"""Tests for utils/http_utils.py."""

from utils.http_utils import classify_transport_error


class TestClassifyTransportError:
    def test_classifies_connection_failure(self):
        error = RuntimeError('curl: (7) Failed to connect to host: Could not connect to server')
        assert classify_transport_error(error).startswith('Provider unreachable:')

    def test_classifies_timeout(self):
        error = RuntimeError('operation timed out after 30000 milliseconds')
        assert classify_transport_error(error).startswith('Network timeout:')

    def test_classifies_dns(self):
        error = RuntimeError('Could not resolve host: example.com')
        assert classify_transport_error(error).startswith('DNS resolution failed:')
