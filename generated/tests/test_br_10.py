import unittest
from unittest.mock import patch

from generated.gui import HCCApplication
from generated.tests.test_br_04 import FakeRoot, FakeStatus


class OrderLookupGuiTests(unittest.TestCase):
    def make_app(self):
        frame = type("Frame", (), {"pack": lambda self, **kwargs: None, "pack_forget": lambda self: None})
        app = object.__new__(HCCApplication)
        app._closed = False
        app._refresh_tokens = {"inventory": 0, "orders": 0}
        app.root = FakeRoot()
        app.status = FakeStatus()
        app.base_url = "http://local"
        app.pages = {"Inventory": frame(), "Place Order": frame(), "Orders": frame()}
        app.order_list = type("List", (), {
            "get_children": lambda self: [],
            "delete": lambda self, *_args: None,
            "insert": lambda self, *args, **kwargs: None,
        })()
        return app

    def test_entering_orders_fetches_automatically_each_time(self):
        app = self.make_app()
        fetched = []
        app.refresh_orders = lambda: fetched.append(True)
        with patch.object(HCCApplication, "refresh_orders", lambda instance: fetched.append(True)):
            HCCApplication.show_page(app, "Orders")
            HCCApplication.show_page(app, "Inventory")
            HCCApplication.show_page(app, "Orders")
        self.assertEqual(fetched, [True, True])

    def test_empty_order_response_is_a_valid_successful_refresh(self):
        app = self.make_app()
        applied = []
        app.order_list = type("List", (), {
            "get_children": lambda self: [],
            "delete": lambda self, *_args: None,
            "insert": lambda self, *args, **kwargs: applied.append(kwargs["values"]),
        })()
        with patch.object(HCCApplication, "_submit_task", lambda *args, **kwargs: args[3]([])):
            HCCApplication.refresh_orders(app)
        self.assertEqual(applied, [])
        self.assertEqual(app._refresh_tokens["orders"], 1)

    def test_refresh_failure_is_reported_through_status(self):
        app = self.make_app()
        applied = []
        def task(_kind, operation, callback, token=None):
            app.status.configure(text="Request in progress...")
            app.status.configure(text="Connection failure: offline")
        app._submit_task = task
        HCCApplication.refresh_orders(app)
        self.assertEqual(app.status.values[-1], "Connection failure: offline")


if __name__ == "__main__":
    unittest.main()
