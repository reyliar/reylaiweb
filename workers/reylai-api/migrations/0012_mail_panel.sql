CREATE TABLE IF NOT EXISTS mail_messages (
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  resend_email_id TEXT UNIQUE,
  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  mailbox TEXT NOT NULL,
  from_email TEXT NOT NULL,
  from_name TEXT,
  to_json TEXT NOT NULL DEFAULT '[]',
  reply_to_json TEXT NOT NULL DEFAULT '[]',
  subject TEXT NOT NULL,
  text_body TEXT NOT NULL DEFAULT '',
  html_body TEXT NOT NULL DEFAULT '',
  snippet TEXT NOT NULL DEFAULT '',
  attachments_json TEXT NOT NULL DEFAULT '[]',
  read_at TEXT,
  received_at TEXT,
  sent_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS mail_messages_mailbox_created_idx ON mail_messages(mailbox, created_at DESC);
CREATE INDEX IF NOT EXISTS mail_messages_thread_idx ON mail_messages(thread_id, created_at);
CREATE INDEX IF NOT EXISTS mail_messages_read_idx ON mail_messages(mailbox, read_at, direction);

CREATE TABLE IF NOT EXISTS mail_sessions (
  token_hash TEXT PRIMARY KEY,
  username TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  ip_address TEXT,
  user_agent TEXT
);

CREATE INDEX IF NOT EXISTS mail_sessions_expires_at_idx ON mail_sessions(expires_at);
