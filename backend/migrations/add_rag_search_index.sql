-- Full-text index for the keyword half of hybrid retrieval (services/rag/retrieval.py).
-- The expression must match the one used in queries exactly for Postgres to use it.
CREATE INDEX IF NOT EXISTS ix_tickets_fts ON tickets USING gin (
    to_tsvector('english', coalesce(short_description, '') || ' ' || coalesce(close_notes, '') || ' ' || coalesce(resolution_notes, ''))
);
CREATE INDEX IF NOT EXISTS ix_tickets_upload ON tickets (upload_id);
