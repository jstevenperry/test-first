> **AI-generated:** Drafted with AI assistance.

# Houseplant Correspondence Company: Business Requirements

## 1. Purpose

- The Houseplant Correspondence Company (HCC) application is a small Python business application representing a stationery catalog, calculating order totals, checking inventory, summarizing orders, storing accepted orders in a standard Python sqlite3 database, exposing its main business methods through an HTTP/JSON API, and providing a Tkinter desktop client for that API

- The business requirements described in this document dictate the observable behavior of the application, both through its REST API, and its Graphical User Interface

- This document serves as the "source code" for generating an application that behaves as described in this document. NO OTHER DOCUMENTS SHALL BE USED TO GENERATED CODE UNLESS EXPLICITLY SPECIFIED BY THE OPERATOR.

- Python source code shall be generated to the root structure: `test-first/generated`, leaving it up to the AI coding assistant to determine whatever structure beneath the specified root

- Test code should be generated to `test-first/generated/tests`

- The Python source code shall be generated TEST-FIRST: the Python unittest tests shall be generated first, making sure that each business requirement has at least one unittest associated with it. The source file name for the unittest shall be encoded with the business requirement. For example, BR-01 unittest file shall be called test_br_01.py. The test methods within the file shall be encoded with a shortened name of the BR title plus any other identifying text such as a shortened edge case title

- The Python source code implementation shall be generated AFTER the unittests for all BRs in the current sprint. The first sprint shall be called "Sprint 1" and its business requirements shall be elucidated within the corresponding section of this document. Sprint 2 and subsequent sprints shall follow the same test-first process.

- The Python source code for the current sprint will not be considered "code complete" until ALL unittest for the sprint pass/execute successfully

- If a test is failing, the AI coding assistant shall make no more than 2 attempts to fix the issue automatically before reporting it to the human operator for intervention

## 2. Business Vocabulary

- **Product:** A catalog entry identified by a SKU, with a name, unit price, and available stock quantity
- **Order:** An accepted order with a generated ID, customer name, creation timestamp, lifecycle status, financial snapshots, payment/refund ledger entries, and one or more associated items.
- **Customer:** A person represented by a stored customer record, which includes full name, address (street number and name, city, state, postal code, country), and full phone number (country code, phone number). A purchased customer is associated with one or more successfully placed orders; a record may also be created before a purchase.

## 3. Sprint 1

Requirements defined in this section are in the current sprint scope

### BR-01: Product identity and data

- Each product shall have a non-empty SKU, a non-empty name, a non-negative unit price, and a non-negative whole-number stock quantity

- SKUs are unique and are case-sensitive

- Zero is a valid unit price and a valid stock quantity

- Negative prices and negative stock quantities are invalid

- Prices shall include only cents to two decimal places, rounding where needed "half up"

- A negative price is invalid before rounding, even when rounding to cents would produce zero.

- A newly initialized database shall contain these products:

    | SKU | Name | Unit price | Initial stock quantity |
    | --- | --- | ---: | ---: |
    | `FIRST-SPROUT` | First Sprout Card Pack | $12.50 | 100 |
    | `REPOTTING-DAY` | Repotting Day Card Pack | $18.00 | 50 |
    | `WINDOWSILL-JOURNAL` | Windowsill Notes Journal | $24.00 | 30 |

### BR-02: Money representation

- Business calculations shall be exact; ten units at $0.10 each total exactly $1.00

- A price with more than two decimal places shall be rounded to cents using half-up rounding (the method most of us learned in school)

- Tax and discount rates shall be stored internally as integer basis points. In JSON, rate values shall be strings with two decimal places in percentage points; for example, `"10.00"` means 10%.

- Monetary calculations shall also support zero-quantity multiplication and line calculations with non-zero basis-point rates without using binary floating-point arithmetic.

### BR-03: Unsecured REST interface

- The application shall expose the main catalog (as a JSON response) through a JSON REST interface

    The interface shall provide:

    - `GET /products` returns an array of products; `GET /products/{sku}` returns one product. A product has `sku`, `name`, `unit_price`, and `stock_quantity`. An unknown SKU returns 404
    - `POST /orders` accepts an order object with `customer_name`, a non-empty `items` array of objects containing `product_sku` and `quantity`, and an optional boolean `shipped` value. A successful request returns 201 and the complete created order.
    - `GET /orders` returns an array of orders; `GET /orders/{id}` returns one order. A non-integer ID returns 400; an unknown ID returns 404. An order has `order_id`, `customer_name`, `status`, `created_at`, `subtotal`, `tax_rate`, `tax_amount`, `shipping_charge`, `total`, `amount_paid`, `amount_refunded`, `payment_status`, and `items`. Each order item has `product_sku`, `quantity`, `unit_price`, `discount_rate`, `tax_amount`, and `returned_quantity`. Orders are returned in ascending `order_id`.

- Money values in JSON responses shall be strings with two decimal places

- Tax rate and discount rate values in JSON responses shall be strings with two decimal places in percentage points; for example, `"0.00"` means 0%.

- Order financial defaults and calculations:
    - The default tax rate, item discount rate, and shipping charge are 0.00%, 0.00%, and $0.00 respectively.
    - Each order item snapshots the product's unit price when the order is accepted. Its `unit_price` is the pre-discount price.
    - For each item, calculate the extended price as unit price times quantity. Calculate the discount from the extended price using the item's discount rate, round that discount to cents using half-up rounding, then subtract it to obtain the net item subtotal.
    - The order `subtotal` is the sum of net item subtotals, before tax and shipping. Calculate each item's `tax_amount` from its net item subtotal using the order tax rate, rounded to cents using half-up rounding. The order `tax_amount` is the sum of item tax amounts. `total` equals subtotal plus tax plus shipping.
    - `amount_paid` and `amount_refunded` are $0.00 when an order is created.
    - The line-calculation rules apply for non-zero rates as well as the zero-rate defaults. For example, 10 units at $18.00 with a 10.00% item discount have an extended price of $180.00, a rounded discount of $18.00, and a net subtotal of $162.00; at a 10.00% tax rate, line tax is $16.20. A $0.05 extended amount discounted at 10.00%, or a $0.05 net subtotal taxed at 10.00%, produces a rounded discount or tax amount of $0.01, respectively.
    - Sprint 1 does not expose an API or GUI setting to change tax, discount, or shipping policy; created orders use the stated defaults.

- Order inventory and line behavior:
    - Every ordered SKU must exist and have sufficient stock. An unknown SKU returns 404; insufficient stock returns 409.
    - Repeated lines for the same SKU are combined by summing their quantities. The combined item retains the position of the SKU's first occurrence.
    - The order and stock decrements shall be committed atomically. Validation, unknown-SKU, or insufficient-stock failures shall not create a partial order or change stock.

- Order metadata and HTTP behavior:
    - A newly created order has status `pending` and payment status `unpaid`, regardless of a valid `shipped` value.
    - The database assigns integer `order_id` values using an auto-incrementing primary key. `created_at` is recorded and returned as UTC ISO 8601 with a trailing `Z`.
    - Invalid JSON, missing or malformed request fields, and BR-05 validation failures return 400 with a JSON `{"error": "..."}` body. Quantity errors for zero or negative quantities use the exact message `quantity must be positive`.
    - Insufficient stock returns 409 with a JSON `{"error": "..."}` body. Unknown product SKUs and order IDs return 404 with a JSON `{"error": "..."}` body.

- The interface shall not require credentials in this iteration. It shall bind to `127.0.0.1` by default. Binding to a non-loopback address is an operator-controlled configuration and must not be used on a shared or public network until authentication, authorization, and transport security are added. The interface can create orders and change stock, so it shall be treated as trusted local access only

- The Python "main" method for running the REST interface shall be conveniently exposed so that it can be run via a simple `python3 {NAME_OF_MODULE}.py` command

- When started, the REST server shall print a console startup message identifying its URL and port. It shall log each incoming HTTP request.

Edge cases:

- An unsupported method on a known route, such as `OPTIONS` or `HEAD`, returns 405 with an `Allow` header
- An unexpected server failure returns 500 with a generic `Internal server error` message. The server writes the full exception traceback to its error log so operators can diagnose it. Error details shall not appear in the JSON response body: {\"error\": \"...\"} for 4xx and 5xx responses, with the 500 value exactly Internal server error
- An unknown route, including `GET /orders/`, returns 404 with a JSON error; it is distinct from an unsupported method on a known route. A known route with an unsupported method returns 405 with a JSON error and the route's `Allow` header.
- A request for an escaped SKU resolves to the same exact SKU after URL decoding.
- A successful order can be retrieved by its integer ID with the same complete representation returned at creation. Changing the product's catalog price afterward does not change the order's unit-price snapshot or subtotal.
- A valid order response has the complete specified order and item field sets, integer `order_id`, UTC ISO-8601 timestamp ending in `Z`, and money/rate values with the specified JSON string types and formatting. The default tax, shipping, discount, payment, and refund values are all represented explicitly.
- A placement containing a valid line followed by an unknown SKU or an insufficient-stock line creates no order and changes no product stock.
- The API calculates ten units at $0.10 as exactly $1.00. Non-zero discount and tax calculations use the line examples above and round each discount and each item tax half up to cents.
- The default server bind address is `127.0.0.1`; the startup message includes its actual port, and a handled request is written to the request log.

### BR-04: Tkinter desktop GUI

- The application shall provide a Tkinter desktop GUI that uses the REST API, not direct database access, for its business operations

- The desktop GUI shall use multiple page frames to provide "views" for the user to interact with different views of the application (for example, to switch between an inventory view and a place order view). Buttons shall be provided to facilitate the switch between page frames (views)

Details:

    The GUI shall allow a user to:

    - Connect to a configurable API base URL, defaulting to `http://127.0.0.1:8000` or the `HCC_API_URL` environment value
    - View the product catalog and current stock
    - Place an order
    - View and refresh orders that have been placed

- The window shall be titled `Houseplant Correspondence Company` and open at a nominal size of 760 by 520 pixels. It shall use the platform's default Tkinter themed-widget appearance, with bold 16-point page headings.

- The window shall have a horizontal navigation row with a `View:` label followed by the `Inventory`, `Place Order`, and `Orders` buttons. Selecting a button shall show that page frame without opening a separate window.

- A red `UNSECURED API  |  Use only with a trusted local endpoint` warning shall remain visible below the navigation row on every page. A status line shall remain visible at the bottom of the window, initially showing `Ready`, and shall communicate when a request is in progress or has failed.

- The Inventory page shall show a table with `SKU`, `Product name`, `Unit price`, and `Stock quantity` columns. It shall not have a `Refresh inventory` button. Showing or returning to the Inventory page shall request the current catalog from the API; after a successful order, the GUI shall refresh inventory.

- The Place Order page shall show labeled controls for `Customer name`, `Product SKU`, and `Quantity`; the product control shall be a catalog-backed dropdown as specified in BR-11, and quantity shall initially be `1`. It shall provide a `Shipped` checkbox, initially unchecked, and a `Submit order` button. Each submission shall contain one product line. After a successful order, the GUI shall refresh inventory.

- The Orders page shall show a list of order summaries containing the order ID, customer name, status, and total, with a `Refresh orders` button. Selecting or returning to the page shall automatically retrieve the current orders; the manual refresh action shall remain available, as specified in BR-10.

- The API base URL shall be configured through the `HCC_API_URL` environment value or the default URL; it shall not require entering credentials or editing the URL in the window.

- Network requests shall not block normal window interaction. Worker threads shall not access Tk widgets or call Tk methods. They shall return results through a thread-safe handoff, and the interface thread shall apply those results.

- If refreshes for the same page complete out of request order, only the result from the most recently requested refresh shall replace that page's displayed data.

- Repeated activations of `Submit order` are separate submissions; each activation shall send its own one-line order request, and each accepted request creates its own order.

- Closing the window while a network request is in flight shall not cause its worker thread to access the destroyed window or its widgets.

- The GUI shall show API errors and connection failures in the bottom status message, using the API's non-empty `error` text when returned and an HTTP-status or connection-failure message when usable error text is absent. It shall show request progress while work is in flight. The window shall display this warning at all times: `UNSECURED API  |  Use only with a trusted local endpoint`

- The Python "main" method for running the GUI code shall be conveniently exposed so that it can be run via a simple `python3 {NAME_OF_MODULE}.py` command

### BR-05: Order placement

An order placement shall have a non-empty customer name and one or more product lines, each with a non-empty product SKU and a positive whole-number quantity. The optional `shipped` flag shall be a boolean when provided, but it does not change the status of the new order: every order starts pending. Invalid values shall be rejected rather than accepted as an order. Invalid placements shall not create an order or change inventory.

A SKU or customer name that is blank (for example, `" "`) shall be rejected with an error. A numeric quantity of zero or less, including negative fractions, shall be rejected with the exact error `quantity must be positive`. A quantity of `1` is valid. A quantity of `true` or `false`, a positive fraction (for example, `1.5`), or a non-numeric quantity shall be rejected with an error. A shipped value that is not `true` or `false` (for example, `yes`) shall be rejected with an error. An order placement created without a shipped value, or with `true` or `false`, shall create a pending order.

Edge cases:

- A blank SKU (`" "`) or blank customer name (`" "`) is rejected with an error.
- A quantity of `0` or `-1` is rejected with an error stating `quantity must be positive`.
- A negative fractional quantity is rejected with the exact error `quantity must be positive`; positive fractions, booleans, and non-numeric quantities are rejected as invalid whole-number quantities.
- A quantity of `1` is accepted.
- Missing customer, item-list, SKU, or quantity fields; non-object items; and malformed item-list or `shipped` values return a JSON 400 error and do not create an order or change stock.
- An invalid line after a valid line rejects the whole placement without a partial order or inventory change.

# Sprint 2

### BR-06: Product lookup

Looking up or placing an order for an unknown SKU shall fail with a clear error stating `Unknown product`; an unknown product shall not create an order or change stock.

Edge cases:

- Looking up `GET /products/UNKNOWN` or placing an order containing `UNKNOWN` returns JSON 404 with the exact error `Unknown product`.
- A placement with one valid SKU and one `UNKNOWN` SKU fails atomically, creates no order, and leaves all product stock unchanged.
- Unknown-SKU handling is consistent across the existing product lookup and order-placement surfaces; it does not add a quote endpoint.

### BR-07: Order creation

An order shall be created with a generated order ID, the customer name, a creation timestamp, and pending status. A placement may contain one or more different products. Duplicate SKU lines shall be combined before discount evaluation and stock checks.

Each line shall keep its SKU, quantity, unit price, discount, and tax as they applied at placement. The order shall keep its merchandise subtotal, tax, shipping charge, and total as they applied at placement. Later price or policy changes shall not alter them.

For example, placing 10 `REPOTTING-DAY` packs shall show one line at $18.00 with a 10% discount, and a subtotal and total of $162.00, with tax and shipping of zero under the default policy. A line without a discount shall show no discount. Under a 10% tax rate applied to the discounted line subtotal, the 10-pack example shall show $16.20 of tax on that line. These nonzero example rates are exercised by controlled test fixtures; they do not add a public policy-management API or change the default rates.

Edge cases:

- Placing 10 x `REPOTTING-DAY` shows one line at $18.00 with a 10% discount, and a subtotal and total of $162.00.
- Placing 2 x `FIRST-SPROUT` and 1 x `WINDOWSILL-JOURNAL` shows two lines, each at its own unit price, and a subtotal of $49.00.
- Placing 10 x `REPOTTING-DAY` and 1 x `FIRST-SPROUT` applies the discount to the `REPOTTING-DAY` line only, for a subtotal of $174.50.
- Placing two lines of 5 x `REPOTTING-DAY` shows one combined line of quantity 10 with a 10% discount, and a subtotal of $162.00.
- Under a 10% tax rate and a 10% `REPOTTING-DAY` discount, the 10-pack line tax is $16.20 and its total is $178.20.
- A $0.05 line rounds a 10% discount of half a cent to $0.01 and a 10% tax of half a cent to $0.01, using half-up cent rounding.
- Duplicate quantities are combined before stock validation; a combined quantity above available stock is rejected without creating an order or changing stock.
- Duplicate lines retain the first occurrence's position, and persisted order totals equal the sum of the line and order snapshots.

### BR-08: Shipping status

New orders shall start as pending, regardless of the shipped flag on the placement. A pending order may be marked shipped only after its full total is paid. The REST transition shall be `POST /orders/{id}/ship`; success shall return the complete updated order, an ineligible order shall return JSON 409, and a missing or already-shipped order shall return JSON 404 with the exact error `Pending order not found`. Attempting to ship a missing, unpaid, cancelled, or non-pending order shall fail without changing it. The shipped status shall still be shown after the application restarts. Payment and cancellation operations are not introduced by this requirement.

Placing an order with the shipped flag set shall create a pending order that is not marked shipped. Marking a pending, fully paid order as shipped shall succeed, and the order shall show as shipped when viewed again, including after the application restarts. Marking a missing order (for example, ID `999`) or an already-shipped order as shipped shall fail with an error stating `Pending order not found`, and shall change nothing.

Edge cases:

- An order placed with the shipped flag set has status `pending` and is not marked shipped.
- Marking a pending, fully paid order as shipped succeeds, and the order shows as shipped when viewed again.
- A paid amount equal to the full total permits shipping; zero or partial payment, a cancelled order, and any other non-pending order are rejected without changing status or payment values.
- Marking a missing or already-shipped order as shipped returns JSON 404 with the exact error `Pending order not found`, and changes nothing.
- A failed shipping attempt can be retried after the test fixture satisfies the full-payment condition; successful status remains persisted after restart.

### BR-09: Order retrieval

A user shall be able to view an order by its ID and list all orders. A viewed order shall show its status, timestamp, and the prices and discounts that applied at placement.

Viewing a placed order shall show the same details as at placement. The order list shall be empty before any order is placed, and shall include every placed order afterward. A viewed line shall keep the unit price and discount that applied at placement; for example, 10 `REPOTTING-DAY` packs shall still show a unit price of $18.00 and a 10% discount after the catalog price changes.

Complete order, line, financial, timestamp, and status snapshots shall remain stable across repeated retrievals and application/database restart. The order list shall return each order once in ascending order ID; an unknown order ID shall return a JSON 404 error.

Edge cases:

- Viewing a placed order shows the same details as when it was placed.
- The order list shows every placed order, and is empty before any order is placed.
- Multiple-line order snapshots, including financial values, remain unchanged after catalog or policy changes and after restart.
- Repeated list/detail retrievals do not duplicate orders or change their values; unknown IDs remain not found.

### BR-10: Order lookup

A user shall be able to see what orders have been placed by clicking on the Orders button to render the Orders page frame. Each time the Orders page is shown, the application shall automatically retrieve the current order list through the REST API and display it, so the user is not required to click the Refresh Orders button. The existing manual Refresh Orders action shall remain available. Order retrieval shall follow BR-04's requirements for non-blocking network requests, applying results on the interface thread, and displaying API or connection errors in the status message.

Edge cases:

- When orders exist, opening or returning to the Orders page displays the latest order list without requiring a manual refresh.
- When no orders exist, the Orders page displays a valid empty list rather than treating the empty result as an error.
- If the automatic order request fails, the GUI displays the API error or connection failure in its status message and remains responsive.
- The page frame is visible on entry, each entry triggers a fresh API request, and the manual `Refresh orders` control continues to work.

### BR-11: Place order inventory dropdown

A user shall not have to memorize the complete list of SKUs for the inventory. The Place Order page shall provide a dropdown populated from the product catalog retrieved through the REST API. Each choice shall identify the product and, when the display includes a product name, retain the corresponding exact SKU for order submission. Selecting a product and submitting an order shall preserve the existing quantity and order-placement behavior. Product selection shall not bypass the API's inventory validation.

Edge cases:

- The dropdown contains the products returned by the catalog, and selecting an option submits that product's exact SKU rather than its display label.
- Each option identifies the product and includes the exact SKU when its product name is displayed; the dropdown starts without an implicit selection.
- Retrieving the product catalog on Inventory-page entry or after a successful order updates the dropdown choices.
- An empty catalog leaves no invalid product selected and is presented as an empty state; the GUI shall not submit an order without a selected product.
- If loading the catalog fails, the GUI displays the API error or connection failure using the existing status message.
- Selecting a product with zero stock does not bypass the API's insufficient-stock validation or appear to create a successful order.

# Sprint 3

### BR-12: Customer management

A Customer record shall contain the fields defined in the Business Vocabulary: full name; street number and street name; city; state; postal code; country; phone country code; and phone number. Customer records shall be stored persistently in the database.

The Order Entry page shall allow a user to enter Customer details for an order. A successfully placed order shall be associated with the Customer record entered for it. The Customer page shall provide a `Create Customer` button to save a Customer independently of placing an order, and shall display customers associated with at least one successfully placed order. A Customer created without an order shall remain stored but shall not appear in the purchased-customer list until associated with a successful order.

Customer fields entered on the Order Entry page and through the `Create Customer` action shall use the same validation rules. BR-12 does not impose customer deduplication or merging based on matching field values.

Validation rules:

- Every Customer field is required and shall be a string containing non-whitespace text.
- Leading and trailing whitespace shall be removed before values are stored. A value that is empty after trimming shall be rejected.
- Phone country code and phone number are separate required text fields. Phone punctuation and formatting shall be preserved; no country-specific phone length or formatting rule is imposed.
- Postal codes shall be treated as text and preserved, including leading zeroes, letters, spaces, or hyphens.
- Invalid Customer data shall be rejected without saving a partial Customer record. If invalid data is submitted with an order, the application shall not create the order or change inventory.

Validation use cases:

- A complete Customer with valid text values for every required field can be saved through `Create Customer`.
- A complete Customer entered on Order Entry can be associated with a successfully placed order and appears in the purchased-customer list.
- Omitting any required field, providing a non-string value, or entering only whitespace for a field is rejected with clear validation feedback.
- A Customer with an international-style name, address, postal code, or phone formatting is accepted when the required fields contain non-whitespace text; the application does not apply a country-specific format rule.

Edge cases:

- Missing, null, empty, and whitespace-only values are rejected independently for each required field.
- A field containing surrounding whitespace is trimmed before saving; internal whitespace is preserved.
- Postal codes such as `"00123"` and `"A1B 2C3"` are preserved as text rather than converted to numbers.
- Phone values such as `"+1"` and `"(555) 123-4567"` are accepted and stored with their supplied formatting when both phone fields are present.
- A validation failure in one field leaves no partial Customer record; for Order Entry it also leaves order records and product stock unchanged.
- A Customer saved through `Create Customer` without a successful order remains persisted but is not shown as a customer who has purchased.
- Matching Customer details do not cause rejection or automatic merging; each successful create action saves its own record.

### BR-13: GUI navigation and inventory refresh

BR-13 modifies the GUI requirements in BR-04. The horizontal navigation row shall display a `View:` label immediately before the `Inventory`, `Place Order`, and `Orders` buttons. The label shall identify the buttons as page-navigation controls; each button shall continue to display its named page.

The Inventory page shall not display a `Refresh inventory` button. The catalog shall continue to refresh automatically whenever the Inventory page is shown or revisited, and after a successful order. Catalog refresh results shall update both the Inventory table and the Place Order dropdown, as specified in BR-11. The existing manual `Refresh orders` action on the Orders page is unchanged.

Validation use cases:

- On application launch, the navigation row displays `View:` immediately before the three page buttons, and the Inventory page is shown.
- Selecting `Inventory`, `Place Order`, or `Orders` displays the corresponding page without hiding or replacing the `View:` label or navigation buttons.
- Entering or returning to Inventory retrieves the current catalog and updates the inventory table and product dropdown.
- After a successful order, inventory and dropdown values are refreshed without requiring a manual inventory-refresh control.
- The Orders page continues to provide its manual `Refresh orders` action.

Edge cases:

- The `View:` label is visible once in the navigation row and does not replace, overlap, or disable any page button.
- The Inventory page has no `Refresh inventory` button; navigating away and returning remains a way to request the catalog again.
- If an automatic catalog request fails, the existing status message displays the failure and the GUI remains responsive; returning to Inventory triggers another request.
- Removing the Inventory refresh button does not remove the automatic refresh after order placement or change the independent Orders refresh behavior.