import unittest
from unittest.mock import patch

from generated.gui import HCCApplication, order_payload
from generated.tests.test_br_04 import FakeRoot, FakeStatus
from generated.tests.sprint2_helpers import ApiFixture


class ProductDropdownTests(unittest.TestCase):
    def make_app(self):
        app = object.__new__(HCCApplication)
        app._closed = False
        app._refresh_tokens = {"inventory": 0, "orders": 0}
        app.root = FakeRoot()
        app.status = FakeStatus()
        app.base_url = "http://local"
        app.inventory = type("Table", (), {
            "get_children": lambda self: [],
            "delete": lambda self, *_args: None,
            "insert": lambda self, *_args, **kwargs: None,
        })()
        app.product_choice = type("Choice", (), {
            "value": "",
            "values": (),
            "get": lambda self: self.value,
            "set": lambda self, value: setattr(self, "value", value),
            "configure": lambda self, **kwargs: setattr(self, "values", kwargs["values"]),
        })()
        app._product_skus = {}
        app.customer_entry = type("Entry", (), {"get": lambda self: "Ada"})()
        app.quantity_entry = type("Entry", (), {"get": lambda self: "1"})()
        app.shipped_var = type("Variable", (), {"get": lambda self: False})()
        return app

    def test_dropdown_starts_without_selection_and_empty_catalog_stays_unselected(self):
        app = self.make_app()
        applied = []
        def submit(_kind, operation, callback, token=None):
            callback([])
        app._submit_task = submit
        HCCApplication.refresh_inventory(app)
        self.assertEqual(app.product_choice.get(), "")
        self.assertEqual(app.product_choice.values, [])

    def test_dropdown_choices_show_products_and_submit_exact_sku(self):
        app = self.make_app()
        product = {"sku": "FIRST-SPROUT", "name": "First Sprout Card Pack", "unit_price": "12.50", "stock_quantity": 5}
        app._submit_task = lambda _kind, operation, callback, token=None: callback([product])
        HCCApplication.refresh_inventory(app)
        self.assertEqual(app.product_choice.values, ["First Sprout Card Pack (FIRST-SPROUT)"])
        app.product_choice.set("First Sprout Card Pack (FIRST-SPROUT)")
        self.assertEqual(app._product_skus[app.product_choice.get()], "FIRST-SPROUT")

    def test_empty_selection_is_not_submitted(self):
        app = self.make_app()
        app.product_choice.set("")
        submitted = []
        app._submit_task = lambda *args, **kwargs: submitted.append(args)
        HCCApplication.submit_order(app)
        self.assertEqual(submitted, [])
        self.assertIn("product", app.status.values[-1].lower())

    def test_selection_posts_exact_sku_not_display_name(self):
        app = self.make_app()
        app._product_skus = {"First Sprout Card Pack (FIRST-SPROUT)": "FIRST-SPROUT"}
        app.product_choice.set("First Sprout Card Pack (FIRST-SPROUT)")
        requests = []
        app._submit_task = lambda _kind, operation, _callback, token=None: operation()
        with patch("generated.gui._request_json", side_effect=lambda *args: requests.append(args) or {}):
            HCCApplication.submit_order(app)
        self.assertEqual(requests[0][2]["items"][0]["product_sku"], "FIRST-SPROUT")

    def test_inventory_refresh_failure_surfaces_status(self):
        app = self.make_app()
        app._submit_task = lambda _kind, operation, callback, token=None: app.status.configure(text="API unavailable")
        HCCApplication.refresh_inventory(app)
        self.assertEqual(app.status.values[-1], "API unavailable")

    def test_zero_stock_choice_still_uses_order_api(self):
        payload = order_payload("Ada", "ZERO", "1", False)
        self.assertEqual(payload["items"][0]["product_sku"], "ZERO")
        self.assertEqual(payload["items"][0]["quantity"], 1)


class ZeroStockDropdownApiTests(unittest.TestCase, ApiFixture):
    def setUp(self):
        self.start_api()
        self.db.add_product("ZERO", "Zero stock plant", "1.00", 0)

    def tearDown(self):
        self.stop_api()

    def test_selecting_zero_stock_product_is_rejected_by_api(self):
        payload = order_payload("Ada", "ZERO", "1", False)
        status, _, error = self.request("POST", "/orders", payload)
        self.assertEqual(status, 409)
        self.assertIn("error", error)
        self.assertEqual(self.db.list_orders(), [])


if __name__ == "__main__":
    unittest.main()
