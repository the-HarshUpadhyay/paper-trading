BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE notes (
            note_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id    NUMBER        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            ticker     VARCHAR2(20),
            title      VARCHAR2(200) NOT NULL,
            body       CLOB,
            created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_notes_user ON notes(user_id)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_notes_ticker ON notes(ticker)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
