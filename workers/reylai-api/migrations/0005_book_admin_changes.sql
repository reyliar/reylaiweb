CREATE TABLE IF NOT EXISTS admin_action_tokens (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_admin_action_tokens_expires_at
  ON admin_action_tokens(expires_at);

CREATE TABLE IF NOT EXISTS book_admin_changes (
  book_key TEXT PRIMARY KEY,
  title TEXT,
  name TEXT,
  cover_data_url TEXT,
  cover_mime_type TEXT,
  cover_updated_at TEXT,
  deleted_at TEXT,
  updated_at TEXT NOT NULL,
  updated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_book_admin_changes_deleted_at
  ON book_admin_changes(deleted_at);
