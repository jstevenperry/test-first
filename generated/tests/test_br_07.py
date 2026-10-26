import unittest

from generated.database import Database
from generated.tests.sprint2_helpers import ApiFixture, placement


class OrderCreationTests(unittest.TestCase, ApiFixture):
    def setUp(self):
        self.start_api()

    def tearDown(self):
        self.stop_api()

    def create(self, lines, **options):
        return self.db.create_order(placement(lines), **options)

    def test_ten_discounted_repottings_and_default_rates(self):
        order = self.create(
            [{"product_sku": "REPOTTING-DAY", "quantity": 10}],
            discount_rates={"REPOTTING-DAY": 1000},
        )
        self.assertEqual(len(order["items"]), 1)
        self.assertEqual(order["items"][0]["unit_price"], "18.00")
        self.assertEqual(order["items"][0]["discount_rate"], "10.00")
        self.assertEqual((order["subtotal"], order["total"]), ("162.00", "162.00"))

    def test_multiple_products_keep_price_and_sum_subtotal(self):
        order = self.create([
            {"product_sku": "FIRST-SPROUT", "quantity": 2},
            {"product_sku": "WINDOWSILL-JOURNAL", "quantity": 1},
        ])
        self.assertEqual([item["product_sku"] for item in order["items"]], ["FIRST-SPROUT", "WINDOWSILL-JOURNAL"])
        self.assertEqual([item["unit_price"] for item in order["items"]], ["12.50", "24.00"])
        self.assertEqual(order["subtotal"], "49.00")

    def test_discount_applies_only_to_selected_sku(self):
        order = self.create([
            {"product_sku": "REPOTTING-DAY", "quantity": 10},
            {"product_sku": "FIRST-SPROUT", "quantity": 1},
        ], discount_rates={"REPOTTING-DAY": 1000})
        self.assertEqual([item["discount_rate"] for item in order["items"]], ["10.00", "0.00"])
        self.assertEqual(order["subtotal"], "174.50")

    def test_duplicate_lines_combine_before_discount_and_retain_position(self):
        order = self.create([
            {"product_sku": "REPOTTING-DAY", "quantity": 5},
            {"product_sku": "FIRST-SPROUT", "quantity": 1},
            {"product_sku": "REPOTTING-DAY", "quantity": 5},
        ], discount_rates={"REPOTTING-DAY": 1000})
        self.assertEqual(
            [(item["product_sku"], item["quantity"]) for item in order["items"]],
            [("REPOTTING-DAY", 10), ("FIRST-SPROUT", 1)],
        )
        self.assertEqual(order["subtotal"], "174.50")

    def test_discount_and_tax_rounding_are_snapshotted(self):
        self.db.add_product("NICKEL", "Five cent item", "0.05", 4)
        discounted = self.create(
            [{"product_sku": "REPOTTING-DAY", "quantity": 10}],
            tax_rate_bps=1000,
            discount_rates={"REPOTTING-DAY": 1000},
        )
        self.assertEqual(discounted["items"][0]["tax_amount"], "16.20")
        self.assertEqual(discounted["subtotal"], "162.00")
        self.assertEqual(discounted["total"], "178.20")
        half_discount = self.create(
            [{"product_sku": "NICKEL", "quantity": 1}],
            discount_rates={"NICKEL": 1000},
        )
        half_tax = self.create(
            [{"product_sku": "NICKEL", "quantity": 1}],
            tax_rate_bps=1000,
        )
        self.assertEqual(half_discount["subtotal"], "0.04")
        self.assertEqual(half_tax["items"][0]["tax_amount"], "0.01")

    def test_combined_quantity_above_stock_is_atomic(self):
        stock = self.db.get_product("REPOTTING-DAY")["stock_quantity"]
        orders = self.db.list_orders()
        with self.assertRaises(OverflowError):
            self.create([
                {"product_sku": "REPOTTING-DAY", "quantity": stock},
                {"product_sku": "REPOTTING-DAY", "quantity": 1},
            ])
        self.assertEqual(self.db.get_product("REPOTTING-DAY")["stock_quantity"], stock)
        self.assertEqual(self.db.list_orders(), orders)

    def test_order_snapshots_survive_catalog_and_rate_changes(self):
        order = self.create(
            [{"product_sku": "REPOTTING-DAY", "quantity": 10}],
            discount_rates={"REPOTTING-DAY": 1000},
        )
        self.db.update_product_price("REPOTTING-DAY", "99.99")
        self.assertEqual(self.db.get_order(order["order_id"]), order)
        self.db.update_product_price("REPOTTING-DAY", "18.00")

    def test_created_orders_still_use_zero_defaults(self):
        _, _, order = self.request("POST", "/orders", placement())
        self.assertEqual(order["items"][0]["discount_rate"], "0.00")
        self.assertEqual(order["tax_rate"], "0.00")
        self.assertEqual((order["shipping_charge"], order["tax_amount"]), ("0.00", "0.00"))


if __name__ == "__main__":
    unittest.main()
