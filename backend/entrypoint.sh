#!/bin/bash
set -e

echo "==> Running demo seed..."
python scripts/run_migrations.py
python scripts/seed_demo.py || echo "==> Demo seed failed; starting Flask anyway."

echo "==> Starting Flask..."
exec python app.py
