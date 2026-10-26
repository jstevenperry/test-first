import queue
import unittest
from unittest.mock import patch

from generated.gui import HCCApplication
from generated.tests.test_br_04 import FakeBooleanVar, FakeRoot, FakeStatus, FakeWidget


class NavigationAndCatalogRefreshTests(unittest.TestCase):
    def setUp(self):
        FakeWidget.instances.clear()

    def create_app(self):
        app = object.__new__(HCCApplication)
        app._closed = False
        app._results = queue.Queue()
        app._refresh_tokens = {"inventory": 0, "orders": 0, "customers": 0}
        app._product_skus = {}
        app.root = FakeRoot()
        app.status = FakeStatus()
        app.pages = {name: FakeWidget() for name in ("Inventory", "Place Order", "Orders", "Customers")}
        app.base_url = "http://local"
        app.inventory = FakeWidget()
        app.order_list = FakeWidget()
        app.product_choice = FakeWidget()
        app.customer_fields = {}
        app.customer_entry = FakeWidget()
        app.quantity_entry = FakeWidget()
        app.shipped_var = FakeBooleanVar(False)
        return app

    def test_each_inventory_entry_requests_catalog_and_preserves_other_pages(self):
        app = self.create_app()
        calls = []
        app.refresh_inventory = lambda: calls.append("inventory")
        app.refresh_orders = lambda: calls.append("orders")
        for name in ("Inventory", "Place Order", "Orders", "Inventory"):
            HCCApplication.show_page(app, name)
        self.assertEqual(calls, ["inventory", "orders", "inventory"])
        self.assertTrue(all(hasattr(frame, "pack_forget") for frame in app.pages.values()))

    def test_order_success_refreshes_catalog(self):
        app = self.create_app()
        app.customer_fields = {}
        app._product_skus = {"Plant (SKU)": "SKU"}
        app.product_choice = FakeWidget()
        app.product_choice.set("Plant (SKU)")
        app.customer_entry = FakeWidget()
        app.customer_entry.value = "Ada"
        app.quantity_entry = FakeWidget()
        app.quantity_entry.value = "1"
        refreshes = []
        app.refresh_inventory = lambda: refreshes.append(True)
        app._submit_task = lambda _kind, _operation, callback, token=None: callback({})
        HCCApplication.submit_order(app)
        self.assertEqual(refreshes, [True])

    def test_manual_orders_refresh_and_no_inventory_refresh_button(self):
        with patch("generated.gui.tk.Tk", FakeRoot), \
             patch("generated.gui.tk.Label", FakeWidget), \
             patch("generated.gui.tk.BooleanVar", FakeBooleanVar), \
             patch("generated.gui.ttk.Frame", FakeWidget), \
             patch("generated.gui.ttk.Label", FakeWidget), \
             patch("generated.gui.ttk.Button", FakeWidget), \
             patch("generated.gui.ttk.Treeview", FakeWidget), \
             patch("generated.gui.ttk.Entry", FakeWidget), \
             patch("generated.gui.ttk.Combobox", FakeWidget), \
             patch("generated.gui.ttk.Checkbutton", FakeWidget), \
             patch("generated.gui._request_json", return_value=[]):
            app = HCCApplication()
        try:
            navigation = [widget.options.get("text") for widget in FakeWidget.instances]
            self.assertEqual(navigation.count("View:"), 1)
            navigation_index = navigation.index("View:")
            self.assertEqual(navigation[navigation_index:navigation_index + 5], [
                "View:", "Inventory", "Place Order", "Orders", "Customers",
            ])
            self.assertNotIn("Refresh inventory", navigation)
            self.assertIn("Refresh orders", navigation)
            self.assertIn("Customers", navigation)
            self.assertIn("Create Customer", navigation)
            for field_label in (
                "Full name", "Street number and name", "City", "State",
                "Postal code", "Country", "Phone country code", "Phone number",
            ):
                self.assertGreaterEqual(navigation.count(field_label), 2)
            app.close()
        finally:
            if not app._closed:
                app.close()

    def test_stale_catalog_response_cannot_replace_latest_inventory_and_dropdown(self):
        app = self.create_app()
        applied = []
        app._refresh_tokens["inventory"] = 2
        app._results.put(("inventory", 1, applied.append, [{"sku": "OLD"}], None))
        app._results.put(("inventory", 2, applied.append, [{"sku": "NEW"}], None))
        with patch.object(HCCApplication, "_drain_results", wraps=HCCApplication._drain_results):
            # Exercise token filtering directly with a callback that records its payload.
            original_after = app.root.after
            app.root.after = lambda *_args: None
            HCCApplication._drain_results(app)
            app.root.after = original_after
        self.assertEqual(applied, [[{"sku": "NEW"}]])


if __name__ == "__main__":
    unittest.main()
