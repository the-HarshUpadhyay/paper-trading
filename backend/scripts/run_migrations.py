"""
scripts/run_migrations.py - Apply backend Oracle migrations before app startup.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import apply_migrations
from db.connection import init_pool


def run():
    print("==> Applying backend migrations...")
    init_pool()
    apply_migrations()
    print("==> Backend migrations complete.")


if __name__ == "__main__":
    run()
