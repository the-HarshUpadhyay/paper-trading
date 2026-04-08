BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE pending_orders (
            order_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id      NUMBER       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            stock_id     NUMBER       NOT NULL REFERENCES stocks(stock_id),
            order_side   VARCHAR2(4)  NOT NULL CHECK (order_side IN (''BUY'',''SELL'')),
            order_type   VARCHAR2(10) NOT NULL CHECK (order_type IN (''LIMIT'',''STOP'',''STOP_LIMIT'')),
            quantity     NUMBER(18,4) NOT NULL,
            limit_price  NUMBER(18,4),
            stop_price   NUMBER(18,4),
            status       VARCHAR2(10) DEFAULT ''OPEN'' NOT NULL
                           CHECK (status IN (''OPEN'',''FILLED'',''CANCELLED'',''EXPIRED'')),
            created_at   TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
            expires_at   TIMESTAMP,
            filled_at    TIMESTAMP,
            filled_price NUMBER(18,4)
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_po_user_status ON pending_orders(user_id, status)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_po_stock_status ON pending_orders(stock_id, status)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
