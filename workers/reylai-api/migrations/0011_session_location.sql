ALTER TABLE sessions ADD COLUMN ip_country TEXT;
ALTER TABLE sessions ADD COLUMN ip_region TEXT;
ALTER TABLE sessions ADD COLUMN ip_city TEXT;
ALTER TABLE sessions ADD COLUMN ip_latitude TEXT;
ALTER TABLE sessions ADD COLUMN ip_longitude TEXT;
ALTER TABLE sessions ADD COLUMN ip_timezone TEXT;
ALTER TABLE sessions ADD COLUMN ip_colo TEXT;
ALTER TABLE sessions ADD COLUMN ip_location_json TEXT;

CREATE INDEX IF NOT EXISTS sessions_ip_address_idx ON sessions(ip_address);
