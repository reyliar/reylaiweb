ALTER TABLE users ADD COLUMN pending_email TEXT;
ALTER TABLE users ADD COLUMN pending_email_code_hash TEXT;
ALTER TABLE users ADD COLUMN pending_email_expires_at TEXT;
ALTER TABLE users ADD COLUMN pending_email_sent_at TEXT;

CREATE INDEX IF NOT EXISTS users_pending_email_idx ON users(pending_email);
