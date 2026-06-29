# Release Checklist

## Pre-release
1. Install dev dependencies: `pip install -r requirements-dev.txt`
2. Run lint: `ruff check .`
3. Run format: `ruff format .`
4. Run type check: `mypy .`
5. Validate migration files in `migrations/`.
6. Update `CHANGELOG.md`.

## Staging
1. Deploy to staging environment.
2. Verify `/health` and `/ready`.
3. Verify `/admin health` and `/admin test-alert`.
4. Run smoke test of critical commands.

## Production
1. Merge to `main`.
2. Deploy production.
3. Verify `/ready` and bot gateway session.
4. Monitor logs and owner DM alerts for 15 minutes.
