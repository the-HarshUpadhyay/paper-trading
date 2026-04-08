#!/bin/bash
set -e

echo "==> Running demo seed..."
python scripts/seed_demo.py

echo "==> Starting Flask..."
exec python app.py
