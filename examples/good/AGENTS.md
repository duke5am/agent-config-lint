# AGENTS.md

This repository is the checkout service: a TypeScript API, a small Python
service, and the integration tests that pit them against each other.

## Commands

Run these from the repository root.

- Install dependencies with `npm ci`.
- Run `npm test` before you commit. It is the same command CI runs.
- Run `npm run lint:fix` to apply the formatting that CI enforces.

## TypeScript

Rules for the API live in `.cursor/rules/typescript.mdc`; the essentials:

- Use two-space indentation and a semicolon at the end of every statement.
- Do not use the `any` type. Use `unknown` and narrow it at the boundary.
- Import the HTTP client from `src/api/client.ts`; do not call `fetch`
  directly, because the client attaches the retry policy.

## Python

Rules for the scheduler live in `.cursor/rules/python-service.mdc`.

- Format with `black` and lint with `ruff` before you commit.
- Annotate every function signature in `src/services/`.

## Tests

- Put a regression test next to the change it protects, under `tests/`.
- Name the test after the behaviour, not the function: `test_rejects_expired_token`.
- The integration suite in `tests/integration/` needs `npm ci` to have run first.

## Pull requests

- Keep one behaviour change per pull request.
- Add the file or directory you touched to the pull request description when the
  change crosses the API boundary.
