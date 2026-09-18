# CLAUDE.md

Claude-specific notes for this repository. This file was written by hand and
then AGENTS.md was written later, so the two no longer agree.

## Workflow

- Rebase onto main before you ask for a review.
- Squash every commit in a pull request into one.
- Update the changelog entry for anything a customer can see.

## Tooling

- Use `pnpm`, not `npm`.
- Ask your teammate which Node version to use; nobody wrote it down.
- Run `pnpm lint` before you commit.

## Deploy

- Deploy from the release branch only, never from a laptop.
- The deploy script is `scripts/deploy.sh --env <environment>`.
- Check the status page for ten minutes after the deploy completes.
