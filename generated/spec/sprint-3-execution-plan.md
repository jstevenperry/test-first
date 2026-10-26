# Sprint 3 Execution Plan

## Scope

Implement only Sprint 3 requirements BR-12 and BR-13 from `src/spec/no-code-business-requirements.md`. BR-12 adds persistent customer records and their use in order entry, the standalone Create Customer action, and the purchased-customer list. BR-13 confirms navigation and inventory-refresh behavior across Inventory, Place Order, and Orders.

Do not introduce requirements beyond BR-12 and BR-13. In particular, do not add customer deduplication/merging, country-specific address or phone validation, new inventory refresh controls, or changes to existing order and policy behavior unless needed to satisfy these BRs.

## Execution strategy

1. Inspect the current database, REST API, GUI, and Sprint 1/2 tests. Identify how order creation and stock updates are transactionally coupled, how the current Place Order page is represented, and what persistent GUI test doubles already exist.
2. Write the BR-12 and BR-13 tests before implementation in `generated/tests/test_br_12.py` and `generated/tests/test_br_13.py`. Test customer persistence/API or service behavior and GUI behavior with deterministic database fixtures and Tk/network test doubles.
3. Run these tests against the current implementation to establish missing behavior. Include rollback and purchased-customer association assertions; do not introduce speculative customer formatting rules.
4. Implement customer schema and persistence first, then integrate customer validation and association into order placement, then implement the Customer page and Create Customer action. Keep Customer form validation shared between standalone creation and order entry.
5. Implement or adjust only the BR-13 navigation/catalog refresh behavior after BR-12 integration, preserving existing Inventory and Orders workflows.
6. Run all new tests and the full Sprint 1/Sprint 2 regression suite. Follow the requirements-document limit of no more than two automatic attempts to fix a failing issue; report any unresolved failures instead of claiming completion.

## BR-12: Customer management

### Planned tests

Use `test_br_12.py` to verify the customer model and database persistence, validation and trimming, standalone customer creation, purchased-customer filtering, successful order association, and failure atomicity. Exercise both service-level operations and REST/GUI paths as supported by the existing application architecture.

### Edge cases to cover

- Persist the complete required customer data: full name, street number and name, city, state, postal code, country, phone country code, and phone number.
- Every required field is validated independently. Missing, `null`, empty, whitespace-only, and non-string values are rejected with clear validation feedback.
- Leading and trailing whitespace is trimmed before storage; internal whitespace remains unchanged.
- Postal code is text: preserve values such as `"00123"` and `"A1B 2C3"` without numeric conversion or normalization.
- Phone country code and phone number are distinct required strings. Accept `"+1"` and `"(555) 123-4567"` with punctuation intact; do not impose country-specific formatting or length rules.
- Accept international-style names and address text when required fields are non-whitespace strings.
- A valid customer may be saved using the standalone `Create Customer` action before an order exists. It remains stored but is absent from the purchased-customer list until associated with a successful order.
- A successfully placed order associates the submitted customer record, and the customer appears in the purchased-customer list.
- If customer validation fails during standalone creation, no partial customer row is persisted.
- If customer validation fails during order placement, no customer/order row is partially persisted and product stock is unchanged.
- Repeated successful create actions with identical field values create separate customer records; no automatic deduplication or merging is applied.
- Customer creation and order-entry customer fields use the same validation and normalization rules.

## BR-13: GUI navigation and inventory refresh

### Planned tests

Use `test_br_13.py` to verify navigation layout and transitions, automatic catalog refreshes, inventory/dropdown synchronization, and retention of the Orders refresh action. Exercise startup and post-order refresh paths using GUI doubles and controlled asynchronous responses.

### Edge cases to cover

- The `View:` label appears exactly once immediately before the `Inventory`, `Place Order`, and `Orders` navigation buttons.
- On launch, Inventory is visible. Each navigation button continues to display its matching page without replacing, hiding, or disabling the navigation row.
- There is no `Refresh inventory` button. Leaving and returning to Inventory automatically requests the current catalog.
- A successful order automatically refreshes the catalog and updates both the Inventory table and product dropdown.
- Inventory refresh failures appear in the existing status message, do not freeze or disable navigation, and can be retried by returning to Inventory.
- The Orders page retains its manual `Refresh orders` action and its existing automatic refresh behavior.
- Test stale/out-of-order catalog responses so an older result cannot replace data from the most recently requested refresh, preserving existing refresh ordering behavior.

## Completion checks

- Every validation, persistence, association, filtering, and navigation edge case above has one or more BR-traceable assertions.
- Verify a standalone customer is persistent but not presented as purchased until an accepted order is associated.
- Verify failed customer/order submissions preserve database and inventory state.
- Verify order creation using customer data continues to use the existing inventory transaction semantics.
- Verify the Inventory table and dropdown show the same current catalog after automatic refresh; the Orders refresh remains independent.
- Run BR-12 and BR-13 tests together with all earlier BR tests.
- Confirm no customer deduplication, country-specific validation, manual inventory refresh control, or unrelated feature was introduced.
