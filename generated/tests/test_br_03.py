import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import unittest
from http.client import HTTPConnection
from io import StringIO
from urllib.parse import quote
from unittest.mock import patch
from contextlib import redirect_stdout

from generated.api import make_server
from generated.database import Database


class RestInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database(":memory:")
        cls.server = make_server("127.0.0.1", 0, cls.db)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.db.close()

    def request(self, method, path, body=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = None if body is None else json.dumps(body)
        conn.request(method, path, payload, {"Content-Type": "application/json"})
        response = conn.getresponse()
        data = response.read()
        headers = dict(response.getheaders())
        conn.close()
        return response.status, headers, json.loads(data) if data else None

    def request_raw(self, method, path, payload):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request(method, path, payload, {"Content-Type": "application/json"})
        response = conn.getresponse()
        data = response.read()
        result = response.status, json.loads(data) if data else None
        conn.close()
        return result

    def order(self, sku="FIRST-SPROUT", quantity=1, **extra):
        return {"customer_name": "Test Customer", "items": [{"product_sku": sku, "quantity": quantity}], **extra}

    def test_get_product_list_and_single_product(self):
        status, _, products = self.request("GET", "/products")
        self.assertEqual(status, 200)
        self.assertEqual(len(products), 3)
        self.assertEqual(set(products[0]), {"sku", "name", "unit_price", "stock_quantity"})
        status, _, product = self.request("GET", "/products/FIRST-SPROUT")
        self.assertEqual((status, product["sku"]), (200, "FIRST-SPROUT"))

    def test_get_unknown_product_is_json_404(self):
        status, _, payload = self.request("GET", "/products/UNKNOWN")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    def test_percent_encoded_sku_is_decoded(self):
        self.db.add_product("WITH SPACE", "Encoded SKU", "1.00", 3)
        status, _, payload = self.request("GET", "/products/" + quote("WITH SPACE", safe=""))
        self.assertEqual((status, payload["sku"]), (200, "WITH SPACE"))

    def test_create_order_complete_shape_and_serialization(self):
        status, _, order = self.request("POST", "/orders", self.order())
        self.assertEqual(status, 201)
        self.assertEqual(set(order), {"order_id", "customer_name", "status", "created_at", "subtotal", "tax_rate", "tax_amount", "shipping_charge", "total", "amount_paid", "amount_refunded", "payment_status", "items"})
        self.assertIsInstance(order["order_id"], int)
        self.assertTrue(order["created_at"].endswith("Z"))
        for key in ("subtotal", "tax_amount", "shipping_charge", "total", "amount_paid", "amount_refunded"):
            self.assertRegex(order[key], r"^\d+\.\d{2}$")
        self.assertEqual(order["tax_rate"], "0.00")
        self.assertEqual(order["items"][0]["discount_rate"], "0.00")
        self.assertEqual(order["subtotal"], "12.50")
        self.assertEqual(order["tax_amount"], "0.00")
        self.assertEqual(order["shipping_charge"], "0.00")
        self.assertEqual(order["total"], "12.50")
        self.assertEqual(order["amount_paid"], "0.00")
        self.assertEqual(order["amount_refunded"], "0.00")
        self.assertEqual(order["items"][0]["unit_price"], "12.50")
        self.assertEqual(order["items"][0]["tax_amount"], "0.00")
        self.assertEqual(set(order["items"][0]), {"product_sku", "quantity", "unit_price", "discount_rate", "tax_amount", "returned_quantity"})

    def test_ten_ten_cent_products_total_exactly_one_dollar_through_api(self):
        self.db.add_product("DIME", "Ten cent product", "0.10", 10)
        status, _, order = self.request("POST", "/orders", self.order("DIME", quantity=10))
        self.assertEqual(status, 201)
        self.assertEqual((order["subtotal"], order["total"]), ("1.00", "1.00"))

    def test_orders_list_is_ascending_and_get_by_id_matches(self):
        _, _, first = self.request("POST", "/orders", self.order())
        _, _, second = self.request("POST", "/orders", self.order("REPOTTING-DAY"))
        status, _, orders = self.request("GET", "/orders")
        self.assertEqual(status, 200)
        ids = [x["order_id"] for x in orders]
        self.assertEqual(ids, sorted(ids))
        self.assertIn(first["order_id"], ids)
        self.assertIn(second["order_id"], ids)
        status, _, fetched = self.request("GET", f"/orders/{first['order_id']}")
        self.assertEqual((status, fetched), (200, first))

    def test_invalid_and_unknown_order_ids(self):
        self.assertEqual(self.request("GET", "/orders/nope")[0], 400)
        status, _, body = self.request("GET", "/orders/999999")
        self.assertEqual(status, 404)
        self.assertIn("error", body)

    def test_order_has_pending_unpaid_default_even_with_shipped(self):
        for shipped in (None, True, False):
            body = self.order()
            if shipped is not None:
                body["shipped"] = shipped
            status, _, result = self.request("POST", "/orders", body)
            self.assertEqual(status, 201)
            self.assertEqual((result["status"], result["payment_status"]), ("pending", "unpaid"))

    def test_invalid_payloads_return_json_400(self):
        for body in (None, {}, {"customer_name": "X", "items": []}, {"customer_name": "X", "items": [{"product_sku": "X"}]}, self.order(shipped="yes")):
            status, _, payload = self.request("POST", "/orders", body)
            self.assertEqual(status, 400)
            self.assertIn("error", payload)
            status, payload = self.request_raw("POST", "/orders", "{malformed")
            self.assertEqual(status, 400)
            self.assertIn("error", payload)
            for quantity in (0, -1, -0.5):
                status, _, payload = self.request("POST", "/orders", self.order(quantity=quantity))
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"], "quantity must be positive")
        status, _, payload = self.request("POST", "/orders", [])
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_price_changes_do_not_change_order_snapshot(self):
        status, _, order = self.request("POST", "/orders", self.order(quantity=2))
        self.assertEqual(status, 201)
        self.db.update_product_price("FIRST-SPROUT", "99.99")
        status, _, retrieved = self.request("GET", f"/orders/{order['order_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(retrieved["items"][0]["unit_price"], "12.50")
        self.assertEqual(retrieved["subtotal"], "25.00")
        self.db.update_product_price("FIRST-SPROUT", "12.50")

    def test_orders_persist_across_database_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/orders.sqlite3"
            db = Database(path)
            order = db.create_order(self.order(quantity=2))
            db.close()
            reopened = Database(path)
            try:
                self.assertEqual(reopened.get_order(order["order_id"]), order)
                self.assertEqual(reopened.get_product("FIRST-SPROUT")["stock_quantity"], 98)
            finally:
                reopened.close()

    def test_unknown_sku_and_insufficient_stock_fail_without_changes(self):
        before = self.db.get_product("FIRST-SPROUT")["stock_quantity"]
        status, _, _ = self.request("POST", "/orders", self.order("UNKNOWN"))
        self.assertEqual(status, 404)
        status, _, _ = self.request("POST", "/orders", self.order(quantity=10000))
        self.assertEqual(status, 409)
        self.assertEqual(self.db.get_product("FIRST-SPROUT")["stock_quantity"], before)

    def test_failure_on_later_line_is_atomic(self):
        before = self.db.get_product("FIRST-SPROUT")["stock_quantity"]
        count_before = len(self.db.list_orders())
        body = {"customer_name": "Customer", "items": [{"product_sku": "FIRST-SPROUT", "quantity": 1}, {"product_sku": "UNKNOWN", "quantity": 1}]}
        self.assertEqual(self.request("POST", "/orders", body)[0], 404)
        self.assertEqual(self.db.get_product("FIRST-SPROUT")["stock_quantity"], before)
        self.assertEqual(len(self.db.list_orders()), count_before)

    def test_duplicate_lines_combine_preserving_first_position(self):
        body = {"customer_name": "Customer", "items": [{"product_sku": "REPOTTING-DAY", "quantity": 1}, {"product_sku": "FIRST-SPROUT", "quantity": 1}, {"product_sku": "REPOTTING-DAY", "quantity": 2}]}
        status, _, result = self.request("POST", "/orders", body)
        self.assertEqual(status, 201)
        self.assertEqual([(i["product_sku"], i["quantity"]) for i in result["items"]], [("REPOTTING-DAY", 3), ("FIRST-SPROUT", 1)])

    def test_duplicate_combined_quantity_over_stock_is_atomic(self):
        before = self.db.get_product("FIRST-SPROUT")["stock_quantity"]
        count_before = len(self.db.list_orders())
        request = {"customer_name": "Customer", "items": [
            {"product_sku": "FIRST-SPROUT", "quantity": before},
            {"product_sku": "FIRST-SPROUT", "quantity": 1},
        ]}
        self.assertEqual(self.request("POST", "/orders", request)[0], 409)
        self.assertEqual(self.db.get_product("FIRST-SPROUT")["stock_quantity"], before)
        self.assertEqual(len(self.db.list_orders()), count_before)

    def test_nonzero_rates_and_order_level_snapshots(self):
        self.db.add_product("NICKEL", "Five cent item", "0.05", 2)
        order = self.db.create_order(
            {"customer_name": "Fixture", "items": [{"product_sku": "NICKEL", "quantity": 1}]},
            tax_rate_bps=1000,
            discount_rates={"NICKEL": 1000},
        )
        self.assertEqual(order["subtotal"], "0.04")
        self.assertEqual(order["tax_amount"], "0.00")
        fixture = self.db.create_order(
            {"customer_name": "Fixture", "items": [{"product_sku": "NICKEL", "quantity": 1}]},
            tax_rate_bps=1000,
        )
        self.assertEqual(fixture["tax_amount"], "0.01")

    def test_request_logging_and_internal_error_redaction(self):
        logger = logging.getLogger("hcc.api")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        old_level = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            self.request("GET", "/products")
            self.assertIn("GET /products", stream.getvalue())
            with patch.object(self.db, "list_products", side_effect=RuntimeError("secret detail")):
                status, _, payload = self.request("GET", "/products")
            self.assertEqual(status, 500)
            self.assertEqual(payload, {"error": "Internal server error"})
            self.assertIn("secret detail", stream.getvalue())
            self.assertNotIn("secret detail", json.dumps(payload))
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)

    def test_unknown_route_and_known_route_wrong_method(self):
        self.assertEqual(self.request("GET", "/orders/")[0], 404)
        status, headers, body = self.request("PUT", "/products")
        self.assertEqual(status, 405)
        self.assertIn("Allow", headers)
        self.assertIn("error", body)

    def test_head_or_options_is_not_an_unhandled_server_error(self):
        for method in ("HEAD", "OPTIONS"):
            status, _, _ = self.request(method, "/products")
            self.assertIn(status, (200, 405))

    def test_default_bind_address_is_loopback(self):
        server = make_server(port=0, database=Database(":memory:"))
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
        finally:
            server.database.close()
            server.server_close()

    def test_startup_message_reports_actual_port(self):
        class FakeServer:
            server_address = ("127.0.0.1", 12345)
            database = type("FakeDatabase", (), {"close": lambda self: None})()

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                pass

        output = StringIO()
        with patch("generated.api.make_server", return_value=FakeServer()), redirect_stdout(output):
            from generated.api import main
            main()
        self.assertIn("http://127.0.0.1:12345", output.getvalue())

    def test_api_module_runs_as_a_python_script(self):
        script = Path(__file__).resolve().parents[1] / "api.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, HCC_API_PORT="0")
            with self.assertRaises(subprocess.TimeoutExpired) as timeout:
                subprocess.run(
                    [sys.executable, str(script)],
                    cwd=directory,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
            output = timeout.exception.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            self.assertIn("HCC API listening at http://127.0.0.1:", output)


if __name__ == "__main__":
    unittest.main()
