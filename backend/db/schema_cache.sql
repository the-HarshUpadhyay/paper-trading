-- schema_cache.sql — DB-backed price cache for cross-restart persistence.
-- Run once at startup via app.py (CREATE TABLE IF NOT EXISTS equivalent using EXCEPTION block).
-- The in-memory cache (services/cache.py) remains the serving layer;
-- this table is used to warm it on restart and as a fallback if in-memory is cold.

BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE stock_price_cache (
            ticker          VARCHAR2(20)  NOT NULL,
            price           NUMBER(18,4),
            change_pct      NUMBER(10,4),
            open_price      NUMBER(18,4),
            day_high        NUMBER(18,4),
            day_low         NUMBER(18,4),
            previous_close  NUMBER(18,4),
            volume          NUMBER(20),
            market_cap      NUMBER(24),
            fetched_at      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
            CONSTRAINT pk_stock_price_cache PRIMARY KEY (ticker)
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;  -- ORA-00955: table already exists
END;
/
