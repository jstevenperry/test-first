# Houseplant Correspondence Company

This repository is the requirements and prompt source for an MVP of the Houseplant Correspondence Company (HCC), a small stationery-catalog and order-management application. The MVP is intended to be generated in Python, with a SQLite database, an HTTP/JSON REST interface, and a Tkinter desktop client.

The project is deliberately requirements-first: the business requirements define the application's observable behavior, and the sprint prompts guide an AI coding assistant through planning and implementing that behavior test-first. The repository's core source is the requirements and prompts; generated application code and tests belong under `generated/`.

## Repository contents

```text
src/
  spec/
    no-code-business-requirements.md
  prompt/
    generate-sprint-1-execution-plan.md
    execute-sprint-1.md
    generate-sprint-2-execution-plan.md
    execute-sprint-2.md
    generate-sprint-3-execution-plan.md
    execute-sprint-3.md
generated/
  spec/       # Sprint execution plans produced from the planning prompts
  tests/      # Requirement-specific Python unittest modules
  ...         # Generated Python application modules
```

`src/spec/no-code-business-requirements.md` is the behavioral source of truth. It defines the business vocabulary, product and order behavior, validation, financial calculations, API responses, GUI behavior, and sprint boundaries. The sprint prompts refer back to this document; execution prompts also use the corresponding generated sprint plan.

## MVP sprint scope

| Sprint | Business requirements | Main capabilities |
| --- | --- | --- |
| Sprint 1 | BR-01–BR-05 | Product catalog and validation, exact money calculations, REST interface, Tkinter client, and validated/atomic order placement |
| Sprint 2 | BR-06–BR-11 | Consistent product lookup, order snapshots and retrieval, paid-order shipping transition, automatic order refresh, and catalog-backed product selection |
| Sprint 3 | BR-12–BR-13 | Persistent customer management and order association, customer entry/listing, and GUI navigation/catalog refresh behavior |

Requirements are intentionally partitioned by sprint. When executing a sprint, follow only that sprint's scope; later requirements can be placeholders or subject to change.

## Intended workflow

For each sprint:

1. Read `src/spec/no-code-business-requirements.md` and the sprint-specific prompt.
2. Run `generate-sprint-N-execution-plan.md` to produce `generated/spec/sprint-N-execution-plan.md`. The plan should describe implementation order and explicitly enumerate requirement edge cases.
3. Run `execute-sprint-N.md` to implement that plan. Write requirement-specific `unittest` tests under `generated/tests/` before writing implementation modules under `generated/`.
4. Ensure every business requirement in the sprint has tests, cover its stated and identified edge cases, and run the sprint tests together with prior sprint regressions.
5. Update the business requirements document if additional edge-case requirements are discovered, as directed by the execution prompt. A sprint is not complete until its tests execute successfully.

Test modules are expected to use the BR identifier in their filenames, for example `generated/tests/test_br_01.py`. The generated application is expected to expose convenient Python entry points for running its REST server and desktop GUI; consult the requirements for their specific behavior and invocation.

## Product behavior at a glance

- The initialized catalog contains First Sprout Card Pack (`FIRST-SPROUT`), Repotting Day Card Pack (`REPOTTING-DAY`), and Windowsill Notes Journal (`WINDOWSILL-JOURNAL`).
- Accepted orders reserve available inventory, combine duplicate product lines, and retain financial snapshots from order placement.
- Monetary arithmetic uses exact decimal/cent values and half-up rounding, rather than binary floating-point for business calculations.
- The REST interface provides product and order operations, and later sprint requirements add customer and shipping operations.
- The Tkinter client uses the REST interface for business operations and is designed for a trusted local endpoint.

## Security and network scope

The requirements explicitly describe the REST interface as unsecured and intended for trusted local use. It binds to `127.0.0.1` by default. Do not expose it to a shared or public network: authentication, authorization, and transport security are outside this MVP's stated scope.

## Runtime and tests

This repository is a specification-and-prompt project, not a packaged Python distribution. It does not define a package installer, dependency lockfile, or root-level test command. The implementation prompts specify Python's standard `unittest` framework and generated output locations. Once generated, run the tests with Python's unittest discovery from the repository root, for example:

```sh
python3 -m unittest discover -s generated/tests -v
```

The generated application is expected to use Python's standard library, including `sqlite3`, `http.server`, and `tkinter`, unless its implementation plan documents an approved change.
