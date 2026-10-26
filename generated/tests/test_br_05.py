import unittest

from generated.database import Database


class OrderPlacementValidationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def placement(self, **overrides):
        value = {"customer_name": "Customer", "items": [{"product_sku": "FIRST-SPROUT", "quantity": 1}]}
        value.update(overrides)
        return value

    def assert_rejected_atomically(self, request, message=None):
        stock = self.db.get_product("FIRST-SPROUT")["stock_quantity"]
        orders = len(self.db.list_orders())
        with self.assertRaises(ValueError) as error:
            self.db.create_order(request)
        if message:
            self.assertEqual(str(error.exception), message)
        self.assertEqual(self.db.get_product("FIRST-SPROUT")["stock_quantity"], stock)
        self.assertEqual(len(self.db.list_orders()), orders)

    def test_blank_customer_and_sku(self):
        self.assert_rejected_atomically(self.placement(customer_name=" "))
        self.assert_rejected_atomically(self.placement(items=[{"product_sku": " ", "quantity": 1}]))

    def test_missing_fields_and_malformed_items(self):
        for request in ({}, {"customer_name": "X"}, {"customer_name": "X", "items": []},
                        self.placement(items="bad"), self.placement(items=[None]),
                        self.placement(items=[{"product_sku": "FIRST-SPROUT"}])):
            self.assert_rejected_atomically(request)

    def test_zero_and_negative_quantity_error_is_exact(self):
        for quantity in (0, -1, -0.5):
            self.assert_rejected_atomically(self.placement(items=[{"product_sku": "FIRST-SPROUT", "quantity": quantity}]), "quantity must be positive")

    def test_positive_fraction_boolean_and_non_numeric_are_invalid(self):
        for quantity in (1.5, True, "one"):
            self.assert_rejected_atomically(self.placement(items=[{"product_sku": "FIRST-SPROUT", "quantity": quantity}]))

    def test_quantity_one_is_accepted(self):
        order = self.db.create_order(self.placement())
        self.assertEqual(order["items"][0]["quantity"], 1)
        self.assertEqual(order["status"], "pending")

    def test_shipped_omitted_creates_pending_order(self):
        order = self.db.create_order(self.placement())
        self.assertEqual(order["status"], "pending")

    def test_shipped_must_be_boolean_and_never_changes_initial_status(self):
        for shipped in (True, False):
            order = self.db.create_order(self.placement(shipped=shipped))
            self.assertEqual(order["status"], "pending")
        self.assert_rejected_atomically(self.placement(shipped="yes"))

    def test_invalid_later_line_rejects_entire_order(self):
        self.assert_rejected_atomically(self.placement(items=[
            {"product_sku": "FIRST-SPROUT", "quantity": 1},
            {"product_sku": "REPOTTING-DAY", "quantity": 1.5},
        ]))


if __name__ == "__main__":
    unittest.main()
