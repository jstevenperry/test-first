import sqlite3
import unittest
from decimal import Decimal

from generated.database import Database


class ProductIdentityTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_seed_catalog_contains_required_products(self):
        self.assertEqual(
            self.db.list_products(),
            [
                {"sku": "FIRST-SPROUT", "name": "First Sprout Card Pack", "unit_price": "12.50", "stock_quantity": 100},
                {"sku": "REPOTTING-DAY", "name": "Repotting Day Card Pack", "unit_price": "18.00", "stock_quantity": 50},
                {"sku": "WINDOWSILL-JOURNAL", "name": "Windowsill Notes Journal", "unit_price": "24.00", "stock_quantity": 30},
            ],
        )

    def test_initialization_is_idempotent(self):
        self.db.initialize()
        self.assertEqual(len(self.db.list_products()), 3)

    def test_blank_sku_and_name_are_rejected(self):
        for sku, name in [("", "Name"), (" ", "Name"), ("SKU", ""), ("SKU", " \t")]:
            with self.subTest(sku=sku, name=name), self.assertRaises(ValueError):
                self.db.add_product(sku, name, "1.00", 1)

    def test_sku_uniqueness_is_case_sensitive(self):
        self.db.add_product("sku", "lowercase", "1.00", 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_product("sku", "duplicate", "1.00", 1)
        self.db.add_product("SKU", "uppercase", "1.00", 1)

    def test_zero_price_and_stock_are_valid(self):
        self.db.add_product("ZERO", "Zero product", "0", 0)
        self.assertEqual(self.db.get_product("ZERO")["unit_price"], "0.00")

    def test_negative_price_and_stock_are_invalid(self):
        with self.assertRaises(ValueError):
            self.db.add_product("NEGPRICE", "Negative price", "-0.001", 1)
        with self.assertRaises(ValueError):
            self.db.add_product("NEGSTOCK", "Negative stock", "1.00", -1)

    def test_stock_must_be_whole_non_boolean_integer(self):
        for quantity in (1.5, True, "2"):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.db.add_product("BAD", "Bad quantity", "1.00", quantity)

    def test_price_rounding_uses_half_up(self):
        self.db.add_product("ROUND", "Rounded", Decimal("1.005"), 1)
        self.assertEqual(self.db.get_product("ROUND")["unit_price"], "1.01")


if __name__ == "__main__":
    unittest.main()
