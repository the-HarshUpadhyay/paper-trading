# README FIRST

This file documents the exact changes made to restore reliable demo-user seeding and startup for the Docker app.

## What Changed

### 1. Backend startup now runs migrations before demo seeding

File changed: [backend/entrypoint.sh](/D:/DBS/paper-trading/backend/entrypoint.sh)

Previous behavior:
- The container tried to run `scripts/seed_demo.py` immediately on startup.
- Newer schema objects such as `watchlist_folders` could still be missing at that point.
- That made demo seeding fail on fresh environments or partially migrated databases.

New behavior:
- The container now runs `python scripts/run_migrations.py` first.
- After migrations complete, it runs `python scripts/seed_demo.py`.
- If demo seeding fails, Flask still starts instead of the backend dying completely.

Current startup flow:

```bash
python scripts/run_migrations.py
python scripts/seed_demo.py || echo "==> Demo seed failed; starting Flask anyway."
python app.py
```

## 2. Migrations were extracted into a reusable app helper

File changed: [backend/app.py](/D:/DBS/paper-trading/backend/app.py)

Changes made:
- Added a module-level `MIGRATIONS` list:
  - `001_notes.sql`
  - `002_watchlist_folders.sql`
  - `003_pending_orders.sql`
  - `004_alerts.sql`
- Added `apply_migrations()` to run that list in one place.
- Updated `create_app()` to call `apply_migrations()` instead of duplicating the migration loop inline.

Why:
- This allows the same migration logic to be reused both:
  - during normal app startup
  - and from a standalone pre-seed script

## 3. Added a dedicated migration runner script

New file: [backend/scripts/run_migrations.py](/D:/DBS/paper-trading/backend/scripts/run_migrations.py)

What it does:
- initializes the Oracle pool
- imports `apply_migrations()` from `app.py`
- runs backend migrations before demo seeding
- prints clear startup markers in container logs

Why:
- `entrypoint.sh` needed a simple pre-seed command that could apply all current backend migrations without booting the whole Flask app first.

## 4. Demo seeding was made more defensive

File changed: [backend/scripts/seed_demo.py](/D:/DBS/paper-trading/backend/scripts/seed_demo.py)

Changes made:
- Added `_table_exists(...)`
- Added `_column_exists(...)`
- Added `_trigger_exists(...)`

These helpers are now used to make seeding safer when schema state varies.

Specific behavior changes:
- The cleanup step now skips missing tables instead of crashing.
- `watchlist_folders` is only cleared if it exists.
- trigger disabling only happens if the `transactions` table exists and the trigger exists.
- watchlist folder seeding only runs if:
  - `watchlist_folders` exists
  - and `watchlist.folder_id` exists
- if folder support is missing, watchlist items are still seeded as uncategorised entries instead of failing.

Why:
- This makes the demo seed much more tolerant of partial schema drift and prevents a single missing table from killing the full demo-data restore.

## Why This Fix Was Needed

The root issue was startup ordering.

The backend had newer features that depended on migration-created tables, but demo seeding could run before those migrations existed in the active database. That caused failures like `ORA-00942: table or view does not exist`, which in turn made the app appear broken or left the seeded account missing.

## Result

After these changes:
- the backend starts even if demo seeding has a problem
- migrations are applied before seeding
- the demo account seeds reliably on the current schema
- the demo credentials are:

```text
username: test
password: 123456
```

## Verified Outcome

The running app was verified after restart with:
- successful backend startup logs showing migration + seed completion
- successful login for `test / 123456`
- seeded demo portfolio with `12` holdings
- seeded watchlist with `10` items across `2` folders
- seeded cash balance of `1180015.0`

## Files Touched For This Fix

- [backend/entrypoint.sh](/D:/DBS/paper-trading/backend/entrypoint.sh)
- [backend/app.py](/D:/DBS/paper-trading/backend/app.py)
- [backend/scripts/run_migrations.py](/D:/DBS/paper-trading/backend/scripts/run_migrations.py)
- [backend/scripts/seed_demo.py](/D:/DBS/paper-trading/backend/scripts/seed_demo.py)

## Manual Reseed Command

If the demo user ever needs to be restored manually:

```powershell
docker compose exec -T backend python scripts/seed_demo.py
```


## Changes Implemented

This update includes a focused cleanup and reliability pass across the backend, database setup, scheduler flow, and project documentation.

### 1. Starting Balance Normalized
The project now consistently uses a starting balance of:

`10_000_000.00` INR

This has been aligned across:
- `backend/config.py`
- `backend/services/auth_service.py`
- `database/04_sample_data.sql`
- seed/demo account setup
- README and related documentation

The app is now documented as an **INR / NSE-first paper trading platform**, and stale USD-based balance references were updated accordingly.

### 2. Safer Notification Mark-As-Read Logic
`backend/services/alert_service.py` was refactored to remove the fragile dynamic SQL placeholder pattern previously used in `mark_read`.

What changed:
- replaced dynamic `IN (...)` placeholder construction
- switched to a fixed SQL statement with bound parameters via `executemany(...)`
- preserved existing behavior while improving safety and maintainability

### 3. Pending Order Semantics Reviewed and Clarified
`backend/services/pending_order_service.py` was reviewed for order-trigger behavior.

What changed:
- `STOP_LIMIT BUY` behavior was validated against standard trading semantics
- clarifying comments were added to explain:
  - `LIMIT BUY`
  - `LIMIT SELL`
  - `STOP BUY`
  - `STOP SELL`
  - `STOP_LIMIT BUY`
  - `STOP_LIMIT SELL`

Result:
- the breakout-style `STOP_LIMIT BUY` logic is now explicitly documented and easier to understand

### 4. Price Cache Limitation Documented
`backend/services/cache.py` now clearly documents that the current `price_cache` is:

- in-memory
- process-local
- safe for single-process deployments
- not suitable for multi-worker production scaling without a shared cache such as Redis

This does not change runtime behavior, but it makes the deployment limitation explicit and provides a clear migration direction for future scaling.

### 5. Faster Scheduler Pickup for New Tickers
`backend/services/scheduler.py` was improved so newly tracked stocks do not need to wait for the full ticker refresh cycle.

What changed:
- added `notify_ticker_added(ticker)`
- allows newly bought stocks or newly added watchlist stocks to be registered immediately
- reduces the delay before price refresh begins for newly tracked symbols

This keeps the scheduler lightweight while improving responsiveness for watchlist and trading flows.

### Overall Impact
These changes improve:
- consistency of financial defaults
- backend SQL safety
- clarity of pending-order behavior
- deployment transparency for caching
- refresh responsiveness for newly tracked stocks

The update is intentionally conservative and does not introduce unnecessary architectural churn.



