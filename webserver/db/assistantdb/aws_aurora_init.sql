-- Create user
CREATE USER sb_assistant_webserver_app WITH PASSWORD <INSERT PW HERE>;
CREATE SCHEMA IF NOT EXISTS sbaw_auth;

-- Grant permissions (adjust based on your app's needs)
GRANT CONNECT ON DATABASE postgres TO sb_assistant_webserver_app;
GRANT USAGE ON SCHEMA sbaw_auth TO sb_assistant_webserver_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA sbaw_auth TO sb_assistant_webserver_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sbaw_auth TO sb_assistant_webserver_app;

-- Optional: auto-grant for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA sbaw_auth
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sb_assistant_webserver_app;