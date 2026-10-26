import json
import os
import queue
import threading
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import ttk


WARNING_TEXT = "UNSECURED API  |  Use only with a trusted local endpoint"


def api_base_url():
    return os.environ.get("HCC_API_URL", "http://127.0.0.1:8000").rstrip("/")


def order_payload(customer_name, sku, quantity, shipped):
    if isinstance(customer_name, dict):
        customer = customer_name
        return {
            "customer": customer,
            "items": [{"product_sku": sku, "quantity": int(quantity)}],
            "shipped": bool(shipped),
        }
    return {
        "customer_name": customer_name,
        "items": [{"product_sku": sku, "quantity": int(quantity)}],
        "shipped": bool(shipped),
    }


def _request_json(url, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read()
        finally:
            exc.close()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        message = payload.get("error") if isinstance(payload, dict) else None
        raise RuntimeError(message if isinstance(message, str) and message.strip() else f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Connection failure: {exc}") from exc


class HCCApplication:
    def __init__(self, root=None, base_url=None):
        self.root = root or tk.Tk()
        self.base_url = (base_url or api_base_url()).rstrip("/")
        self._results = queue.Queue()
        self._closed = False
        self._refresh_tokens = {"inventory": 0, "orders": 0, "customers": 0}
        self._product_skus = {}
        self.root.title("Houseplant Correspondence Company")
        self.root.geometry("760x520")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        container = ttk.Frame(self.root, padding=10)
        container.pack(fill="both", expand=True)
        navigation = ttk.Frame(container)
        navigation.pack(fill="x")
        ttk.Label(navigation, text="View:").pack(side="left", padx=(0, 8))
        for title in ("Inventory", "Place Order", "Orders", "Customers"):
            ttk.Button(navigation, text=title, command=lambda name=title: self.show_page(name)).pack(side="left", padx=3)
        self.warning = tk.Label(container, text=WARNING_TEXT, foreground="red")
        self.warning.pack(fill="x", pady=(8, 4))

        self.pages = {}
        self._build_inventory(container)
        self._build_place_order(container)
        self._build_orders(container)
        self._build_customers(container)
        self.status = ttk.Label(container, text="Ready", anchor="w")
        self.status.pack(side="bottom", fill="x", pady=(8, 0))
        self.pages["Inventory"].pack(fill="both", expand=True)
        self.root.after(0, self.refresh_inventory)
        self.root.after(50, self._drain_results)

    def _heading(self, parent, text):
        ttk.Label(parent, text=text, font=("TkDefaultFont", 16, "bold")).pack(anchor="w", pady=(4, 12))

    def _build_inventory(self, parent):
        frame = ttk.Frame(parent)
        self.pages["Inventory"] = frame
        self._heading(frame, "Inventory")
        self.inventory = ttk.Treeview(frame, columns=("sku", "name", "price", "stock"), show="headings")
        for key, title, width in (
            ("sku", "SKU", 150), ("name", "Product name", 280),
            ("price", "Unit price", 120), ("stock", "Stock quantity", 130),
        ):
            self.inventory.heading(key, text=title)
            self.inventory.column(key, width=width)
        self.inventory.pack(fill="both", expand=True)

    def _build_place_order(self, parent):
        frame = ttk.Frame(parent)
        self.pages["Place Order"] = frame
        self._heading(frame, "Place Order")
        form = ttk.Frame(frame)
        form.pack(anchor="nw")
        self.customer_fields = {}
        customer_labels = (
            ("full_name", "Full name"),
            ("street_address", "Street number and name"),
            ("city", "City"),
            ("state", "State"),
            ("postal_code", "Postal code"),
            ("country", "Country"),
            ("phone_country_code", "Phone country code"),
            ("phone_number", "Phone number"),
        )
        for row, (field, label) in enumerate(customer_labels):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(form, width=40)
            entry.grid(row=row, column=1, sticky="w", pady=2)
            self.customer_fields[field] = entry
        self.customer_entry = self.customer_fields["full_name"]
        ttk.Label(form, text="Product SKU").grid(row=8, column=0, sticky="w", pady=3)
        self.product_choice = ttk.Combobox(form, state="readonly", width=37, values=())
        self.product_choice.grid(row=8, column=1, sticky="w", pady=3)
        ttk.Label(form, text="Quantity").grid(row=9, column=0, sticky="w", pady=3)
        self.quantity_entry = ttk.Entry(form, width=10)
        self.quantity_entry.insert(0, "1")
        self.quantity_entry.grid(row=9, column=1, sticky="w", pady=3)
        self.shipped_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Shipped", variable=self.shipped_var).grid(row=10, column=1, sticky="w", pady=3)
        ttk.Button(form, text="Submit order", command=self.submit_order).grid(row=11, column=1, sticky="w", pady=5)

    def _build_orders(self, parent):
        frame = ttk.Frame(parent)
        self.pages["Orders"] = frame
        self._heading(frame, "Orders")
        self.order_list = ttk.Treeview(frame, columns=("id", "customer", "status", "total"), show="headings")
        for key, title, width in (
            ("id", "Order ID", 100), ("customer", "Customer name", 270),
            ("status", "Status", 150), ("total", "Total", 120),
        ):
            self.order_list.heading(key, text=title)
            self.order_list.column(key, width=width)
        self.order_list.pack(fill="both", expand=True)
        ttk.Button(frame, text="Refresh orders", command=self.refresh_orders).pack(anchor="e", pady=8)

    def _build_customers(self, parent):
        frame = ttk.Frame(parent)
        self.pages["Customers"] = frame
        self._heading(frame, "Customers")
        form = ttk.Frame(frame)
        form.pack(anchor="nw")
        self.new_customer_fields = {}
        customer_labels = (
            ("full_name", "Full name"),
            ("street_address", "Street number and name"),
            ("city", "City"),
            ("state", "State"),
            ("postal_code", "Postal code"),
            ("country", "Country"),
            ("phone_country_code", "Phone country code"),
            ("phone_number", "Phone number"),
        )
        for row, (field, label) in enumerate(customer_labels):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=1)
            entry = ttk.Entry(form, width=38)
            entry.grid(row=row, column=1, sticky="w", pady=1)
            self.new_customer_fields[field] = entry
        ttk.Button(form, text="Create Customer", command=self.create_customer).grid(
            row=len(customer_labels), column=1, sticky="w", pady=5
        )
        self.customer_list = ttk.Treeview(
            frame, columns=("name", "city", "country", "phone"), show="headings", height=6
        )
        for key, title, width in (
            ("name", "Full name", 190), ("city", "City", 130),
            ("country", "Country", 130), ("phone", "Phone", 170),
        ):
            self.customer_list.heading(key, text=title)
            self.customer_list.column(key, width=width)
        self.customer_list.pack(fill="both", expand=True, pady=(6, 0))

    def show_page(self, name):
        for frame in self.pages.values():
            frame.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        if name == "Inventory":
            self.refresh_inventory()
        elif name == "Orders":
            self.refresh_orders()
        elif name == "Customers":
            self.refresh_customers()

    def _submit_task(self, kind, operation, callback, token=None):
        self.status.configure(text="Request in progress...")

        def work():
            try:
                result = operation()
                self._results.put((kind, token, callback, result, None))
            except Exception as exc:
                self._results.put((kind, token, callback, None, str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _drain_results(self):
        if self._closed:
            return
        while True:
            try:
                kind, token, callback, result, error = self._results.get_nowait()
            except queue.Empty:
                break
            if token is not None and token != self._refresh_tokens.get(kind):
                continue
            if error:
                self.status.configure(text=error)
            else:
                callback(result)
                self.status.configure(text="Ready")
        self.root.after(50, self._drain_results)

    def refresh_inventory(self):
        self._refresh_tokens["inventory"] += 1
        token = self._refresh_tokens["inventory"]

        def apply(products):
            for row in self.inventory.get_children():
                self.inventory.delete(row)
            for product in products:
                self.inventory.insert("", "end", values=(
                    product["sku"], product["name"], product["unit_price"], product["stock_quantity"]
                ))
            previous_selection = self.product_choice.get()
            self._product_skus = {
                f"{product['name']} ({product['sku']})": product["sku"]
                for product in products
            }
            choices = list(self._product_skus)
            self.product_choice.configure(values=choices)
            self.product_choice.set(previous_selection if previous_selection in self._product_skus else "")

        self._submit_task("inventory", lambda: _request_json(self.base_url + "/products"), apply, token)

    def refresh_orders(self):
        self._refresh_tokens["orders"] += 1
        token = self._refresh_tokens["orders"]

        def apply(orders):
            for row in self.order_list.get_children():
                self.order_list.delete(row)
            for order in orders:
                self.order_list.insert("", "end", values=(
                    order["order_id"], order["customer_name"], order["status"], order["total"]
                ))

        self._submit_task("orders", lambda: _request_json(self.base_url + "/orders"), apply, token)

    def refresh_customers(self):
        self._refresh_tokens["customers"] += 1
        token = self._refresh_tokens["customers"]

        def apply(customers):
            for row in self.customer_list.get_children():
                self.customer_list.delete(row)
            for customer in customers:
                self.customer_list.insert("", "end", values=(
                    customer["full_name"], customer["city"], customer["country"], customer["phone_number"]
                ))

        self._submit_task(
            "customers",
            lambda: _request_json(self.base_url + "/customers/purchased"),
            apply,
            token,
        )

    def _customer_values(self, fields):
        return {name: entry.get() for name, entry in fields.items()}

    def create_customer(self):
        customer = self._customer_values(self.new_customer_fields)

        def apply(_created):
            self.status.configure(text="Customer created")
            self.refresh_customers()

        self._submit_task(
            "customer_create",
            lambda: _request_json(self.base_url + "/customers", "POST", customer),
            apply,
        )

    def submit_order(self):
        selected = self.product_choice.get()
        sku = self._product_skus.get(selected)
        if not sku:
            self.status.configure(text="Select a product before submitting an order")
            return
        try:
            payload = order_payload(
                self._customer_values(self.customer_fields), sku,
                self.quantity_entry.get(), self.shipped_var.get()
            )
        except (TypeError, ValueError):
            self.status.configure(text="Quantity must be a whole number")
            return

        def apply(_order):
            self.status.configure(text="Order submitted")
            self.refresh_inventory()

        self._submit_task(
            "submit",
            lambda: _request_json(self.base_url + "/orders", "POST", payload),
            apply,
        )

    def close(self):
        self._closed = True
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    HCCApplication().run()


if __name__ == "__main__":
    main()
