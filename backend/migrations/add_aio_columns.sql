-- ============================================================
-- Migration: Add AIO Classification Columns
-- Run: psql -U postgres -d triageiq -f add_aio_columns.sql
-- Safe: All columns use IF NOT EXISTS / ADD COLUMN with defaults
-- ============================================================

-- Ticket table: 7 new columns
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS aio_tower VARCHAR;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS aio_category VARCHAR;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS aio_subcategory VARCHAR;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS aio_summary TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS aio_confidence FLOAT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS aio_classified_by VARCHAR;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS aio_needs_review BOOLEAN DEFAULT FALSE;

-- Indexes for fast filtering on Ticket Intelligence tab
CREATE INDEX IF NOT EXISTS idx_tickets_aio_tower ON tickets(aio_tower);
CREATE INDEX IF NOT EXISTS idx_tickets_aio_category ON tickets(aio_category);
CREATE INDEX IF NOT EXISTS idx_tickets_aio_needs_review ON tickets(aio_needs_review);

-- TrainingData table: 3 new columns for AIO label training
ALTER TABLE training_data ADD COLUMN IF NOT EXISTS aio_tower VARCHAR;
ALTER TABLE training_data ADD COLUMN IF NOT EXISTS aio_category VARCHAR;
ALTER TABLE training_data ADD COLUMN IF NOT EXISTS aio_subcategory VARCHAR;

-- Verify
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'tickets' AND column_name LIKE 'aio_%'
ORDER BY ordinal_position;