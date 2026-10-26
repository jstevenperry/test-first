import sqlite3
import threading
from datetime import datetime, timezone

if __package__ in (None, ""):
    from money import cents, format_cents, format_rate, line_amounts
else:
    from generated.money import cents, format_cents, format_rate, line_amounts


SEED_PRODUCTS = (
    ("FIRST-SPROUT", "First Sprout Card Pack", "12.50", 100),
    ("REPOTTING-DAY", "Repotting Day Card Pack", "18.00", 50),
    ("WINDOWSILL-JOURNAL", "Windowsill Notes Journal", "24.00", 30),
)

CUSTOMER_FIELDS = (
    "full_name",
    "street_address",
    "city",
    "state",
    "postal_code",
    "country",
    "phone_country_code",
    "phone_number",
)


class OrderNotShippable(Exception):
    pass


def _positive_quantity(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("quantity must be a positive whole number")
    if value <= 0:
        raise ValueError("quantity must be positive")
    return value


def _nonnegative_stock(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("stock quantity must be a non-negative whole number")


class Database:
    def __init__(self, path="hcc.sqlite3"):
        self.path = path
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self):
        with self._lock, self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    street_address TEXT NOT NULL,
                    city TEXT NOT NULL,
                    state TEXT NOT NULL,
                    postal_code TEXT NOT NULL,
                    country TEXT NOT NULL,
                    phone_country_code TEXT NOT NULL,
                    phone_number TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    sku TEXT PRIMARY KEY COLLATE BINARY,
                    name TEXT NOT NULL,
                    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
                    stock_quantity INTEGER NOT NULL CHECK(stock_quantity >= 0)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    subtotal_cents INTEGER NOT NULL,
                    tax_rate_bps INTEGER NOT NULL,
                    tax_cents INTEGER NOT NULL,
                    shipping_cents INTEGER NOT NULL,
                    total_cents INTEGER NOT NULL,
                    amount_paid_cents INTEGER NOT NULL,
                    amount_refunded_cents INTEGER NOT NULL,
                    payment_status TEXT NOT NULL,
                    customer_id INTEGER REFERENCES customers(customer_id)
                );
                CREATE TABLE IF NOT EXISTS order_items (
                    order_id INTEGER NOT NULL REFERENCES orders(order_id),
                    position INTEGER NOT NULL,
                    product_sku TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price_cents INTEGER NOT NULL,
                    discount_rate_bps INTEGER NOT NULL,
                    tax_cents INTEGER NOT NULL,
                    returned_quantity INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(order_id, position)
                );
                """
            )
            order_columns = {
                row["name"] for row in self.connection.execute("PRAGMA table_info(orders)")
            }
            if "customer_id" not in order_columns:
                self.connection.execute(
                    "ALTER TABLE orders ADD COLUMN customer_id INTEGER REFERENCES customers(customer_id)"
                )
            self.connection.executemany(
                "INSERT OR IGNORE INTO products(sku, name, unit_price_cents, stock_quantity) VALUES (?, ?, ?, ?)",
                [(sku, name, cents(price), stock) for sku, name, price, stock in SEED_PRODUCTS],
            )

    def close(self):
        with self._lock:
            self.connection.close()

    def add_product(self, sku, name, unit_price, stock_quantity):
        if not isinstance(sku, str) or not sku.strip():
            raise ValueError("sku must be non-empty")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be non-empty")
        _nonnegative_stock(stock_quantity)
        price = cents(unit_price)
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO products(sku, name, unit_price_cents, stock_quantity) VALUES (?, ?, ?, ?)",
                (sku, name, price, stock_quantity),
            )

    def update_product_price(self, sku, unit_price):
        price = cents(unit_price)
        with self._lock, self.connection:
            cursor = self.connection.execute("UPDATE products SET unit_price_cents=? WHERE sku=?", (price, sku))
            if cursor.rowcount == 0:
                raise KeyError(sku)

    def list_products(self):
        with self._lock:
            rows = self.connection.execute(
                "SELECT sku, name, unit_price_cents, stock_quantity FROM products ORDER BY rowid"
            ).fetchall()
        return [self._product_dict(row) for row in rows]

    def get_product(self, sku):
        with self._lock:
            row = self.connection.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
        return None if row is None else self._product_dict(row)

    @staticmethod
    def normalize_customer(customer):
        if not isinstance(customer, dict):
            raise ValueError("customer must be an object")
        normalized = {}
        for field in CUSTOMER_FIELDS:
            value = customer.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
            normalized[field] = value.strip()
        return normalized

    def create_customer(self, customer):
        normalized = self.normalize_customer(customer)
        columns = ", ".join(CUSTOMER_FIELDS)
        placeholders = ", ".join("?" for _ in CUSTOMER_FIELDS)
        with self._lock, self.connection:
            cursor = self.connection.execute(
                f"INSERT INTO customers({columns}) VALUES({placeholders})",
                tuple(normalized[field] for field in CUSTOMER_FIELDS),
            )
            customer_id = cursor.lastrowid
        return self.get_customer(customer_id)

    def get_customer(self, customer_id):
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM customers WHERE customer_id=?", (customer_id,)
            ).fetchone()
        return None if row is None else self._customer_dict(row)

    def list_customers(self):
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM customers ORDER BY customer_id"
            ).fetchall()
        return [self._customer_dict(row) for row in rows]

    def list_purchased_customers(self):
        with self._lock:
            rows = self.connection.execute(
                """SELECT DISTINCT c.* FROM customers c
                   JOIN orders o ON o.customer_id=c.customer_id
                   ORDER BY c.customer_id"""
            ).fetchall()
        return [self._customer_dict(row) for row in rows]

    @staticmethod
    def _customer_dict(row):
        return {
            "customer_id": row["customer_id"],
            **{field: row[field] for field in CUSTOMER_FIELDS},
        }

    @staticmethod
    def _product_dict(row):
        return {
            "sku": row["sku"],
            "name": row["name"],
            "unit_price": format_cents(row["unit_price_cents"]),
            "stock_quantity": row["stock_quantity"],
        }

    def create_order(self, request, *, tax_rate_bps=0, discount_rates=None, shipping_charge_cents=0):
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        customer_fields = self.normalize_customer(request["customer"]) if "customer" in request else None
        customer_name = (
            customer_fields["full_name"] if customer_fields is not None else request.get("customer_name")
        )
        if not isinstance(customer_name, str) or not customer_name.strip():
            raise ValueError("customer_name must be non-empty")
        customer_name = customer_name.strip()
        if "shipped" in request and not isinstance(request["shipped"], bool):
            raise ValueError("shipped must be a boolean")
        items = request.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("items must be a non-empty array")
        merged = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("each item must be an object")
            sku = item.get("product_sku")
            if not isinstance(sku, str) or not sku.strip():
                raise ValueError("product_sku must be non-empty")
            if "quantity" not in item:
                raise ValueError("quantity is required")
            quantity = item["quantity"]
            if isinstance(quantity, (int, float)) and not isinstance(quantity, bool) and quantity <= 0:
                raise ValueError("quantity must be positive")
            _positive_quantity(quantity)
            merged[sku] = merged.get(sku, 0) + quantity

        discount_rates = discount_rates or {}
        with self._lock:
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                snapshots = []
                for sku, quantity in merged.items():
                    product = self.connection.execute(
                        "SELECT sku, unit_price_cents, stock_quantity FROM products WHERE sku=?", (sku,)
                    ).fetchone()
                    if product is None:
                        raise LookupError("Unknown product")
                    if product["stock_quantity"] < quantity:
                        raise OverflowError("Insufficient stock")
                    rate = discount_rates.get(sku, 0)
                    amounts = line_amounts(product["unit_price_cents"], quantity, rate, tax_rate_bps)
                    snapshots.append((sku, quantity, product["unit_price_cents"], rate, amounts))

                customer_id = None
                if customer_fields is not None:
                    columns = ", ".join(CUSTOMER_FIELDS)
                    placeholders = ", ".join("?" for _ in CUSTOMER_FIELDS)
                    cursor = self.connection.execute(
                        f"INSERT INTO customers({columns}) VALUES({placeholders})",
                        tuple(customer_fields[field] for field in CUSTOMER_FIELDS),
                    )
                    customer_id = cursor.lastrowid
                subtotal = sum(line["subtotal"] for _, _, _, _, line in snapshots)
                tax = sum(line["tax"] for _, _, _, _, line in snapshots)
                total = subtotal + tax + shipping_charge_cents
                created = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                cursor = self.connection.execute(
                    """INSERT INTO orders(customer_name,status,created_at,subtotal_cents,tax_rate_bps,
                       tax_cents,shipping_cents,total_cents,amount_paid_cents,amount_refunded_cents,payment_status,customer_id)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (customer_name, "pending", created, subtotal, tax_rate_bps, tax, shipping_charge_cents, total, 0, 0, "unpaid", customer_id),
                )
                order_id = cursor.lastrowid
                for position, (sku, quantity, unit_price, rate, amounts) in enumerate(snapshots):
                    self.connection.execute(
                        """INSERT INTO order_items(order_id,position,product_sku,quantity,unit_price_cents,
                           discount_rate_bps,tax_cents,returned_quantity) VALUES(?,?,?,?,?,?,?,0)""",
                        (order_id, position, sku, quantity, unit_price, rate, amounts["tax"]),
                    )
                    self.connection.execute(
                        "UPDATE products SET stock_quantity=stock_quantity-? WHERE sku=?", (quantity, sku)
                    )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
        return self.get_order(order_id)

    def get_order(self, order_id):
        with self._lock:
            row = self.connection.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                return None
            items = self.connection.execute(
                "SELECT * FROM order_items WHERE order_id=? ORDER BY position", (order_id,)
            ).fetchall()
        return self._order_dict(row, items)

    def list_orders(self):
        with self._lock:
            ids = [r["order_id"] for r in self.connection.execute("SELECT order_id FROM orders ORDER BY order_id")]
        return [self.get_order(order_id) for order_id in ids]

    def ship_order(self, order_id):
        with self._lock:
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                order = self.connection.execute(
                    "SELECT status, total_cents, amount_paid_cents FROM orders WHERE order_id=?",
                    (order_id,),
                ).fetchone()
                if order is None or order["status"] == "shipped":
                    raise LookupError("Pending order not found")
                if order["status"] != "pending" or order["amount_paid_cents"] < order["total_cents"]:
                    raise OrderNotShippable("Order must be pending and fully paid before shipping")
                cursor = self.connection.execute(
                    "UPDATE orders SET status='shipped' WHERE order_id=? AND status='pending'",
                    (order_id,),
                )
                if cursor.rowcount != 1:
                    raise OrderNotShippable("Order must be pending and fully paid before shipping")
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
        return self.get_order(order_id)

    @staticmethod
    def _order_dict(row, items):
        return {
            "order_id": row["order_id"],
            "customer_name": row["customer_name"],
            "status": row["status"],
            "created_at": row["created_at"],
            "subtotal": format_cents(row["subtotal_cents"]),
            "tax_rate": format_rate(row["tax_rate_bps"]),
            "tax_amount": format_cents(row["tax_cents"]),
            "shipping_charge": format_cents(row["shipping_cents"]),
            "total": format_cents(row["total_cents"]),
            "amount_paid": format_cents(row["amount_paid_cents"]),
            "amount_refunded": format_cents(row["amount_refunded_cents"]),
            "payment_status": row["payment_status"],
            "items": [
                {
                    "product_sku": item["product_sku"],
                    "quantity": item["quantity"],
                    "unit_price": format_cents(item["unit_price_cents"]),
                    "discount_rate": format_rate(item["discount_rate_bps"]),
                    "tax_amount": format_cents(item["tax_cents"]),
                    "returned_quantity": item["returned_quantity"],
                }
                for item in items
            ],
        }
