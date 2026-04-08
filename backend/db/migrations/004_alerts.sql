BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE price_alerts (
            alert_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id      NUMBER       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            ticker       VARCHAR2(20) NOT NULL,
            condition    VARCHAR2(5)  NOT NULL CHECK (condition IN (''ABOVE'',''BELOW'')),
            target_price NUMBER(18,4) NOT NULL,
            is_active    NUMBER(1)    DEFAULT 1 NOT NULL,
            created_at   TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
            triggered_at TIMESTAMP
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE notifications (
            notif_id   NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id    NUMBER        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            alert_id   NUMBER        REFERENCES price_alerts(alert_id) ON DELETE SET NULL,
            message    VARCHAR2(500) NOT NULL,
            is_read    NUMBER(1)     DEFAULT 0 NOT NULL,
            created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_notif_user_unread ON notifications(user_id, is_read)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_alert_ticker ON price_alerts(ticker, is_active)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
