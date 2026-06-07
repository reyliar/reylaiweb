ALTER TABLE users ADD COLUMN password_change_code_hash TEXT;
ALTER TABLE users ADD COLUMN password_change_expires_at TEXT;
ALTER TABLE users ADD COLUMN password_change_sent_at TEXT;
ALTER TABLE users ADD COLUMN password_change_token_hash TEXT;
ALTER TABLE users ADD COLUMN password_change_token_expires_at TEXT;
