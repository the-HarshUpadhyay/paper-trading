BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE watchlist_folders (
            folder_id  NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id    NUMBER        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            name       VARCHAR2(100) NOT NULL,
            created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
            CONSTRAINT uq_wl_folder UNIQUE (user_id, name)
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE '
        ALTER TABLE watchlist ADD (
            folder_id NUMBER REFERENCES watchlist_folders(folder_id) ON DELETE SET NULL
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -1430 THEN NULL; END IF;
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_wl_folder ON watchlist(folder_id)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;
END;
/
