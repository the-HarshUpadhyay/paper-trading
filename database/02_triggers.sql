-- ============================================================
--  Paper Trading Platform — Oracle 19c / XE
--  02_triggers.sql  |  Business-rule enforcement triggers
-- ============================================================

-- ============================================================
--  TRG_VALIDATE_TRADE
--  BEFORE INSERT on TRANSACTIONS
--  • Prevents selling more shares than owned
--  • Prevents buying when insufficient cash
--  • Sets total_amount automatically
-- ============================================================
CREATE OR REPLACE TRIGGER trg_validate_trade
BEFORE INSERT ON transactions
FOR EACH ROW
DECLARE
    v_available_qty  NUMBER := 0;
    v_user_balance   NUMBER := 0;
    v_required_cash  NUMBER;
BEGIN
    -- Always compute total_amount from qty * price
    :NEW.total_amount := :NEW.quantity * :NEW.price;

    IF :NEW.transaction_type = 'SELL' THEN
        -- Check owned quantity
        SELECT NVL(quantity, 0)
          INTO v_available_qty
          FROM holdings
         WHERE user_id  = :NEW.user_id
           AND stock_id = :NEW.stock_id;

        IF v_available_qty < :NEW.quantity THEN
            RAISE_APPLICATION_ERROR(
                -20001,
                'Insufficient holdings. Owned: ' || v_available_qty ||
                ', Requested: ' || :NEW.quantity
            );
        END IF;

    ELSIF :NEW.transaction_type = 'BUY' THEN
        -- Check cash balance
        SELECT balance
          INTO v_user_balance
          FROM users
         WHERE user_id = :NEW.user_id;

        v_required_cash := :NEW.quantity * :NEW.price;

        IF v_user_balance < v_required_cash THEN
            RAISE_APPLICATION_ERROR(
                -20002,
                'Insufficient balance. Available: $' || TO_CHAR(v_user_balance,'FM999,999,990.00') ||
                ', Required: $' || TO_CHAR(v_required_cash,'FM999,999,990.00')
            );
        END IF;
    END IF;
END;
/


-- ============================================================
--  TRG_UPDATE_HOLDINGS
--  AFTER INSERT on TRANSACTIONS
--  • Upserts HOLDINGS with new quantity & VWAP cost basis
--  • Removes zero-quantity rows
-- ============================================================
CREATE OR REPLACE TRIGGER trg_update_holdings
AFTER INSERT ON transactions
FOR EACH ROW
DECLARE
    v_existing_qty    NUMBER := 0;
    v_existing_avg    NUMBER := 0;
    v_new_qty         NUMBER;
    v_new_avg         NUMBER;
    v_holding_exists  NUMBER := 0;
BEGIN
    -- Check if holding row exists
    SELECT COUNT(*), NVL(MAX(quantity),0), NVL(MAX(avg_buy_price),0)
      INTO v_holding_exists, v_existing_qty, v_existing_avg
      FROM holdings
     WHERE user_id  = :NEW.user_id
       AND stock_id = :NEW.stock_id;

    IF :NEW.transaction_type = 'BUY' THEN
        IF v_holding_exists = 0 THEN
            -- First purchase: insert new holding
            INSERT INTO holdings (user_id, stock_id, quantity, avg_buy_price, last_updated)
            VALUES (:NEW.user_id, :NEW.stock_id, :NEW.quantity, :NEW.price, SYSTIMESTAMP);
        ELSE
            -- Subsequent purchase: VWAP cost basis
            v_new_qty := v_existing_qty + :NEW.quantity;
            v_new_avg := ((v_existing_qty * v_existing_avg) + (:NEW.quantity * :NEW.price)) / v_new_qty;

            UPDATE holdings
               SET quantity       = v_new_qty,
                   avg_buy_price  = v_new_avg,
                   last_updated   = SYSTIMESTAMP
             WHERE user_id  = :NEW.user_id
               AND stock_id = :NEW.stock_id;
        END IF;

    ELSIF :NEW.transaction_type = 'SELL' THEN
        v_new_qty := v_existing_qty - :NEW.quantity;

        IF v_new_qty = 0 THEN
            -- Fully sold out: remove holding row
            DELETE FROM holdings
             WHERE user_id  = :NEW.user_id
               AND stock_id = :NEW.stock_id;
        ELSE
            -- Partial sell: reduce quantity (avg_buy_price unchanged on sells)
            UPDATE holdings
               SET quantity     = v_new_qty,
                   last_updated = SYSTIMESTAMP
             WHERE user_id  = :NEW.user_id
               AND stock_id = :NEW.stock_id;
        END IF;
    END IF;
END;
/


-- ============================================================
--  TRG_UPDATE_USER_BALANCE
--  AFTER INSERT on TRANSACTIONS
--  • Deducts cash on BUY, credits cash on SELL
-- ============================================================
CREATE OR REPLACE TRIGGER trg_update_user_balance
AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    IF :NEW.transaction_type = 'BUY' THEN
        UPDATE users
           SET balance = balance - :NEW.total_amount
         WHERE user_id = :NEW.user_id;

    ELSIF :NEW.transaction_type = 'SELL' THEN
        UPDATE users
           SET balance = balance + :NEW.total_amount
         WHERE user_id = :NEW.user_id;
    END IF;
END;
/


-- ============================================================
--  TRG_STOCKS_UPPER_TICKER
--  BEFORE INSERT OR UPDATE on STOCKS
--  • Enforces ticker is always stored in uppercase
-- ============================================================
CREATE OR REPLACE TRIGGER trg_stocks_upper_ticker
BEFORE INSERT OR UPDATE OF ticker ON stocks
FOR EACH ROW
BEGIN
    :NEW.ticker := UPPER(TRIM(:NEW.ticker));
END;
/

COMMIT;
/

PROMPT Triggers created successfully.
