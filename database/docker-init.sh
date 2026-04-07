#!/bin/bash
set -e
echo "==> Connecting as trader and running setup scripts..."
sqlplus -s "trader/trader@//localhost:1521/XEPDB1" @/opt/db-scripts/setup.sql
echo "==> Schema initialisation complete."
