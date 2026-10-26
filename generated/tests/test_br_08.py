import unittest
from tempfile import TemporaryDirectory

from generated.database import Database
from generated.tests.sprint2_helpers import ApiFixture, placement


class ShippingStatusTests(unittest.TestCase, ApiFixture):
    def setUp(self):
        self.start_api()

    def tearDown(self):
        self.stop_api()

    def place_order(self, shipped=None):
        request = placement()
        if shipped is not None:
            request["shipped"] = shipped
        status, _, order = self.request("POST", "/orders", request)
        self.assertEqual(status, 201)
        return order

    def set_payment(self, order_id, paid_cents):
        with self.db.connection:
            row = self.db.connection.execute(
                "SELECT total_cents FROM orders WHERE order_id=?", (order_id,)
            ).fetchone()
            self.db.connection.execute(
                "UPDATE orders SET amount_paid_cents=?, payment_status=? WHERE order_id=?",
                (paid_cents, "paid" if paid_cents == row["total_cents"] else ("partial" if paid_cents else "unpaid"), order_id),
            )

    def test_creation_shipped_flag_does_not_ship_order(self):
        order = self.place_order(True)
        self.assertEqual(order["status"], "pending")
        status, _, result = self.request("POST", f"/orders/{order['order_id']}/ship", {})
        self.assertEqual(status, 409)
        self.assertIn("fully paid", result["error"])

    def test_unpaid_and_partial_orders_cannot_ship_and_can_retry_after_payment(self):
        order = self.place_order()
        before = self.db.get_order(order["order_id"])
        status, _, _ = self.request("POST", f"/orders/{order['order_id']}/ship", {})
        self.assertEqual(status, 409)
        self.assertEqual(self.db.get_order(order["order_id"]), before)
        self.set_payment(order["order_id"], 1)
        partial = self.db.get_order(order["order_id"])
        status, _, _ = self.request("POST", f"/orders/{order['order_id']}/ship", {})
        self.assertEqual(status, 409)
        self.assertEqual(self.db.get_order(order["order_id"]), partial)
        self.set_payment(order["order_id"], 1250)
        status, _, shipped = self.request("POST", f"/orders/{order['order_id']}/ship", {})
        self.assertEqual(status, 200)
        self.assertEqual(shipped["status"], "shipped")
        self.assertEqual(self.request("GET", f"/orders/{order['order_id']}")[2], shipped)

    def test_missing_and_already_shipped_orders_return_exact_404(self):
        status, _, payload = self.request("POST", "/orders/999/ship", {})
        self.assertEqual((status, payload), (404, {"error": "Pending order not found"}))
        order = self.place_order()
        self.set_payment(order["order_id"], 1250)
        self.assertEqual(self.request("POST", f"/orders/{order['order_id']}/ship", {})[0], 200)
        status, _, payload = self.request("POST", f"/orders/{order['order_id']}/ship", {})
        self.assertEqual((status, payload), (404, {"error": "Pending order not found"}))

    def test_cancelled_or_other_non_pending_order_cannot_ship(self):
        order = self.place_order()
        with self.db.connection:
            self.db.connection.execute("UPDATE orders SET status='cancelled' WHERE order_id=?", (order["order_id"],))
        before = self.db.get_order(order["order_id"])
        status, _, payload = self.request("POST", f"/orders/{order['order_id']}/ship", {})
        self.assertEqual(status, 409)
        self.assertIn("error", payload)
        self.assertEqual(self.db.get_order(order["order_id"]), before)

    def test_shipped_state_persists_after_database_restart(self):
        with TemporaryDirectory() as directory:
            path = directory + "/shipping.sqlite3"
            db = Database(path)
            order = db.create_order(placement())
            with db.connection:
                db.connection.execute("UPDATE orders SET amount_paid_cents=total_cents,payment_status='paid' WHERE order_id=?", (order["order_id"],))
            shipped = db.ship_order(order["order_id"])
            db.close()
            reopened = Database(path)
            try:
                self.assertEqual(reopened.get_order(order["order_id"]), shipped)
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
