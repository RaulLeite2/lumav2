# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [2026-06-29]
### Added
- Runtime owner alerting via DM with context and traceback.
- Health/readiness HTTP endpoints (`/health`, `/ready`).
- Admin diagnostics command improvements with readiness flags and modules/cogs status.
- Manual alert validation command (`/admin test-alert`) with non-error logging mode.
- Global app-command rate limiting per guild/command with metric counters.
- Additional hot-query indexes migration (`019_add_hot_query_indexes.sql`).
- Developer tooling baseline: Ruff, MyPy, pre-commit.
- SLO and operational runbook documents.

### Changed
- App-command errors now use internal error codes and safer user-facing messages.
- SQL migration loader now tolerates UTF-8 BOM.
- Debug print statements in cogs replaced by structured logging.

### Fixed
- BOM-related Postgres syntax failure in migration `017_seed_standard_tosco_shop_catalog.sql`.
