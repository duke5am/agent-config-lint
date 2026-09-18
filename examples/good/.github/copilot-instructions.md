---
globs: '**/*.{ts,tsx}'
alwaysApply: false
---

# Code review guidance

- Create pure functions and modules, and keep side effects inside
  `src/api/handlers.ts`.
- Prefer `const` over `let`; only use `let` when the binding is reassigned.
- Explain a non-obvious decision in a comment above the line it affects.
