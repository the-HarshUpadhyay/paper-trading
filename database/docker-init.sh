#!/bin/bash
set -e
echo "==> Connecting as $APP_USER and running setup scripts..."
sqlplus -s "$APP_USER/$APP_USER_PASSWORD@//localhost:1521/XEPDB1" @/opt/db-scripts/setup.sql
echo "==> Schema initialisation complete."
