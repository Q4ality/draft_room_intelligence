# Development Workflow

## Branches

- main is the stable, release-ready branch. Do not develop directly on it.
- dev is the shared integration branch for completed, verified work.
- Create focused work branches from dev, using the codex/ prefix where applicable.

## Normal flow

1. Update local dev from origin/dev.
2. Create a focused branch from dev.
3. Implement and run checks relevant to the change.
4. Open a pull request from the work branch into dev; merge after review and checks pass.
5. Open a pull request from dev into main only for a deliberate release or stable milestone.
6. Review that promotion manually, verify release checks, and merge it manually. Do not automatically merge dev into main.

## Required checks

Before a pull request, run this PowerShell command:

    .\scripts\check-local.ps1

It runs the test suite, rebuilds the pinned longitudinal baseline, and writes an offline-safe ingestion-lineage audit. It does not refresh or overwrite provider data.

## Keeping main protected

Configure the GitHub main branch rule to require pull requests and passing checks, and disable direct pushes. Keep merge approval manual; do not enable automatic merge from dev.
