# Staging Environment Guide

## Objective
Run a separate staging bot and database before promoting changes to production.

## Minimum setup
- Create a second Discord application/bot token for staging.
- Create a separate Postgres database for staging.
- Create a separate deployment service (Railway recommended) for staging.

## Required environment variables
- `TOKEN` (staging bot token)
- `DATABASE_URL` (staging database)
- `OWNER_ALERT_USER_ID` (can be same owner)
- `LOG_LEVEL=INFO`
- `COMMAND_RATE_LIMIT_PER_GUILD`
- `COMMAND_RATE_LIMIT_WINDOW_SECONDS`
- `SHARD_COUNT` (optional)

## Deployment recommendations
- Service name example: `luma-staging`
- Branch strategy: deploy from `develop` or `staging`
- Keep production deploying from `main`

## Validation checklist
1. `GET /health` returns 200.
2. `GET /ready` returns 200 after startup.
3. `/admin health` shows DB/Discord/Migrations ready.
4. `/admin test-alert` delivers DM test alert.
5. Core commands (`/setup`, `/mod warn`, `/ask`) execute normally.

## Promotion to production
1. Merge tested staging branch into `main`.
2. Create release note in `CHANGELOG.md`.
3. Deploy production.
4. Validate `/ready` and key slash commands.
