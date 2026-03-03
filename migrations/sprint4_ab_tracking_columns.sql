-- LandFinder Sprint 4 migration: A/B tracking columns
-- Paste into: Supabase Dashboard > SQL Editor > New Query > Run

ALTER TABLE letters     ADD COLUMN IF NOT EXISTS version   TEXT    DEFAULT 'A';
ALTER TABLE letters     ADD COLUMN IF NOT EXISTS hook_type TEXT;
ALTER TABLE touchpoints ADD COLUMN IF NOT EXISTS version   TEXT    DEFAULT 'A';
ALTER TABLE touchpoints ADD COLUMN IF NOT EXISTS responded BOOLEAN DEFAULT FALSE;
