import os
import queue
import threading
import time
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from generated.gui import HCCApplication, _request_json, api_base_url, order_payload


class FakeStatus:
    def __init__(self):
        self.values = []

    def configure(self, **kwargs):
        self.values.append(kwargs["text"])


class FakeRoot:
    def __init__(self):
        self.scheduled = []
        self.destroyed = False

    def after(self, delay, callback):
        self.scheduled.append((delay, callback))

    def destroy(self):
        self.destroyed = True

    def title(self, value):
        self.window_title = value

    def geometry(self, value):
        self.window_geometry = value

    def protocol(self, *_args):
        pass


class FakeWidget:
    instances = []

    def __init__(self, *_args, **kwargs):
        self.options = dict(kwargs)
        self.value = ""
        self.children = []
        self.headings = []
        self.columns = []
        self.__class__.instances.append(self)

    def pack(self, **_kwargs):
        pass

    def grid(self, **_kwargs):
        pass

    def pack_forget(self):
        pass

    def heading(self, *_args, **_kwargs):
        self.headings.append((_args, _kwargs))

    def column(self, *_args, **_kwargs):
        self.columns.append((_args, _kwargs))

    def insert(self, *_args, **kwargs):
        self.value = _args[-1] if len(_args) > 1 else kwargs.get("values", "")
        if "values" in kwargs:
            self.children.append(kwargs["values"])

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def get_children(self):
        return self.children

    def delete(self, *_args):
        self.children.clear()


class FakeBooleanVar:
    def __init__(self, value=False):
        self.value = value

    def get(self):
        return self.value


def make_task_app():
    app = object.__new__(HCCApplication)
    app._closed = False
    app._results = queue.Queue()
    app._refresh_tokens = {"inventory": 1, "orders": 1}
    app.status = FakeStatus()
    app.root = FakeRoot()
    return app


class DesktopGuiTests(unittest.TestCase):
    def test_api_url_uses_environment_or_default(self):
        with patch.dict(os.environ, {"HCC_API_URL": "http://localhost:8123"}):
            self.assertEqual(api_base_url(), "http://localhost:8123")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(api_base_url(), "http://127.0.0.1:8000")

    def test_order_submission_is_one_line_and_preserves_checkbox(self):
        self.assertEqual(order_payload("Ada", "FIRST-SPROUT", "2", True), {
            "customer_name": "Ada", "items": [{"product_sku": "FIRST-SPROUT", "quantity": 2}], "shipped": True,
        })

    def test_quantity_is_converted_to_integer(self):
        self.assertEqual(order_payload("Ada", "FIRST-SPROUT", "1", False)["items"][0]["quantity"], 1)

    def test_warning_text_is_constant(self):
        from generated.gui import WARNING_TEXT
        self.assertEqual(WARNING_TEXT, "UNSECURED API  |  Use only with a trusted local endpoint")

    def test_worker_hands_results_to_ui_thread_and_shows_progress(self):
        app = make_task_app()
        called = []
        HCCApplication._submit_task(app, "inventory", lambda: "data", called.append, 1)
        self.assertEqual(app.status.values[-1], "Request in progress...")
        deadline = time.monotonic() + 2
        while app._results.empty() and time.monotonic() < deadline:
            time.sleep(0.005)
        HCCApplication._drain_results(app)
        self.assertEqual(called, ["data"])
        self.assertEqual(app.status.values[-1], "Ready")
        self.assertTrue(app.root.scheduled)

    def test_out_of_order_refresh_result_is_ignored(self):
        app = make_task_app()
        called = []
        app._refresh_tokens["inventory"] = 2
        app._results.put(("inventory", 1, called.append, "stale", None))
        HCCApplication._drain_results(app)
        self.assertEqual(called, [])

    def test_closing_during_request_prevents_result_callback(self):
        app = make_task_app()
        started = threading.Event()
        finish = threading.Event()
        called = []

        def operation():
            started.set()
            finish.wait(2)
            return "late"

        HCCApplication._submit_task(app, "submit", operation, called.append)
        self.assertTrue(started.wait(1))
        HCCApplication.close(app)
        finish.set()
        deadline = time.monotonic() + 2
        while app._results.empty() and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(app.root.destroyed)
        self.assertEqual(called, [])
        self.assertEqual(app.root.scheduled, [])

    def test_api_errors_use_error_text_or_connection_message(self):
        response = HTTPError("http://local", 409, "conflict", {}, None)
        response.read = lambda: b'{"error":"Out of stock"}'
        with patch("generated.gui.urllib.request.urlopen", side_effect=response):
            with self.assertRaisesRegex(RuntimeError, "Out of stock"):
                _request_json("http://local")
        response = HTTPError("http://local", 503, "unavailable", {}, None)
        response.read = lambda: b'{"error":" "}'
        with patch("generated.gui.urllib.request.urlopen", side_effect=response):
            with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
                _request_json("http://local")
        with patch("generated.gui.urllib.request.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(RuntimeError, "Connection failure"):
                _request_json("http://local")

    def test_window_navigation_warning_and_form_controls(self):
        FakeWidget.instances.clear()
        with ExitStack() as stack:
            stack.enter_context(patch("generated.gui.tk.Tk", FakeRoot))
            stack.enter_context(patch("generated.gui.tk.Label", FakeWidget))
            stack.enter_context(patch("generated.gui.tk.BooleanVar", FakeBooleanVar))
            for name in ("Frame", "Label", "Button", "Treeview", "Entry", "Combobox", "Checkbutton"):
                stack.enter_context(patch(f"generated.gui.ttk.{name}", FakeWidget))
            stack.enter_context(patch("generated.gui._request_json", return_value=[]))
            app = HCCApplication(base_url="http://local")
            try:
                self.assertEqual(app.root.window_title, "Houseplant Correspondence Company")
                self.assertEqual(app.root.window_geometry, "760x520")
                texts = [widget.options.get("text") for widget in FakeWidget.instances]
                self.assertIn("View:", texts)
                for label in ("Inventory", "Place Order", "Orders", "Submit order", "Refresh orders"):
                    self.assertIn(label, texts)
                for label in ("Full name", "Street number and name", "Phone number", "Product SKU", "Quantity", "Shipped"):
                    self.assertIn(label, texts)
                self.assertNotIn("Refresh inventory", texts)
                warning = next(widget for widget in FakeWidget.instances if widget.options.get("text") == "UNSECURED API  |  Use only with a trusted local endpoint")
                self.assertEqual(warning.options.get("foreground"), "red")
                self.assertIn(("TkDefaultFont", 16, "bold"), [
                    widget.options.get("font") for widget in FakeWidget.instances
                ])
                self.assertEqual(app.quantity_entry.get(), "1")
                self.assertEqual(app.shipped_var.get(), False)
                self.assertEqual(app.product_choice.options["state"], "readonly")
                self.assertEqual(app.status.options["text"], "Ready")
                self.assertEqual(
                    [heading[1]["text"] for heading in app.inventory.headings],
                    ["SKU", "Product name", "Unit price", "Stock quantity"],
                )
                product = {"sku": "FIRST-SPROUT", "name": "First Sprout Card Pack", "unit_price": "12.50", "stock_quantity": 100}
                with patch("generated.gui._request_json", return_value=[product]):
                    app.refresh_inventory()
                    deadline = time.monotonic() + 2
                    while app._results.empty() and time.monotonic() < deadline:
                        time.sleep(0.005)
                    HCCApplication._drain_results(app)
                self.assertEqual(app.inventory.children, [("FIRST-SPROUT", "First Sprout Card Pack", "12.50", 100)])
                self.assertEqual(app.product_choice.options["values"], ["First Sprout Card Pack (FIRST-SPROUT)"])
                order = {"order_id": 1, "customer_name": "Ada", "status": "pending", "total": "12.50"}
                with patch("generated.gui._request_json", return_value=[order]):
                    app.refresh_orders()
                    deadline = time.monotonic() + 2
                    while app._results.empty() and time.monotonic() < deadline:
                        time.sleep(0.005)
                    HCCApplication._drain_results(app)
                self.assertEqual(app.order_list.children, [(1, "Ada", "pending", "12.50")])
                refresh_calls = []
                app.refresh_inventory = lambda: refresh_calls.append("inventory")
                app.refresh_orders = lambda: refresh_calls.append("orders")
                next(w for w in FakeWidget.instances if w.options.get("text") == "Inventory" and "command" in w.options).options["command"]()
                next(w for w in FakeWidget.instances if w.options.get("text") == "Orders" and "command" in w.options).options["command"]()
                self.assertEqual(refresh_calls, ["inventory", "orders"])
            finally:
                app.close()

    def test_repeated_submit_activations_create_separate_requests(self):
        app = object.__new__(HCCApplication)
        app.base_url = "http://local"
        app.customer_entry = SimpleNamespace(get=lambda: "Ada")
        app.product_choice = SimpleNamespace(get=lambda: "FIRST-SPROUT")
        app.quantity_entry = SimpleNamespace(get=lambda: "1")
        app.shipped_var = SimpleNamespace(get=lambda: False)
        app._product_skus = {"FIRST-SPROUT": "FIRST-SPROUT"}
        app.customer_fields = {
            "full_name": SimpleNamespace(get=lambda: "Ada"),
            "street_address": SimpleNamespace(get=lambda: "12 Main"),
            "city": SimpleNamespace(get=lambda: "Town"),
            "state": SimpleNamespace(get=lambda: "CA"),
            "postal_code": SimpleNamespace(get=lambda: "00123"),
            "country": SimpleNamespace(get=lambda: "US"),
            "phone_country_code": SimpleNamespace(get=lambda: "+1"),
            "phone_number": SimpleNamespace(get=lambda: "555-0100"),
        }
        app.status = FakeStatus()
        tasks = []
        sent = []

        def record(_self, kind, operation, callback, token=None):
            tasks.append((kind, operation, callback, token))

        with patch.object(HCCApplication, "_submit_task", record), patch(
            "generated.gui._request_json", side_effect=lambda *args: sent.append(args) or {}
        ):
            HCCApplication.submit_order(app)
            HCCApplication.submit_order(app)
            self.assertEqual(len(tasks), 2)
            for _, operation, _, _ in tasks:
                operation()
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0][2], {
            "customer": {
                "full_name": "Ada",
                "street_address": "12 Main",
                "city": "Town",
                "state": "CA",
                "postal_code": "00123",
                "country": "US",
                "phone_country_code": "+1",
                "phone_number": "555-0100",
            },
            "items": [{"product_sku": "FIRST-SPROUT", "quantity": 1}],
            "shipped": False,
        })


if __name__ == "__main__":
    unittest.main()
