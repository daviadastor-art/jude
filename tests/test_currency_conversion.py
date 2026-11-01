import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from config.currency import old_to_new, new_to_old, require_new_integer, require_old_multiple_of_rate


class CurrencyConversionTests(unittest.TestCase):
    def test_new_to_ichancy_is_one_to_one(self):
        self.assertEqual(new_to_old(250), 250)
        self.assertEqual(new_to_old(1), 1)

    def test_ichancy_old_to_new(self):
        self.assertEqual(old_to_new(25000), Decimal("25000"))
        self.assertEqual(old_to_new(100), Decimal("100"))

    def test_invalid_fractional_or_non_multiple_amounts(self):
        with self.assertRaises(ValueError):
            require_new_integer("250.5")
        self.assertEqual(require_old_multiple_of_rate(25050), 25050)
        with self.assertRaises(ValueError):
            new_to_old(-1)

    def test_round_trip(self):
        for amount in (1, 250, 10000):
            self.assertEqual(int(old_to_new(new_to_old(amount))), amount)


if __name__ == "__main__":
    unittest.main()
