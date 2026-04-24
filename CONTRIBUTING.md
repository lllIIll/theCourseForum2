# Contributing to theCourseForum2

Welcome. This file explains how to set up a working environment, what we expect on every PR, and where to look for deeper context.

## Setup

Setup, environment variables, Docker, database restore, and migrations are documented in [doc/dev.md](doc/dev.md). Read it once before making any changes.

For the layout of the codebase, what lives where, and how data flows from the SEAS scraper through Supabase into the Django models, read [doc/architecture.md](doc/architecture.md).

For useful management commands (loading semesters, grades, labs, reviews), see [doc/useful-commands.md](doc/useful-commands.md).

## Branching

- New work branches off `dev`. Production-grade work merges into `dev`. `dev` merges into `main` for releases.
- Feature branches use a short, descriptive name (e.g. `LabForum1`, `schedule-share-fix`). No personal-name prefixes.
- Do not commit directly to `main` or `dev`. Open a PR.

## Before you push

These commands must succeed locally before you push. CI runs the same checks; running them first saves a round trip.

```bash
# Run the full Django test suite
docker exec tcf_django python manage.py test

# Verify migrations are in sync with models
docker exec tcf_django python manage.py makemigrations --check --dry-run

# Run the linters CI runs
docker exec tcf_django python -m pylint tcf_website tcf_core
docker exec tcf_django python -m black --check tcf_website tcf_core
docker exec tcf_django python -m isort --check tcf_website tcf_core

# Frontend lint (only if you touched JS or templates)
docker compose run --rm web npx eslint -c .config/.eslintrc.yml tcf_website/static/js
```

If a lint fails, fix it. Do not push with failing lints. If a check is wrong (genuine false positive), document the reason in the PR and add a per-line `# pylint: disable=...` rather than a global suppression.

## Pull requests

- Title under 70 characters. Imperative mood. "Add X", "Fix Y", not "Adding X" or "X added".
- Description has a one-paragraph summary and a test plan. Screenshots for UI changes.
- One concern per PR. If you find an unrelated bug while in the file, open a separate PR for it.
- Squash-merge by default. Commit history within the branch is for review; the squash commit is what lives forever.

## Commit messages

- First line: short imperative summary, under 70 chars.
- Body wrapped at ~72 chars. Explain the *why*, not the *what*. The diff shows the what.
- No `Co-Authored-By:` lines unless a real human collaborator was involved.

## Models, migrations, and data

- New models or field changes require a migration. Run `python manage.py makemigrations` and commit the generated file alongside the model change.
- Migrations should be reversible. Avoid raw SQL unless you genuinely need it; if you do, write the reverse SQL too.
- The `tcf_website/models/` package is split by domain (course, review, lab, user, club, question, schedule). Add new models to the existing submodule that fits, or create a new submodule if you have a clean new domain. New code should `from tcf_website.models.lab import Lab` rather than `from tcf_website.models import Lab` so the dependency is legible.
- For lab-data scraping and Supabase staging, see [scripts/lab_scraper/README.md](scripts/lab_scraper/README.md). Always run the scraper's safety-gated diff tool before applying changes to production data.

## Tests

- Tests live in `tcf_website/tests/`. One file per feature surface (`test_lab_models.py`, `test_lab_views.py`, etc.). Match the pattern.
- Use `setUp` to build the minimum fixtures the test needs. Do not pull in shared global fixtures.
- New code without tests is a yellow flag. Bug fixes without a regression test are a red flag.

## Asking for help

If you are stuck, ask in the team Discord before fighting alone for an hour. Sharing the diff and the error is faster than describing the symptom.
