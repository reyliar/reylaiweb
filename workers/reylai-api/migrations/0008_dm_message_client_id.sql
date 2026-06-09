ALTER TABLE dm_messages ADD COLUMN client_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_dm_messages_sender_client_id
  ON dm_messages(sender_id, client_id)
  WHERE client_id IS NOT NULL AND client_id <> '';
