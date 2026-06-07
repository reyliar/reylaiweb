CREATE TABLE IF NOT EXISTS dm_messages (
  id TEXT PRIMARY KEY,
  sender_id TEXT NOT NULL,
  recipient_id TEXT NOT NULL,
  body TEXT,
  kind TEXT NOT NULL DEFAULT 'text',
  attachment_data_url TEXT,
  attachment_name TEXT,
  attachment_mime_type TEXT,
  attachment_size INTEGER,
  voice_duration_ms INTEGER,
  forward_json TEXT,
  created_at TEXT NOT NULL,
  read_at TEXT,
  deleted_at TEXT,
  FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dm_messages_pair_created
  ON dm_messages(sender_id, recipient_id, created_at);

CREATE INDEX IF NOT EXISTS idx_dm_messages_recipient_unread
  ON dm_messages(recipient_id, read_at, created_at);

CREATE INDEX IF NOT EXISTS idx_dm_messages_sender_created
  ON dm_messages(sender_id, created_at);
