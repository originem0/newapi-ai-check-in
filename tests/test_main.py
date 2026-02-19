"""Tests for main.py - balance hash generation"""


from main import generate_balance_hash


class TestGenerateBalanceHash:
    def test_empty_balances(self):
        result = generate_balance_hash({})
        assert isinstance(result, str)
        assert len(result) == 16

    def test_deterministic(self):
        balances = {
            "account_1": {
                "linux.do": {"quota": 10.5, "used": 2.0, "bonus": 0.5},
            }
        }
        hash1 = generate_balance_hash(balances)
        hash2 = generate_balance_hash(balances)
        assert hash1 == hash2

    def test_different_balances_different_hash(self):
        b1 = {"account_1": {"linux.do": {"quota": 10.5, "used": 2.0, "bonus": 0.5}}}
        b2 = {"account_1": {"linux.do": {"quota": 11.0, "used": 2.0, "bonus": 0.5}}}
        assert generate_balance_hash(b1) != generate_balance_hash(b2)

    def test_none_balances(self):
        """None balances should not crash"""
        result = generate_balance_hash(None)
        assert isinstance(result, str)
