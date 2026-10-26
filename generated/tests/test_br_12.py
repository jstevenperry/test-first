import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from generated.database import Database
from generated.gui import HCCApplication, order_payload
from generated.tests.sprint2_helpers import ApiFixture, placement
from generated.tests.test_br_04 import FakeStatus


CUSTOMER = {
    "full_name": "  Zoë O'Neil  ",
    "street_address": "  12 Rue de l'Église  ",
    "city": "  Montréal  ",
    "state": " QC ",
    "postal_code": " A1B 2C3 ",
    "country": " Canada ",
    "phone_country_code": " +1 ",
    "phone_number": " (555) 123-4567 ",
}


class CustomerManagementTests(unittest.TestCase, ApiFixture):
    def setUp(self):
        self.start_api()

    def tearDown(self):
        self.stop_api()

    def test_standalone_customer_is_persisted_but_not_purchased(self):
        status, _, customer = self.request("POST", "/customers", CUSTOMER)
        self.assertEqual(status, 201)
        self.assertEqual(customer["full_name"], "Zoë O'Neil")
        self.assertEqual(customer["street_address"], "12 Rue de l'Église")
        self.assertEqual(customer["postal_code"], "A1B 2C3")
        self.assertEqual(customer["phone_country_code"], "+1")
        self.assertEqual(customer["phone_number"], "(555) 123-4567")
        status, _, purchased = self.request("GET", "/customers/purchased")
        self.assertEqual((status, purchased), (200, []))
        status, _, saved = self.request("GET", "/customers")
        self.assertEqual(status, 200)
        self.assertEqual(saved, [customer])

    def test_all_required_fields_reject_missing_null_empty_whitespace_and_non_string(self):
        fields = (
            "full_name", "street_address", "city", "state", "postal_code",
            "country", "phone_country_code", "phone_number",
        )
        for field in fields:
            for invalid in ("missing", None, "", " \t ", 123):
                with self.subTest(field=field, invalid=invalid):
                    body = dict(CUSTOMER)
                    if invalid == "missing":
                        body.pop(field)
                    else:
                        body[field] = invalid
                    before = self.db.list_customers()
                    status, _, response = self.request("POST", "/customers", body)
                    self.assertEqual(status, 400)
                    self.assertIn("error", response)
                    self.assertEqual(self.db.list_customers(), before)

    def test_identical_customer_values_create_separate_records(self):
        first = self.request("POST", "/customers", CUSTOMER)
        second = self.request("POST", "/customers", CUSTOMER)
        self.assertEqual((first[0], second[0]), (201, 201))
        self.assertNotEqual(first[2]["customer_id"], second[2]["customer_id"])
        self.assertEqual(len(self.db.list_customers()), 2)

    def test_postal_code_text_and_internal_whitespace_are_preserved(self):
        customer = dict(CUSTOMER)
        customer["postal_code"] = "00123"
        customer["street_address"] = "  12   Main Street  "
        status, _, saved = self.request("POST", "/customers", customer)
        self.assertEqual(status, 201)
        self.assertEqual(saved["postal_code"], "00123")
        self.assertEqual(saved["street_address"], "12   Main Street")

    def test_customer_validation_accepts_international_phone_and_order_payload(self):
        payload = order_payload(CUSTOMER, "FIRST-SPROUT", "1", False)
        self.assertEqual(payload["customer"], CUSTOMER)
        customer = dict(CUSTOMER, phone_country_code=" +33 ", phone_number=" 06 12 34 56 78 ")
        created = self.db.create_customer(customer)
        self.assertEqual(created["phone_country_code"], "+33")
        self.assertEqual(created["phone_number"], "06 12 34 56 78")

    def test_order_with_customer_associates_purchased_customer(self):
        body = placement()
        body.pop("customer_name")
        body["customer"] = CUSTOMER
        status, _, order = self.request("POST", "/orders", body)
        self.assertEqual(status, 201)
        status, _, customers = self.request("GET", "/customers/purchased")
        self.assertEqual(status, 200)
        self.assertEqual(len(customers), 1)
        self.assertEqual(order["customer_name"], "Zoë O'Neil")
        self.assertEqual(customers[0]["full_name"], order["customer_name"])

    def test_invalid_customer_order_is_atomic(self):
        before_stock = self.db.get_product("FIRST-SPROUT")["stock_quantity"]
        before_orders = self.db.list_orders()
        body = placement()
        body.pop("customer_name")
        invalid = dict(CUSTOMER, postal_code=" ")
        body["customer"] = invalid
        status, _, response = self.request("POST", "/orders", body)
        self.assertEqual(status, 400)
        self.assertIn("error", response)
        self.assertEqual(self.db.list_orders(), before_orders)
        self.assertEqual(self.db.get_product("FIRST-SPROUT")["stock_quantity"], before_stock)
        self.assertEqual(self.db.list_customers(), [])

    def test_invalid_later_order_line_does_not_create_customer_or_change_stock(self):
        before_stock = self.db.get_product("FIRST-SPROUT")["stock_quantity"]
        body = placement([
            {"product_sku": "FIRST-SPROUT", "quantity": 1},
            {"product_sku": "UNKNOWN", "quantity": 1},
        ])
        body.pop("customer_name")
        body["customer"] = CUSTOMER
        status, _, response = self.request("POST", "/orders", body)
        self.assertEqual(status, 404)
        self.assertEqual(response, {"error": "Unknown product"})
        self.assertEqual(self.db.list_customers(), [])
        self.assertEqual(self.db.list_orders(), [])
        self.assertEqual(self.db.get_product("FIRST-SPROUT")["stock_quantity"], before_stock)

    def test_customer_and_order_are_persistent(self):
        with TemporaryDirectory() as directory:
            path = directory + "/customers.sqlite3"
            db = Database(path)
            customer = db.create_customer(CUSTOMER)
            order_request = placement()
            order_request.pop("customer_name")
            order_request["customer"] = CUSTOMER
            order = db.create_order(order_request)
            db.close()
            reopened = Database(path)
            try:
                self.assertEqual(reopened.get_customer(customer["customer_id"]), customer)
                self.assertEqual(reopened.get_order(order["order_id"]), order)
                purchased = reopened.list_purchased_customers()
                self.assertEqual(len(purchased), 1)
                self.assertEqual(purchased[0]["full_name"], customer["full_name"])
                self.assertNotEqual(purchased[0]["customer_id"], customer["customer_id"])
            finally:
                reopened.close()

    def test_customer_page_create_action_posts_all_fields(self):
        app = object.__new__(HCCApplication)
        app.base_url = "http://local"
        app.status = FakeStatus()
        app.new_customer_fields = {
            field: SimpleNamespace(get=lambda value=value: value)
            for field, value in CUSTOMER.items()
        }
        submitted = []
        app.refresh_customers = lambda: None

        def submit(_kind, operation, callback, token=None):
            result = operation()
            submitted.append(result)
            callback(result)

        app._submit_task = submit
        with patch("generated.gui._request_json", side_effect=lambda *args: args[2]):
            HCCApplication.create_customer(app)
        self.assertEqual(submitted, [CUSTOMER])
        self.assertIn("Customer created", app.status.values[0])

    def test_customer_page_displays_only_purchased_customers(self):
        app = object.__new__(HCCApplication)
        app.base_url = "http://local"
        app._refresh_tokens = {"customers": 0}
        app.customer_list = type("CustomerList", (), {
            "rows": [],
            "get_children": lambda self: list(range(len(self.rows))),
            "delete": lambda self, _item: self.rows.clear(),
            "insert": lambda self, _parent, _index, values: self.rows.append(values),
        })()
        app._submit_task = lambda _kind, operation, callback, token=None: callback([
            {"full_name": "Zoë", "city": "Montréal", "country": "Canada", "phone_number": "+1 (555)"},
        ])
        HCCApplication.refresh_customers(app)
        self.assertEqual(app.customer_list.rows, [("Zoë", "Montréal", "Canada", "+1 (555)")])


if __name__ == "__main__":
    unittest.main()
