"""Tests for utils/balance_hash.py"""

import os
import tempfile

from utils.balance_hash import load_balance_hash, save_balance_hash


class TestBalanceHash:
    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            filepath = f.name

        try:
            save_balance_hash(filepath, "abc123")
            result = load_balance_hash(filepath)
            assert result == "abc123"
        finally:
            os.unlink(filepath)

    def test_load_nonexistent_file(self):
        result = load_balance_hash("/nonexistent/path/file.txt")
        assert result is None

    def test_load_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            filepath = f.name

        try:
            result = load_balance_hash(filepath)
            assert result == ""
        finally:
            os.unlink(filepath)

    def test_load_whitespace_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("  abc123  \n")
            filepath = f.name

        try:
            result = load_balance_hash(filepath)
            assert result == "abc123"
        finally:
            os.unlink(filepath)
