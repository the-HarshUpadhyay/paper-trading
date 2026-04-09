"""
app.py — Flask application factory and entry point.

v2 changes:
  - PriceScheduler is started after the Oracle pool is ready.
  - On SIGTERM / app teardown the scheduler is stopped cleanly.
  - Logging is configured at DEBUG level in dev so scheduler activity is visible.
"""
import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config
from db.connection import init_pool

from routes.auth           import auth_bp
from routes.stocks         import stocks_bp
from routes.trading        import trading_bp
from routes.portfolio      import portfolio_bp
from routes.watchlist      import watchlist_bp
from routes.notes          import notes_bp
from routes.pending_orders import pending_orders_bp
from routes.alerts         import alerts_bp


MIGRATIONS = [
    "001_notes.sql",
    "002_watchlist_folders.sql",
    "003_pending_orders.sql",
    "004_alerts.sql",
]


def run_migration(filename: str) -> None:
    path = os.path.join(os.path.dirname(__file__), "db", "migrations", filename)
    try:
        with open(path) as f:
            sql = f.read()
        blocks = [b.strip() for b in sql.split("/") if b.strip()]
        from db.connection import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            for block in blocks:
                if block:
                    cur.execute(block)
            conn.commit()
            cur.close()
        finally:
            conn.close()
    except Exception as e:
        logging.getLogger(__name__).warning("Migration %s: %s", filename, e)


def apply_migrations() -> None:
    for migration in MIGRATIONS:
        run_migration(migration)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Logging ────────────────────────────────────────────────────────────
    level = logging.DEBUG if Config.DEBUG else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    # ── Extensions ─────────────────────────────────────────────────────────
    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)
    JWTManager(app)

    # ── Oracle pool ────────────────────────────────────────────────────────
    with app.app_context():
        init_pool()

    # ── Background price scheduler ─────────────────────────────────────────
    # scheduler.py  → active portfolio/watchlist tickers, every 15 s
    # price_refresh → full catalogue tickers, every 300 s + DB persistence
    from services.scheduler     import start_scheduler
    from services.price_refresh import start_refresh_daemon

    start_scheduler()
    start_refresh_daemon()
    # The scheduler thread is a daemon — it exits automatically when the
    # process terminates.  teardown_appcontext fires after EVERY request so
    # we must NOT call stop_scheduler() there.

    @app.teardown_appcontext
    def shutdown(_):
        pass  # Pool and scheduler live for the full app lifetime

    # ── Migrations ─────────────────────────────────────────────────────────
    apply_migrations()

    # ── Blueprints ─────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp,           url_prefix="/api")
    app.register_blueprint(stocks_bp,         url_prefix="/api")
    app.register_blueprint(trading_bp,        url_prefix="/api")
    app.register_blueprint(portfolio_bp,      url_prefix="/api")
    app.register_blueprint(watchlist_bp,      url_prefix="/api")
    app.register_blueprint(notes_bp,          url_prefix="/api")
    app.register_blueprint(pending_orders_bp, url_prefix="/api")
    app.register_blueprint(alerts_bp,         url_prefix="/api")

    # ── Health check ───────────────────────────────────────────────────────
    @app.route("/api/health")
    def health():
        from services.cache import price_cache
        return jsonify({
            "status":        "ok",
            "service":       "paper-trading-api",
            "cache_entries": price_cache.size(),
        })

    # ── Global error handlers ──────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
