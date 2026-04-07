-- ============================================================
--  Paper Trading Platform — Oracle 19c / XE
--  01_schema.sql  |  Tables, Indexes, Constraints (3NF)
-- ============================================================

-- Drop in reverse dependency order (safe re-run)
BEGIN
  FOR t IN (
    SELECT table_name FROM user_tables
    WHERE table_name IN (
      'PORTFOLIO_SNAPSHOTS','WATCHLIST','HOLDINGS',
      'TRANSACTIONS','STOCKS','USERS'
    )
  ) LOOP
    EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS';
  END LOOP;
END;
/

-- ============================================================
--  USERS
-- ============================================================
CREATE TABLE users (
    user_id        NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       VARCHAR2(50)    NOT NULL,
    email          VARCHAR2(100)   NOT NULL,
    password_hash  VARCHAR2(256)   NOT NULL,
    balance        NUMBER(15,2)    DEFAULT 100000.00 NOT NULL,
    created_at     TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    is_active      NUMBER(1)       DEFAULT 1 NOT NULL,
    -- Constraints
    CONSTRAINT uq_users_username  UNIQUE (username),
    CONSTRAINT uq_users_email     UNIQUE (email),
    CONSTRAINT chk_users_balance  CHECK  (balance >= 0),
    CONSTRAINT chk_users_active   CHECK  (is_active IN (0,1)),
    CONSTRAINT chk_users_email    CHECK  (email LIKE '%@%.%')
);

COMMENT ON TABLE  users             IS 'Registered platform users with paper-money balance';
COMMENT ON COLUMN users.balance     IS 'Available cash for paper trading (default Rs.10,00,000)';
COMMENT ON COLUMN users.is_active   IS '1=active, 0=deactivated';

-- ============================================================
--  STOCKS  (lookup / catalogue table)
-- ============================================================
CREATE TABLE stocks (
    stock_id      NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker        VARCHAR2(20)    NOT NULL,
    company_name  VARCHAR2(200)   NOT NULL,
    sector        VARCHAR2(100),
    exchange      VARCHAR2(50),
    -- Constraints
    CONSTRAINT uq_stocks_ticker   UNIQUE (ticker),
    CONSTRAINT chk_stocks_ticker  CHECK  (ticker = UPPER(ticker))
);

COMMENT ON TABLE stocks IS 'Canonical stock catalogue; populated on first search/trade';

-- ============================================================
--  TRANSACTIONS  (immutable ledger)
-- ============================================================
CREATE TABLE transactions (
    transaction_id    NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           NUMBER          NOT NULL,
    stock_id          NUMBER          NOT NULL,
    transaction_type  VARCHAR2(4)     NOT NULL,
    quantity          NUMBER(12,4)    NOT NULL,
    price             NUMBER(15,4)    NOT NULL,
    total_amount      NUMBER(18,4)    NOT NULL,
    transaction_time  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    -- Constraints
    CONSTRAINT fk_trans_user    FOREIGN KEY (user_id)  REFERENCES users(user_id),
    CONSTRAINT fk_trans_stock   FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    CONSTRAINT chk_trans_type   CHECK (transaction_type IN ('BUY','SELL')),
    CONSTRAINT chk_trans_qty    CHECK (quantity > 0),
    CONSTRAINT chk_trans_price  CHECK (price > 0),
    CONSTRAINT chk_trans_total  CHECK (total_amount > 0)
);

COMMENT ON TABLE  transactions                  IS 'Immutable trade ledger — never UPDATE/DELETE rows here';
COMMENT ON COLUMN transactions.total_amount     IS 'quantity * price at execution time';

-- ============================================================
--  HOLDINGS  (materialised view of open positions)
-- ============================================================
CREATE TABLE holdings (
    holding_id     NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        NUMBER          NOT NULL,
    stock_id       NUMBER          NOT NULL,
    quantity       NUMBER(12,4)    DEFAULT 0 NOT NULL,
    avg_buy_price  NUMBER(15,4)    DEFAULT 0 NOT NULL,
    last_updated   TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    -- Constraints
    CONSTRAINT fk_hold_user      FOREIGN KEY (user_id)            REFERENCES users(user_id),
    CONSTRAINT fk_hold_stock     FOREIGN KEY (stock_id)           REFERENCES stocks(stock_id),
    CONSTRAINT uq_hold_user_stk  UNIQUE (user_id, stock_id),
    CONSTRAINT chk_hold_qty      CHECK (quantity >= 0),
    CONSTRAINT chk_hold_avg      CHECK (avg_buy_price >= 0)
);

COMMENT ON TABLE  holdings               IS 'Live open positions per user; maintained by trigger';
COMMENT ON COLUMN holdings.avg_buy_price IS 'Volume-weighted average cost basis';

-- ============================================================
--  WATCHLIST
-- ============================================================
CREATE TABLE watchlist (
    watchlist_id  NUMBER    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       NUMBER    NOT NULL,
    stock_id      NUMBER    NOT NULL,
    added_at      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    -- Constraints
    CONSTRAINT fk_watch_user      FOREIGN KEY (user_id)  REFERENCES users(user_id),
    CONSTRAINT fk_watch_stock     FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    CONSTRAINT uq_watch_user_stk  UNIQUE (user_id, stock_id)
);

-- ============================================================
--  PORTFOLIO_SNAPSHOTS  (daily/periodic valuation history)
-- ============================================================
CREATE TABLE portfolio_snapshots (
    snapshot_id    NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        NUMBER          NOT NULL,
    total_value    NUMBER(18,2)    NOT NULL,
    cash_balance   NUMBER(15,2)    NOT NULL,
    holdings_value NUMBER(18,2)    NOT NULL,
    snapshot_date  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    -- Constraints
    CONSTRAINT fk_snap_user     FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT chk_snap_total   CHECK (total_value >= 0),
    CONSTRAINT chk_snap_cash    CHECK (cash_balance >= 0),
    CONSTRAINT chk_snap_holdval CHECK (holdings_value >= 0)
);

COMMENT ON TABLE portfolio_snapshots IS 'Periodic snapshots for portfolio growth chart';

-- ============================================================
--  INDEXES  (cover frequent query patterns)
-- ============================================================
-- Transactions: look up user history, stock history
CREATE INDEX idx_trans_user      ON transactions (user_id, transaction_time DESC);
CREATE INDEX idx_trans_stock     ON transactions (stock_id, transaction_time DESC);
CREATE INDEX idx_trans_user_type ON transactions (user_id, transaction_type);

-- Holdings: look up by user (portfolio page)
CREATE INDEX idx_hold_user       ON holdings (user_id);

-- Watchlist: look up by user
CREATE INDEX idx_watch_user      ON watchlist (user_id);

-- Portfolio snapshots: time-series query
CREATE INDEX idx_snap_user_date  ON portfolio_snapshots (user_id, snapshot_date DESC);

-- Stocks: case-insensitive company name search
CREATE INDEX idx_stocks_name     ON stocks (UPPER(company_name));

COMMIT;
/

PROMPT Schema created successfully.
