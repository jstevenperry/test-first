import unittest
from decimal import Decimal

from generated.money import cents, format_cents, format_rate, line_amounts, multiply


class MoneyRepresentationTests(unittest.TestCase):
    def test_ten_dimes_total_exactly_one_dollar(self):
        self.assertEqual(format_cents(multiply(Decimal("0.10"), 10)), "1.00")

    def test_half_up_price_rounding(self):
        self.assertEqual(format_cents(cents("1.005")), "1.01")

    def test_zero_quantity_is_exact_zero(self):
        self.assertEqual(multiply(Decimal("987.65"), 0), 0)

    def test_discount_and_tax_round_half_up_per_line(self):
        discounted = line_amounts(5, 1, 1000, 0)
        taxed = line_amounts(5, 1, 0, 1000)
        self.assertEqual(discounted, {"extended": 5, "discount": 1, "subtotal": 4, "tax": 0})
        self.assertEqual(taxed, {"extended": 5, "discount": 0, "subtotal": 5, "tax": 1})

    def test_ten_units_discount_and_tax(self):
        result = line_amounts(1800, 10, 1000, 1000)
        self.assertEqual(result, {"extended": 18000, "discount": 1800, "subtotal": 16200, "tax": 1620})

    def test_rates_are_integer_basis_points_and_format_as_percent(self):
        self.assertEqual(format_rate(0), "0.00")
        self.assertEqual(format_rate(1000), "10.00")

    def test_money_is_formatted_with_two_decimal_places(self):
        self.assertEqual(format_cents(cents("0")), "0.00")
        self.assertEqual(format_cents(cents("12.3")), "12.30")


if __name__ == "__main__":
    unittest.main()
