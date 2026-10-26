import unittest
from tempfile import TemporaryDirectory

from generated.database import Database
from generated.tests.sprint2_helpers import ApiFixture, placement


class OrderRetrievalTests(unittest.TestCase, ApiFixture):
    def setUp(self):
        self.start_api()

    def tearDown(self):
        self.stop_api()

    def test_empty_then_populated_order_list_returns_each_order_once(self):
        self.db.connection.execute("DELETE FROM order_items")
        self.db.connection.execute("DELETE FROM orders")
        self.db.connection.commit()
        self.assertEqual(self.request("GET", "/orders")[2], [])
        _, _, first = self.request("POST", "/orders", placement())
        _, _, second = self.request("POST", "/orders", placement([
            {"product_sku": "WINDOWSILL-JOURNAL", "quantity": 1},
        ]))
        for _ in range(3):
            status, _, orders = self.request("GET", "/orders")
            self.assertEqual(status, 200)
            self.assertEqual([order["order_id"] for order in orders], [first["order_id"], second["order_id"]])

    def test_multiple_line_snapshots_survive_repeated_reads_and_restart(self):
        with TemporaryDirectory() as directory:
            path = directory + "/retrieval.sqlite3"
            db = Database(path)
            order = db.create_order(placement([
                {"product_sku": "REPOTTING-DAY", "quantity": 10},
                {"product_sku": "FIRST-SPROUT", "quantity": 2},
            ]), discount_rates={"REPOTTING-DAY": 1000})
            db.update_product_price("REPOTTING-DAY", "44.00")
            self.assertEqual(db.get_order(order["order_id"]), order)
            db.close()
            reopened = Database(path)
            try:
                self.assertEqual(reopened.get_order(order["order_id"]), order)
                self.assertEqual(reopened.list_orders(), [order])
            finally:
                reopened.close()

    def test_unknown_order_id_remains_not_found(self):
        status, _, payload = self.request("GET", "/orders/987654")
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "Order not found")


if __name__ == "__main__":
    unittest.main()
