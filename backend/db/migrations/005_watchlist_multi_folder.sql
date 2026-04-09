-- Migration 005: Allow same ticker in multiple watchlist folders
-- Drops the old (user_id, stock_id) unique constraint and replaces it with a
-- function-based unique index on (user_id, stock_id, NVL(folder_id, -1)) so
-- the same ticker can appear in different folders but not twice in the same one.

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE watchlist DROP CONSTRAINT uq_watch_user_stk';
EXCEPTION
    WHEN OTHERS THEN IF SQLCODE = -2443 THEN NULL; END IF;  -- constraint not found
END;
/
BEGIN
    EXECUTE IMMEDIATE 'CREATE UNIQUE INDEX idx_wl_user_stk_folder
                        ON watchlist(user_id, stock_id, NVL(folder_id, -1))';
EXCEPTION
    WHEN OTHERS THEN IF SQLCODE = -955 THEN NULL; END IF;   -- index already exists
END;
/
