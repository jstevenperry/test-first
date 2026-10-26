import unittest

from generated.tests.sprint2_helpers import ApiFixture, placement


class ProductLookupTests(unittest.TestCase, ApiFixture):
    def setUp(self):
        self.start_api()

    def tearDown(self):
        self.stop_api()

    def test_unknown_product_lookup_uses_exact_json_error(self):
        status, _, body = self.request("GET", "/products/UNKNOWN")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "Unknown product"})

    def test_unknown_product_placement_has_same_error_and_no_changes(self):
        before_stock = self.db.get_product("FIRST-SPROUT")["stock_quantity"]
        before_orders = self.db.list_orders()
        status, _, body = self.request("POST", "/orders", placement([
            {"product_sku": "FIRST-SPROUT", "quantity": 1},
            {"product_sku": "UNKNOWN", "quantity": 1},
        ]))
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "Unknown product"})
        self.assertEqual(self.db.get_product("FIRST-SPROUT")["stock_quantity"], before_stock)
        self.assertEqual(self.db.list_orders(), before_orders)


if __name__ == "__main__":
    unittest.main()
