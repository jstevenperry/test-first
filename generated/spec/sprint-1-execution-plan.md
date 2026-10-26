# Sprint 1 Execution Plan

## Scope

Implement only Sprint 1: BR-01 through BR-05 in `src/spec/no-code-business-requirements.md`. This sprint delivers the product and money domain, SQLite persistence, the JSON REST interface, order placement, and the Tkinter client. Do not implement later-sprint features or use later-sprint requirements to expand this scope. Where BR-04 explicitly requires a catalog-backed product dropdown, implement that behavior using the Sprint 1 catalog interface without importing additional, not-yet-in-scope behavior from later requirements.

Follow the source requirements as the behavioral authority. Place Python implementation modules under `generated/` and tests under `generated/tests/`. Use Python's standard `unittest` framework and name test modules by requirement: `test_br_01.py` through `test_br_05.py`. Use test method names that identify the requirement behavior and, where relevant, its edge case.

## Execution strategy

1. Inspect the workspace and available Python version; establish a minimal package layout under `generated/` and `generated/tests/`. Keep the application runnable through simple `python3 {NAME_OF_MODULE}.py` entry points for both the REST service and GUI.
2. Write all Sprint 1 tests before implementing application behavior. Each BR test module must include coverage for every listed edge case and observable contract in its requirement. Keep API and GUI tests deterministic by using temporary SQLite databases, ephemeral local ports, controlled HTTP responses, and Tk test doubles or a display-capable test setup as appropriate.
3. Run the tests and confirm that failures demonstrate missing behavior rather than test setup or environment errors. Do not start implementation until the complete Sprint 1 test set has been written.
4. Implement shared domain and persistence behavior first, then the REST interface, followed by the GUI. Reuse shared validation and money logic so the API and GUI-facing operations remain consistent.
5. Run the complete Sprint 1 unittest suite after implementation. Investigate failures without exceeding the source requirement's limit of two automatic fix attempts per failing issue; report any unresolved failure for operator intervention. Do not treat the sprint as code complete unless all Sprint 1 tests execute successfully.

## Proposed module responsibilities

- `generated/money.py`: exact decimal-to-cent and basis-point calculations; no binary floating-point for business money.
- `generated/catalog.py` and/or `generated/database.py`: SQLite schema, initialization and seed products, product validation, order persistence, stock checks, and atomic order placement.
- `generated/api.py`: JSON HTTP routes, request validation, response formatting, server startup, and request/error logging; bind to loopback by default.
- `generated/gui.py`: Tkinter views and navigation, REST client calls, non-blocking workers, and thread-safe result handoff.
- `generated/tests/test_br_01.py` through `test_br_05.py`: requirement-specific unit and integration tests using the standard library.

The exact module split may be adjusted to fit the implementation cleanly, but keep the required output roots, test-first order, runnable entry points, and requirement traceability.

## BR-01: Product identity and data

### Planned tests

In `test_br_01.py`, verify product data validation, uniqueness, price normalization, and fresh-database initialization. Include product creation or insertion tests for valid and invalid inputs, as well as checks of the three seeded records and their exact field values.

### Edge cases to cover

- Empty or whitespace-only SKU and product name are rejected.
- SKU uniqueness is case-sensitive: an exact duplicate is rejected while SKUs differing only by letter case remain distinct.
- Zero unit price and zero stock quantity are valid.
- Negative unit prices and negative stock quantities are invalid.
- Stock quantity must be a whole number; fractions and booleans must not be accepted as whole-number quantities.
- Prices with more than two decimal places round to cents using half-up rounding, including positive halfway values.
- A negative price is rejected before rounding, including a small negative value that would otherwise round to zero.
- A newly initialized database contains exactly the required starter catalog entries with the specified SKUs, names, prices, and quantities; initialization must not duplicate seed data when the database is reopened.

## BR-02: Money representation

### Planned tests

In `test_br_02.py`, exercise conversion, formatting, multiplication, discount, and tax helpers independently of HTTP or GUI code. Assert exact cent values and serialized strings rather than approximate floating-point equality.

### Edge cases to cover

- Ten units at $0.10 total exactly $1.00.
- Half-up rounding at the cent boundary, including a $0.05 extended amount discounted at 10.00% producing a $0.01 discount.
- A $0.05 net line taxed at 10.00% produces $0.01 tax.
- Zero-quantity multiplication returns an exact zero amount.
- Non-zero integer basis-point rates calculate line discount and tax correctly.
- Percentage rates serialize as strings with two decimal places in percentage points, including zero and 10.00%.
- Ensure monetary calculations do not rely on binary floating-point, and that the final monetary representation always has exactly two decimal places.

## BR-03: Unsecured REST interface

### Planned tests

In `test_br_03.py`, start the service against a temporary database and exercise it over HTTP. Verify status codes, headers, JSON bodies, field sets, ordering, formatting, persistence, default binding, and logs. Reserve an ephemeral loopback port for tests so they do not depend on port 8000 being available.

### Edge cases to cover

- `GET /products` returns the catalog array with the required product fields; `GET /products/{sku}` returns one matching product; an unknown SKU returns 404 with a JSON error.
- An escaped SKU path resolves to the same exact SKU after URL decoding.
- `POST /orders` accepts valid customer and item data and returns 201 with the complete order; missing or malformed JSON, fields, item lists, items, quantities, or shipped values return 400 with a JSON `error`.
- Order responses contain exactly the specified order and item fields, integer order IDs, and explicitly represented default tax, discount, shipping, payment, and refund values.
- Money and rate fields are JSON strings with two decimal places; timestamps are UTC ISO 8601 strings ending in `Z`.
- `GET /orders` returns orders in ascending ID order. `GET /orders/{id}` returns the same complete representation as creation; a non-integer ID returns 400 and an unknown integer ID returns 404.
- Product unit prices are snapshotted at order placement: changing a catalog price later does not alter the persisted order unit price or subtotal.
- Order financial calculations use the default 0.00% tax, 0.00% discount, and $0.00 shipping values; line tax is summed from rounded item tax amounts, and order total is subtotal plus tax and shipping.
- Non-zero-rate calculation fixtures verify half-up rounding for item discounts and item taxes, including the stated 10-unit examples.
- Repeated order lines for one SKU combine quantities while retaining first-occurrence order; stock is validated against the combined quantity.
- Unknown-SKU, insufficient-stock, and invalid-order failures are atomic: no partial order is persisted and no product stock changes, including when the failing line follows a valid line.
- A newly created order remains `pending` and `unpaid` regardless of whether `shipped` is omitted, true, or false.
- An unsupported method on a known route returns 405 with a JSON error and the correct `Allow` header, including `OPTIONS` or `HEAD` where supported by the test client.
- An unknown route, including `GET /orders/`, returns 404 and is distinct from a known route with an unsupported method.
- Unexpected server failures return status 500 and exactly `{"error": "Internal server error"}` without leaking exception details; the full traceback is written to the error log.
- The server binds to `127.0.0.1` by default, prints a startup message identifying its actual URL and port, and logs each handled HTTP request.
- The REST service exposes a `python3 {NAME_OF_MODULE}.py` entry point.

## BR-04: Tkinter desktop GUI

### Planned tests

In `test_br_04.py`, test widget configuration and user-visible state, and isolate networking behind a client or injectable request function to verify asynchronous behavior without relying on a live external service. Use a display-capable CI environment where available; otherwise use focused Tk doubles for the required widget and lifecycle assertions.

### Edge cases to cover

- The window title is exactly `Houseplant Correspondence Company`, nominal geometry is 760 by 520, and page headings use bold 16-point text with platform-default themed widgets.
- Navigation has the `View:` label and `Inventory`, `Place Order`, and `Orders` buttons; activating a button switches the visible frame without opening another window.
- The red unsecured-API warning remains visible on every page, and the bottom status line starts at `Ready`.
- The API base URL comes from `HCC_API_URL` when set and otherwise defaults to `http://127.0.0.1:8000`; the window does not solicit credentials or allow URL edits.
- Inventory displays the required columns, has no `Refresh inventory` button, and fetches current data whenever shown or revisited.
- The Place Order form has the required labels, a catalog-backed product dropdown, quantity initially set to `1`, an initially unchecked `Shipped` checkbox, and a `Submit order` action. Each submission sends exactly one product line.
- Successful orders trigger an inventory refresh; the Orders page fetches on selection/return and also provides the required manual refresh button and order summary fields.
- Network calls do not block normal UI interaction. Workers do not read or mutate Tk widgets or call Tk methods; results are handed back thread-safely and applied on the interface thread.
- When same-page refreshes finish out of request order, an older response cannot overwrite the latest requested page data.
- Repeated Submit activations send separate requests; successful activations create separate orders rather than being silently coalesced.
- Closing the window with requests in flight does not let a worker access the destroyed window or its widgets.
- Progress is shown while requests are in flight. API-provided non-empty `error` text is displayed; absent or empty error text falls back to an HTTP-status or connection-failure message.
- The unsecured warning text is shown exactly: `UNSECURED API  |  Use only with a trusted local endpoint`.
- The GUI exposes a `python3 {NAME_OF_MODULE}.py` entry point.

## BR-05: Order placement

### Planned tests

In `test_br_05.py`, exercise order input validation through the API-facing business operation and verify rejection leaves both the order table and inventory unchanged. Keep HTTP-level status and response assertions in `test_br_03.py`; use this module to make the BR-05 validation and atomicity coverage easy to trace.

### Edge cases to cover

- Blank or whitespace-only customer names and product SKUs are rejected.
- Missing customer, item-list, SKU, or quantity fields are rejected.
- Empty, malformed, or non-list item collections are rejected; non-object item entries are rejected.
- A quantity of zero or a negative integer returns the exact error `quantity must be positive`.
- Negative fractional quantities return the exact error `quantity must be positive`.
- Positive fractional quantities, booleans, and non-numeric quantities are rejected as invalid whole-number quantities.
- Quantity `1` is accepted.
- A supplied `shipped` value must be a JSON boolean; malformed values such as `"yes"` are rejected. An omitted, true, or false shipped value results in a `pending` order.
- An invalid line after an otherwise valid line rejects the entire placement: no order is created and no inventory is changed.

## Cross-requirement checks and completion

- Keep every test traceable to its BR and use the required BR-specific test module filenames.
- Verify API serialization uses the same domain and money rules tested in isolation; avoid duplicating calculations in the GUI or HTTP layer.
- Verify a failed order never leaves partially inserted order or item records and never decrements stock, even if validation fails after earlier valid input.
- Run all five test modules together after implementation, in addition to any focused test runs during development.
- Confirm the implementation and tests remain entirely within `generated/` and `generated/tests/`, respectively, and that only Sprint 1 behavior has been added.
