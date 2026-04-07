-- ============================================================
--  Paper Trading Platform — Oracle 19c / XE
--  03_procedures.sql  |  Stored procedures, functions, packages
-- ============================================================


-- ============================================================
--  PACKAGE: pkg_trading
--  Public API for all trading operations
-- ============================================================
CREATE OR REPLACE PACKAGE pkg_trading AS

    -- Execute a BUY order
    PROCEDURE execute_buy (
        p_user_id   IN  users.user_id%TYPE,
        p_ticker    IN  stocks.ticker%TYPE,
        p_quantity  IN  NUMBER,
        p_price     IN  NUMBER,
        p_trans_id  OUT transactions.transaction_id%TYPE
    );

    -- Execute a SELL order
    PROCEDURE execute_sell (
        p_user_id   IN  users.user_id%TYPE,
        p_ticker    IN  stocks.ticker%TYPE,
        p_quantity  IN  NUMBER,
        p_price     IN  NUMBER,
        p_trans_id  OUT transactions.transaction_id%TYPE
    );

    -- Add stock to catalogue if not present; return stock_id
    FUNCTION upsert_stock (
        p_ticker       IN stocks.ticker%TYPE,
        p_company_name IN stocks.company_name%TYPE,
        p_sector       IN stocks.sector%TYPE DEFAULT NULL,
        p_exchange     IN stocks.exchange%TYPE DEFAULT NULL
    ) RETURN stocks.stock_id%TYPE;

END pkg_trading;
/


CREATE OR REPLACE PACKAGE BODY pkg_trading AS

    -- --------------------------------------------------------
    --  upsert_stock: insert or return existing stock_id
    -- --------------------------------------------------------
    FUNCTION upsert_stock (
        p_ticker       IN stocks.ticker%TYPE,
        p_company_name IN stocks.company_name%TYPE,
        p_sector       IN stocks.sector%TYPE DEFAULT NULL,
        p_exchange     IN stocks.exchange%TYPE DEFAULT NULL
    ) RETURN stocks.stock_id%TYPE IS
        v_stock_id stocks.stock_id%TYPE;
        v_ticker   stocks.ticker%TYPE := UPPER(TRIM(p_ticker));
    BEGIN
        SELECT stock_id INTO v_stock_id
          FROM stocks
         WHERE ticker = v_ticker;
        RETURN v_stock_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            INSERT INTO stocks (ticker, company_name, sector, exchange)
            VALUES (v_ticker, p_company_name, p_sector, p_exchange)
            RETURNING stock_id INTO v_stock_id;
            RETURN v_stock_id;
    END upsert_stock;

    -- --------------------------------------------------------
    --  execute_buy
    -- --------------------------------------------------------
    PROCEDURE execute_buy (
        p_user_id   IN  users.user_id%TYPE,
        p_ticker    IN  stocks.ticker%TYPE,
        p_quantity  IN  NUMBER,
        p_price     IN  NUMBER,
        p_trans_id  OUT transactions.transaction_id%TYPE
    ) IS
        v_stock_id  stocks.stock_id%TYPE;
    BEGIN
        -- Validate inputs
        IF p_quantity <= 0 THEN
            RAISE_APPLICATION_ERROR(-20010, 'Quantity must be positive');
        END IF;
        IF p_price <= 0 THEN
            RAISE_APPLICATION_ERROR(-20011, 'Price must be positive');
        END IF;

        -- Resolve stock (create catalogue entry if needed)
        v_stock_id := upsert_stock(p_ticker, p_ticker);

        -- Insert transaction (trg_validate_trade fires here for balance check,
        --                     trg_update_holdings + trg_update_user_balance fire after)
        INSERT INTO transactions (user_id, stock_id, transaction_type, quantity, price, total_amount)
        VALUES (p_user_id, v_stock_id, 'BUY', p_quantity, p_price, p_quantity * p_price)
        RETURNING transaction_id INTO p_trans_id;

        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END execute_buy;

    -- --------------------------------------------------------
    --  execute_sell
    -- --------------------------------------------------------
    PROCEDURE execute_sell (
        p_user_id   IN  users.user_id%TYPE,
        p_ticker    IN  stocks.ticker%TYPE,
        p_quantity  IN  NUMBER,
        p_price     IN  NUMBER,
        p_trans_id  OUT transactions.transaction_id%TYPE
    ) IS
        v_stock_id stocks.stock_id%TYPE;
    BEGIN
        IF p_quantity <= 0 THEN
            RAISE_APPLICATION_ERROR(-20010, 'Quantity must be positive');
        END IF;
        IF p_price <= 0 THEN
            RAISE_APPLICATION_ERROR(-20011, 'Price must be positive');
        END IF;

        -- Stock must already exist if user is selling
        SELECT stock_id INTO v_stock_id
          FROM stocks
         WHERE ticker = UPPER(TRIM(p_ticker));

        INSERT INTO transactions (user_id, stock_id, transaction_type, quantity, price, total_amount)
        VALUES (p_user_id, v_stock_id, 'SELL', p_quantity, p_price, p_quantity * p_price)
        RETURNING transaction_id INTO p_trans_id;

        COMMIT;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            ROLLBACK;
            RAISE_APPLICATION_ERROR(-20012, 'Stock not found: ' || p_ticker);
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END execute_sell;

END pkg_trading;
/


-- ============================================================
--  PACKAGE: pkg_portfolio
--  Portfolio valuation and snapshot utilities
-- ============================================================
CREATE OR REPLACE PACKAGE pkg_portfolio AS

    -- Returns total portfolio value (cash + holdings value at given prices)
    -- Prices are passed as a comma-separated string: 'AAPL:150.25,MSFT:320.10'
    -- In practice the Python layer resolves live prices and calls this.
    FUNCTION get_portfolio_value (
        p_user_id IN users.user_id%TYPE
    ) RETURN NUMBER;

    -- Save a snapshot row (call periodically / after each trade)
    PROCEDURE save_snapshot (
        p_user_id       IN users.user_id%TYPE,
        p_holdings_val  IN NUMBER
    );

    -- Return P/L for a single holding
    FUNCTION get_holding_pl (
        p_user_id    IN users.user_id%TYPE,
        p_stock_id   IN stocks.stock_id%TYPE,
        p_cur_price  IN NUMBER
    ) RETURN NUMBER;

END pkg_portfolio;
/


CREATE OR REPLACE PACKAGE BODY pkg_portfolio AS

    -- --------------------------------------------------------
    --  get_portfolio_value: cash balance only from DB side;
    --  Python enriches with live prices for holdings value.
    -- --------------------------------------------------------
    FUNCTION get_portfolio_value (
        p_user_id IN users.user_id%TYPE
    ) RETURN NUMBER IS
        v_cash NUMBER;
    BEGIN
        SELECT balance INTO v_cash
          FROM users
         WHERE user_id = p_user_id;
        RETURN v_cash;  -- Holdings value added by app layer
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RETURN 0;
    END get_portfolio_value;

    -- --------------------------------------------------------
    --  save_snapshot
    -- --------------------------------------------------------
    PROCEDURE save_snapshot (
        p_user_id       IN users.user_id%TYPE,
        p_holdings_val  IN NUMBER
    ) IS
        v_cash NUMBER;
    BEGIN
        SELECT balance INTO v_cash
          FROM users
         WHERE user_id = p_user_id;

        INSERT INTO portfolio_snapshots
            (user_id, total_value, cash_balance, holdings_value)
        VALUES
            (p_user_id, v_cash + p_holdings_val, v_cash, p_holdings_val);

        COMMIT;
    END save_snapshot;

    -- --------------------------------------------------------
    --  get_holding_pl
    -- --------------------------------------------------------
    FUNCTION get_holding_pl (
        p_user_id    IN users.user_id%TYPE,
        p_stock_id   IN stocks.stock_id%TYPE,
        p_cur_price  IN NUMBER
    ) RETURN NUMBER IS
        v_qty      NUMBER;
        v_avg_cost NUMBER;
    BEGIN
        SELECT quantity, avg_buy_price
          INTO v_qty, v_avg_cost
          FROM holdings
         WHERE user_id  = p_user_id
           AND stock_id = p_stock_id;

        RETURN (p_cur_price - v_avg_cost) * v_qty;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RETURN 0;
    END get_holding_pl;

END pkg_portfolio;
/


-- ============================================================
--  FUNCTION: fn_user_total_invested
--  Returns total cost basis of all open positions for a user
-- ============================================================
CREATE OR REPLACE FUNCTION fn_user_total_invested (
    p_user_id IN users.user_id%TYPE
) RETURN NUMBER IS
    v_total NUMBER := 0;
BEGIN
    SELECT NVL(SUM(quantity * avg_buy_price), 0)
      INTO v_total
      FROM holdings
     WHERE user_id = p_user_id;
    RETURN v_total;
END fn_user_total_invested;
/


-- ============================================================
--  VIEW: vw_user_holdings_detail
--  Joins holdings + stocks for easy portfolio queries
-- ============================================================
CREATE OR REPLACE VIEW vw_user_holdings_detail AS
SELECT
    h.user_id,
    h.holding_id,
    s.stock_id,
    s.ticker,
    s.company_name,
    s.sector,
    s.exchange,
    h.quantity,
    h.avg_buy_price,
    h.quantity * h.avg_buy_price  AS cost_basis,
    h.last_updated
FROM holdings h
JOIN stocks   s ON s.stock_id = h.stock_id
WHERE h.quantity > 0;
/


-- ============================================================
--  VIEW: vw_transaction_history
--  Full transaction log with stock details
-- ============================================================
CREATE OR REPLACE VIEW vw_transaction_history AS
SELECT
    t.transaction_id,
    t.user_id,
    s.ticker,
    s.company_name,
    t.transaction_type,
    t.quantity,
    t.price,
    t.total_amount,
    t.transaction_time
FROM transactions t
JOIN stocks       s ON s.stock_id = t.stock_id
ORDER BY t.transaction_time DESC;
/

COMMIT;
/

PROMPT Procedures, packages, and views created successfully.
