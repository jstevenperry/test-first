# Sprint 2 Execution Plan

## Scope

Implement only Sprint 2 requirements BR-06 through BR-11 from `src/spec/no-code-business-requirements.md`. Sprint 2 extends the Sprint 1 product, order, REST, and Tkinter behavior with product lookup consistency, complete order snapshots, shipping transitions, durable order retrieval, automatic Orders-page refresh, and a catalog-backed order dropdown.

Do not implement Sprint 3 requirements BR-12 or BR-13. In particular, do not add customer management or use BR-13 as scope for navigation or inventory-refresh changes. Preserve already-required Sprint 1 behavior and test any Sprint 1 surface changed by this sprint.

## Execution strategy

1. Inspect the current generated implementation and test suite before editing. Reuse its database, API, money, and GUI patterns. Confirm how test fixtures control order rates, payment values, database restarts, and asynchronous GUI responses.
2. Add requirement-traceable tests before changing implementation. Use dedicated `test_br_06.py` through `test_br_11.py` modules under `generated/tests/`, or extend existing BR-specific modules where an API/GUI integration check needs shared setup; keep every case traceable to its BR.
3. Run the new tests against the current implementation to establish failures. Use temporary databases, controlled rate/payment fixtures, and deterministic HTTP/UI test doubles. Do not introduce a public policy-management, payment, or cancellation API: fixtures may arrange non-default rates or payment state only to test required outcomes.
4. Implement shared domain and persistence changes first, then HTTP behavior, then GUI integration. Keep error shapes/status codes and thread-safe GUI result handoff consistent with Sprint 1.
5. Run all Sprint 2 tests plus the existing Sprint 1 regression suite. Fix regressions without exceeding the source requirements' limit of two automatic fix attempts per failing issue. Report any unresolved failures rather than treating the sprint as code complete.

## BR-06: Product lookup

### Planned tests

Exercise lookup and order placement through the REST API, asserting the exact error text, response status, and unchanged persistent state after a failed order.

### Edge cases to cover

- `GET /products/UNKNOWN` returns HTTP 404 and JSON `{"error": "Unknown product"}`.
- Placing an order containing `UNKNOWN` returns the same HTTP 404 and exact error.
- A request with a valid product line followed by an unknown SKU fails atomically: no order is saved and no product stock changes.
- Product lookup and placement use the same unknown-product wording and behavior; do not add a quote endpoint.

## BR-07: Order creation

### Planned tests

Verify order calculations and snapshots at the domain/database and REST layers. Arrange controlled policy fixtures for the specified non-zero discount/tax cases without exposing a public policy-management interface.

### Edge cases to cover

- Ten `REPOTTING-DAY` units produce one line, pre-discount unit price `$18.00`, 10.00% discount, and subtotal/total `$162.00` under zero tax and shipping.
- Two `FIRST-SPROUT` units plus one `WINDOWSILL-JOURNAL` unit produce two correctly priced lines and subtotal `$49.00`.
- A mixed order of ten discounted `REPOTTING-DAY` units and one undiscounted `FIRST-SPROUT` unit has subtotal `$174.50`; the discount applies only to the eligible product.
- Two duplicate five-unit `REPOTTING-DAY` lines combine before discount evaluation into one ten-unit line and subtotal `$162.00`.
- Under 10.00% discount and tax, the ten-unit `REPOTTING-DAY` line has `$16.20` tax and `$178.20` line total.
- A `$0.05` extended line discounted at 10.00% rounds the half-cent discount to `$0.01`; a `$0.05` net line taxed at 10.00% rounds tax to `$0.01`.
- Duplicate lines are aggregated before stock validation. If the combined quantity exceeds stock, reject the entire order without changing stock or creating an order.
- Duplicate SKU aggregation retains the SKU's first input position. Persisted order and line financial snapshots reconcile and remain the values calculated at acceptance.
- A line with no discount retains the zero discount rate and its undiscounted value.

## BR-08: Shipping status

### Planned tests

Test `POST /orders/{id}/ship`, its HTTP responses, state transitions, and persistence. Use controlled database fixtures to represent full payment because Sprint 2 does not introduce payment or cancellation operations.

### Edge cases to cover

- Supplying `shipped: true` at order creation still creates a pending, unshipped order.
- A pending order with paid amount equal to its full total ships successfully; response is the complete updated order and subsequent detail retrieval reports shipped.
- Zero or partial payment does not permit shipping. Failed attempts preserve status and all payment values.
- Cancelled and any other non-pending order cannot ship and remains unchanged.
- Missing and already-shipped order IDs return HTTP 404 with exact JSON error `Pending order not found`; the request changes nothing.
- An unpaid shipping attempt fails, then succeeds after its test fixture is adjusted to full payment.
- Shipped status survives closing and reopening the application/database.
- An ineligible existing order returns HTTP 409; errors have the standard JSON `error` body.

## BR-09: Order retrieval

### Planned tests

Exercise empty and populated order-list responses, detail retrieval, snapshots, and persistence across database reopen using both the API and storage layer.

### Edge cases to cover

- Listing orders before any placement returns an empty array; after placement it contains each order exactly once.
- Detail retrieval returns the same full order, line, financial, timestamp, and status values as placement.
- Catalog price or policy changes after placement do not rewrite stored line prices, discounts, totals, or other financial snapshots.
- Multiple-line order snapshots are stable across repeated detail/list requests and application/database restart.
- Order listing remains in ascending `order_id` order and contains no duplicate entries after repeated retrieval.
- An unknown order ID returns JSON 404.

## BR-10: Order lookup in the GUI

### Planned tests

Use GUI test doubles and controlled REST responses to verify Orders-page navigation, automatic/manual retrieval, result application on the UI thread, and errors without requiring a live display or network.

### Edge cases to cover

- Every entry to or return to the Orders page shows the page frame and automatically requests a fresh order list; a manual `Refresh orders` action remains available and functional.
- Existing orders are displayed on automatic page entry without requiring the manual refresh action.
- An empty response is rendered as a valid empty list, not an error.
- An API error or connection failure is shown in the status message while the interface remains responsive.
- Requests remain non-blocking; worker results are handed to the interface thread, and an older same-page refresh result cannot overwrite the latest requested result.

## BR-11: Place-order catalog dropdown

### Planned tests

Verify catalog-backed dropdown population, selected SKU submission, empty/error states, and refresh integration with the Inventory view and successful order flow.

### Edge cases to cover

- Dropdown choices correspond to products returned by the catalog API, identify each product, and submit the exact SKU even if the displayed choice includes its product name.
- The dropdown begins with no implicit selection; a user must choose a product before submitting.
- Returning to Inventory or refreshing it after a successful order updates both the inventory table and dropdown choices.
- An empty catalog leaves no product selected and cannot submit an order.
- A catalog-loading error is shown through the existing status message.
- Selecting a zero-stock product does not bypass server-side inventory checks or appear successful when the API rejects the order.
- Existing quantity and order placement behavior remains unchanged; the request contains the selected exact SKU and selected quantity.

## Completion checks

- Each new test module maps clearly to its corresponding BR, and every edge case listed above has at least one assertion.
- Verify both successful and failed shipping transitions against durable state, not only response payloads.
- Verify order snapshots after restart and ensure failed unknown-product/stock/shipping operations do not alter protected data.
- Verify GUI page-entry fetches, manual refresh, status errors, empty states, dropdown selection, and out-of-order response handling.
- Run the full BR-06–BR-11 tests and the existing Sprint 1 regression tests together.
- Confirm no Sprint 3 feature or policy/payment management endpoint was added.
